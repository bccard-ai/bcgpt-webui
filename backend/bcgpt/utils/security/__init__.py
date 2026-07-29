from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ThreatSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ThreatType(str, Enum):
    PROMPT_INJECTION = "prompt_injection"
    JAILBREAK = "jailbreak"
    PII = "pii"
    TOXICITY = "toxicity"
    SECRET = "secret"
    OUTPUT_FILTER = "output_filter"
    LLM_DETECTION = "llm_detection"


@dataclass
class ThreatMatch:
    threat_type: ThreatType
    pattern_name: str
    matched_text: str
    masked_text: str = "[REDACTED]"
    severity: ThreatSeverity = ThreatSeverity.MEDIUM
    description: str = ""
    confidence: float = 1.0


@dataclass
class ScanResult:
    is_safe: bool
    threats: list[ThreatMatch] = field(default_factory=list)
    scanner_name: str = ""
    masked_text: Optional[str] = None
    pii_should_block: bool = False


class SecurityException(Exception):
    def __init__(self, message: str, threats: list[ThreatMatch]):
        super().__init__(message)
        self.threats = threats


class PIIBlockException(SecurityException):
    pass


PII_BLOCKED_MESSAGE_KO = "Your message was blocked because it appears to contain personal information. Please remove any personal information and try again."

BLOCKED_MESSAGE_KO = "Message could not be processed. Blocked by security policy."
BLOCKED_MESSAGE_EN = "Message could not be processed. Blocked by security policy."


class SecurityPreset(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    STRICT = "strict"


PRESET_CONFIGS: dict[SecurityPreset, dict[str, bool]] = {
    SecurityPreset.MINIMAL: {
        "SECURITY_PROMPT_INJECTION_ENABLED": True,
        "SECURITY_JAILBREAK_ENABLED": False,
        "SECURITY_PII_ENABLED": False,
        "SECURITY_TOXICITY_ENABLED": False,
        "SECURITY_SECRETS_ENABLED": True,
        "SECURITY_OUTPUT_FILTER_ENABLED": False,
        "SECURITY_LLM_SCANNER_ENABLED": False,
        "SECURITY_SHADOW_MODE": True,
        "SECURITY_FAIL_CLOSED": False,
        "SECURITY_OUTPUT_ENFORCEMENT": False,
    },
    SecurityPreset.STANDARD: {
        "SECURITY_PROMPT_INJECTION_ENABLED": True,
        "SECURITY_JAILBREAK_ENABLED": True,
        "SECURITY_PII_ENABLED": True,
        "SECURITY_TOXICITY_ENABLED": False,
        "SECURITY_SECRETS_ENABLED": True,
        "SECURITY_OUTPUT_FILTER_ENABLED": True,
        "SECURITY_LLM_SCANNER_ENABLED": False,
        "SECURITY_SHADOW_MODE": False,
        "SECURITY_FAIL_CLOSED": False,
        "SECURITY_OUTPUT_ENFORCEMENT": False,
    },
    SecurityPreset.STRICT: {
        "SECURITY_PROMPT_INJECTION_ENABLED": True,
        "SECURITY_JAILBREAK_ENABLED": True,
        "SECURITY_PII_ENABLED": True,
        "SECURITY_TOXICITY_ENABLED": True,
        "SECURITY_SECRETS_ENABLED": True,
        "SECURITY_OUTPUT_FILTER_ENABLED": True,
        "SECURITY_LLM_SCANNER_ENABLED": True,
        "SECURITY_SHADOW_MODE": False,
        "SECURITY_FAIL_CLOSED": True,
        "SECURITY_OUTPUT_ENFORCEMENT": True,
    },
}


def apply_security_preset(config, preset: SecurityPreset | str) -> None:
    settings = PRESET_CONFIGS.get(
        preset if isinstance(preset, SecurityPreset) else SecurityPreset(preset)
    )
    if not settings:
        return
    for key, value in settings.items():
        setattr(config, key, value)


import asyncio
import hashlib
import logging
import os

log = logging.getLogger(__name__)

# Wall-clock ceiling for any single LLM-based scanner call. Scanners run on the
# request critical path (before the user's real completion streams), so an
# unbounded scan call directly inflates TTFT. Bounded + fail-open keeps a slow
# or hung scanner from hanging the whole request. Env-overridable; also read
# per-call from config via ``scanner_timeout`` so it can move to admin settings.
_DEFAULT_SCANNER_TIMEOUT = float(os.environ.get("SECURITY_SCANNER_TIMEOUT", "8") or "8")

# Cap how many recent user turns the multi-turn conversation scanner inspects,
# so cost stays flat instead of growing with history length on every request.
_DEFAULT_CONVERSATION_MAX_MESSAGES = int(
    os.environ.get("SECURITY_CONVERSATION_MAX_MESSAGES", "10") or "10"
)


def _config_value(config, name, default):
    """Read a (possibly PersistentConfig-wrapped) numeric setting, with fallback."""
    val = getattr(config, name, None)
    if hasattr(val, "value"):
        val = val.value
    return val if val not in (None, "") else default


def scanner_timeout(config) -> float:
    """Per-call timeout (seconds) for LLM-based scanners."""
    try:
        t = float(
            _config_value(config, "SECURITY_SCANNER_TIMEOUT", _DEFAULT_SCANNER_TIMEOUT)
        )
        return t if t > 0 else _DEFAULT_SCANNER_TIMEOUT
    except (TypeError, ValueError):
        return _DEFAULT_SCANNER_TIMEOUT


# Scanner submodules import ``scanner_timeout`` from this package, so these
# imports must come after it is defined above.
from bcgpt.utils.security.prompt_injection import PromptInjectionScanner
from bcgpt.utils.security.jailbreak import JailbreakScanner
from bcgpt.utils.security.pii import PIIScanner
from bcgpt.utils.security.toxicity import ToxicityScanner
from bcgpt.utils.security.secrets import SecretsScanner
from bcgpt.utils.security.output_filter import OutputFilterScanner
from bcgpt.utils.security.guardrail_scanner import GuardrailScanner


class SecurityPipeline:
    def __init__(self, config):
        self.config = config
        self._prompt_injection = PromptInjectionScanner()
        self._jailbreak = JailbreakScanner()
        self._pii = PIIScanner()
        self._toxicity = ToxicityScanner()
        self._secrets = SecretsScanner()
        self._output_filter = OutputFilterScanner()
        self._guardrail = GuardrailScanner(config)

        from .llm_scanner import LLMScanner

        self._llm_scanner = LLMScanner(config)

    def _filter_by_confidence(self, threats: list[ThreatMatch]) -> list[ThreatMatch]:
        """Filter threats below the configured confidence threshold."""
        threshold = (
            float(self.config.SECURITY_CONFIDENCE_THRESHOLD)
            if hasattr(self.config, "SECURITY_CONFIDENCE_THRESHOLD")
            else 0.0
        )
        return [t for t in threats if (t.confidence or 0) >= threshold]

    async def scan_input(
        self,
        text: str,
        user: dict,
        metadata: dict = None,
        *,
        request=None,
        skip_llm: bool = False,
    ) -> ScanResult:
        all_threats = []
        pii_threats = None

        if self.config.SECURITY_PROMPT_INJECTION_ENABLED:
            result = self._prompt_injection.scan(text)
            all_threats.extend(result.threats)

        if self.config.SECURITY_JAILBREAK_ENABLED:
            result = self._jailbreak.scan(text)
            all_threats.extend(result.threats)

        regex_pii_threats = []
        if self.config.SECURITY_PII_ENABLED:
            result = self._pii.scan(text)
            regex_pii_threats = list(result.threats)
            pii_threats = list(regex_pii_threats)

            if (
                pii_threats
                and not skip_llm
                and self.config.SECURITY_LLM_SCANNER_ENABLED
                and request
            ):
                try:
                    pii_threats = await self._llm_scanner.verify_pii_threats(
                        pii_threats, text, request, user
                    )
                except Exception as e:
                    log.warning(
                        f"PII LLM verification failed, keeping regex results: {e}"
                    )

            all_threats.extend(pii_threats)

        if self.config.SECURITY_TOXICITY_ENABLED:
            custom_words = self.config.SECURITY_TOXICITY_CUSTOM_WORD_LIST or ""
            result = self._toxicity.scan(text, custom_words=custom_words)
            all_threats.extend(result.threats)

        if self.config.SECURITY_SECRETS_ENABLED:
            result = self._secrets.scan(text)
            all_threats.extend(result.threats)

        # LLM-based scanners (slow). Both gated by ``skip_llm`` so the
        # conversation scanner and shadow-mode critical path stay regex-only.
        # Run them concurrently so latency is the max of the two, not the sum.
        if not skip_llm and request:
            llm_jobs = []
            if self.config.SECURITY_LLM_SCANNER_ENABLED:
                llm_jobs.append(
                    (
                        "LLM input scan",
                        self._llm_scanner.scan_input(text, request, user),
                    )
                )
            if getattr(self.config, "SECURITY_GUARDRAIL_ENABLED", False):
                llm_jobs.append(
                    ("Guardrail scan", self._guardrail.scan(text, request, user))
                )

            if llm_jobs:
                results = await asyncio.gather(
                    *(job for _, job in llm_jobs), return_exceptions=True
                )
                for (name, _), result in zip(llm_jobs, results):
                    if isinstance(result, Exception):
                        if getattr(self.config, "SECURITY_FAIL_CLOSED", False):
                            all_threats.append(
                                ThreatMatch(
                                    threat_type=ThreatType.LLM_DETECTION,
                                    pattern_name=f"{name}_failure",
                                    matched_text="",
                                    severity=ThreatSeverity.HIGH,
                                    description=f"{name} failed/timed out (fail-closed)",
                                    confidence=1.0,
                                )
                            )
                            log.warning("%s failed, fail-closed: %s", name, result)
                        else:
                            log.warning("%s failed, failing open: %s", name, result)
                    else:
                        all_threats.extend(result.threats)

        all_threats = self._filter_by_confidence(all_threats)

        is_safe = len(all_threats) == 0

        # PII masking: always apply regex-based masking when PII scanner
        # detected threats, regardless of LLM verification outcome.  LLM
        # verification only affects the block/allow decision, not masking.
        masked_text = text
        if self.config.SECURITY_PII_ENABLED and regex_pii_threats:
            masked_text = self._pii.mask(text)

        combined = ScanResult(
            is_safe=is_safe,
            threats=all_threats,
            scanner_name="SecurityPipeline",
            masked_text=masked_text if masked_text != text else None,
        )

        if self.config.SECURITY_LOG_DETECTIONS and not is_safe:
            self._log_detection(
                combined, user, text, direction="input", metadata=metadata
            )

        return combined

    async def scan_output(
        self, text: str, metadata: dict = None, *, request=None, user=None
    ) -> ScanResult:
        if not self.config.SECURITY_OUTPUT_FILTER_ENABLED:
            return ScanResult(is_safe=True, scanner_name="SecurityPipeline")

        result = self._output_filter.scan(text)
        if self.config.SECURITY_LLM_SCANNER_ENABLED and request:
            try:
                llm_result = await self._llm_scanner.scan_output(text, request, user)
                result.threats.extend(llm_result.threats)
            except Exception as e:
                if getattr(self.config, "SECURITY_FAIL_CLOSED", False):
                    result.threats.append(
                        ThreatMatch(
                            threat_type=ThreatType.LLM_DETECTION,
                            pattern_name="output_llm_scan_failure",
                            matched_text="",
                            severity=ThreatSeverity.HIGH,
                            description="LLM output scan failed/timed out (fail-closed)",
                            confidence=1.0,
                        )
                    )
                    log.warning("LLM output scan failed, fail-closed: %s", e)
                else:
                    log.warning(f"LLM output scan failed, failing open: {e}")
        result.threats = self._filter_by_confidence(result.threats)
        result.is_safe = len(result.threats) == 0
        if self.config.SECURITY_LOG_DETECTIONS and not result.is_safe:
            self._log_detection(
                result, user=None, text=text, direction="output", metadata=metadata
            )
        return result

    async def scan_conversation(
        self, messages: list, user: dict = None, metadata: dict = None, *, request=None
    ) -> ScanResult:
        """Multi-turn attack detector: aggregates threat signals across conversation history."""
        all_threats = []
        conversation_score = 0.0

        user_messages = [m for m in messages if m.get("role") == "user"]
        total_messages = len(user_messages)

        # Only inspect the most recent user turns so per-request cost stays flat
        # rather than growing with the full conversation history every time.
        max_user = int(
            _config_value(
                self.config,
                "SECURITY_CONVERSATION_MAX_MESSAGES",
                _DEFAULT_CONVERSATION_MAX_MESSAGES,
            )
        )
        user_indices = [i for i, m in enumerate(messages) if m.get("role") == "user"]
        allowed_indices = (
            set(user_indices[-max_user:]) if max_user > 0 else set(user_indices)
        )

        severity_weights = {"critical": 3.0, "high": 2.0, "medium": 1.0, "low": 0.5}

        for i, msg in enumerate(messages):
            if msg.get("role") != "user" or i not in allowed_indices:
                continue

            content = msg.get("content", "")
            if not content or not isinstance(content, str):
                continue

            result = await self.scan_input(
                content, user, metadata, request=request, skip_llm=True
            )

            if result.threats:
                recency_weight = 1.0 + (i / max(total_messages, 1))
                for threat in result.threats:
                    sev = (
                        threat.severity.value
                        if hasattr(threat.severity, "value")
                        else str(threat.severity)
                    )
                    conversation_score += (
                        severity_weights.get(sev, 1.0) * recency_weight
                    )
                    all_threats.append(threat)

        all_threats = self._filter_by_confidence(all_threats)

        threshold = (
            float(self.config.SECURITY_CONVERSATION_THRESHOLD)
            if hasattr(self.config, "SECURITY_CONVERSATION_THRESHOLD")
            else 2.0
        )
        is_safe = conversation_score < threshold

        masked_text = None
        if not is_safe and self.config.SECURITY_PII_ENABLED:
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    masked_text = self._pii.mask(msg.get("content", ""))
                    break

        result = ScanResult(
            is_safe=is_safe,
            threats=all_threats,
            scanner_name="ConversationSecurityPipeline",
            masked_text=masked_text,
        )

        if all_threats and self.config.SECURITY_LOG_DETECTIONS:
            self._log_detection(
                result,
                user,
                f"[CONVERSATION] score={conversation_score:.2f}, threshold={threshold}, messages_scanned={total_messages}",
                direction="input",
                metadata={
                    **(metadata or {}),
                    "conversation_score": conversation_score,
                    "messages_scanned": total_messages,
                },
            )

        return result

    def should_block(self, result: ScanResult) -> bool:
        return not result.is_safe and not self.config.SECURITY_SHADOW_MODE

    def should_block_pii(self, result: ScanResult) -> bool:
        return result.pii_should_block

    def _log_detection(
        self,
        result: ScanResult,
        user: dict | None,
        text: str,
        direction: str = "input",
        metadata: dict = None,
    ):
        safe_text = self._pii.mask(text[:200]) if text else ""
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16] if text else ""
        log.info(
            "Security detection",
            extra={
                "scanner": result.scanner_name,
                "threat_count": len(result.threats),
                "threat_types": [t.threat_type.value for t in result.threats],
                "user_id": user.get("id", "unknown") if user else "system",
                "text_hash": text_hash,
                "text_sample": safe_text,
            },
        )

        try:
            from bcgpt.models.security_events import SecurityEvents, SecurityEventForm

            severities = [t.severity.value for t in result.threats]
            severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
            max_severity = (
                max(severities, key=lambda s: severity_order.get(s, 0))
                if severities
                else "info"
            )
            event = SecurityEventForm(
                user_id=user.get("id") if user else None,
                chat_id=metadata.get("chat_id") if metadata else None,
                message_id=metadata.get("message_id") if metadata else None,
                session_id=metadata.get("session_id") if metadata else None,
                direction=direction,
                scanner_name=result.scanner_name or "pipeline",
                threat_types=[t.threat_type.value for t in result.threats],
                threat_count=len(result.threats),
                severity=max_severity,
                is_blocked=self.should_block(result),
                is_shadow=self.config.SECURITY_SHADOW_MODE,
                text_hash=text_hash,
                text_sample=safe_text[:200],
                model_id=metadata.get("model_id") if metadata else None,
                metadata=metadata,
            )
            SecurityEvents.insert_new_event(event)
        except Exception as e:
            log.error(f"Failed to persist security event: {e}")

        if getattr(self.config, "SECURITY_SIEM_WEBHOOK_ENABLED", False):
            try:
                from bcgpt.utils.security.siem_webhook import (
                    send_siem_event,
                    format_security_event_for_siem,
                )

                webhook_url = getattr(self.config, "SECURITY_SIEM_WEBHOOK_URL", "")
                if webhook_url:
                    headers_raw = getattr(
                        self.config, "SECURITY_SIEM_WEBHOOK_HEADERS", "{}"
                    )
                    import json

                    try:
                        headers = (
                            json.loads(headers_raw)
                            if isinstance(headers_raw, str)
                            else {}
                        )
                    except (json.JSONDecodeError, TypeError):
                        headers = {}
                    siem_event = format_security_event_for_siem(
                        result, user, text_hash, metadata
                    )
                    import asyncio

                    asyncio.ensure_future(
                        send_siem_event(siem_event, webhook_url, headers)
                    )
            except Exception as e:
                log.warning(f"SIEM webhook dispatch failed: {e}")
