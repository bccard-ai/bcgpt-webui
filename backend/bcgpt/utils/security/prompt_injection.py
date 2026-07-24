import re

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType

_EN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore_instructions",
        re.compile(r"ignore\s+.*?(?:instructions|prompts|rules)", re.IGNORECASE),
    ),
    (
        "disregard_training",
        re.compile(r"disregard\s+(your\s+|all\s+)?training", re.IGNORECASE),
    ),
    (
        "forget_knowledge",
        re.compile(
            r"forget\s+(everything\s+|all\s+)?you\s+(know|were\s+told)", re.IGNORECASE
        ),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            r"reveal\s+(your\s+|the\s+)?(system|initial)\s+prompt", re.IGNORECASE
        ),
    ),
    (
        "developer_mode",
        re.compile(
            r"you\s+are\s+(now\s+)?(in\s+|a\s+)?(developer|admin|debug|god)\s+mode",
            re.IGNORECASE,
        ),
    ),
    ("bypass", re.compile(r"BYPASS", re.IGNORECASE)),
    (
        "override_filter",
        re.compile(
            r"override\s+(your\s+|all\s+)?(safety|security|content)\s+(filter|guard|policy|rules)",
            re.IGNORECASE,
        ),
    ),
    ("new_instructions", re.compile(r"new\s+instructions:?", re.IGNORECASE)),
    (
        "stop_being_ai",
        re.compile(
            r"stop\s+(being|acting\s+as|following)\s+(a\s+|an\s+)?(AI|assistant|helpful)",
            re.IGNORECASE,
        ),
    ),
]

_KO_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("ko_previous_instructions", re.compile(r"이전\s*지시")),
    ("ko_system_prompt", re.compile(r"시스템\s*프롬프트")),
    ("ko_ignore_rules", re.compile(r"모든\s*규칙.*무시")),
    ("ko_forget_instructions", re.compile(r"원래\s*지시.*잊어")),
    ("ko_developer_mode", re.compile(r"개발자\s*모드")),
    ("ko_bypass_filter", re.compile(r"필터.*우회")),
]

_ALL_PATTERNS = _EN_PATTERNS + _KO_PATTERNS


class PromptInjectionScanner:
    def scan(self, text: str) -> ScanResult:
        threats: list[ThreatMatch] = []
        for name, pattern in _ALL_PATTERNS:
            for match in pattern.finditer(text):
                matched = match.group(0)
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.PROMPT_INJECTION,
                        pattern_name=name,
                        matched_text=matched[:50],
                        masked_text="[REDACTED]",
                        severity=ThreatSeverity.HIGH,
                        confidence=0.9,
                    )
                )
        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="prompt_injection",
        )
