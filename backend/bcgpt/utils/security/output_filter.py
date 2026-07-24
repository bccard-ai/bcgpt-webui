import re

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType
from .pii import PIIScanner
from .secrets import SecretsScanner

_INTERNAL_URL_PATTERN = re.compile(
    r"http://(localhost|127\.0\.0\.1|10\.\d+\.\d+\.\d+|172\.(1[6-9]|2\d|3[01])\.\d+\.\d+|192\.168\.\d+\.\d+):\d+"
)

_INSTRUCTION_PATTERNS = [
    re.compile(r"(?i)you\s+are\s+a\b", re.IGNORECASE),
    re.compile(r"(?i)always\s+(respond|answer|act|follow)", re.IGNORECASE),
    re.compile(r"(?i)never\s+(reveal|disclose|mention)", re.IGNORECASE),
    re.compile(r"(?i)your\s+instructions\s+are", re.IGNORECASE),
    re.compile(r"(?i)system\s*:\s*", re.IGNORECASE),
]


class OutputFilterScanner:
    def __init__(self) -> None:
        self._pii = PIIScanner()
        self._secrets = SecretsScanner()

    def scan(self, text: str) -> ScanResult:
        threats: list[ThreatMatch] = []

        pii_result = self._pii.scan(text)
        threats.extend(pii_result.threats)

        secrets_result = self._secrets.scan(text)
        threats.extend(secrets_result.threats)

        for match in _INTERNAL_URL_PATTERN.finditer(text):
            threats.append(
                ThreatMatch(
                    threat_type=ThreatType.OUTPUT_FILTER,
                    pattern_name="internal_url",
                    matched_text=match.group(0)[:50],
                    masked_text="[REDACTED_URL]",
                    severity=ThreatSeverity.HIGH,
                    confidence=0.9,
                )
            )

        if len(text) > 200:
            instruction_hits = sum(1 for p in _INSTRUCTION_PATTERNS if p.search(text))
            if instruction_hits >= 2:
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.OUTPUT_FILTER,
                        pattern_name="system_prompt_leakage",
                        matched_text=text[:50],
                        masked_text="[REDACTED_PROMPT]",
                        severity=ThreatSeverity.HIGH,
                        confidence=0.7,
                        description="Possible system prompt leakage detected",
                    )
                )

        masked_text = text
        if pii_result.masked_text:
            masked_text = pii_result.masked_text
        for t in threats:
            if t.threat_type == ThreatType.SECRET:
                masked_text = masked_text.replace(t.matched_text, t.masked_text)
        masked_text = _INTERNAL_URL_PATTERN.sub("[REDACTED_URL]", masked_text)

        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="output_filter",
            masked_text=masked_text if threats else None,
        )
