import re

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType

_PATTERNS: list[tuple[str, re.Pattern[str], ThreatSeverity]] = [
    (
        "aws_access_key",
        re.compile(
            r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}"
        ),
        ThreatSeverity.HIGH,
    ),
    ("github_token", re.compile(r"gh[ps]_[A-Za-z0-9_]{36,}"), ThreatSeverity.HIGH),
    (
        "generic_api_key",
        re.compile(
            r"(?i)(api[_\-]?key|apikey|access[_\-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9\-_]{20,}"
        ),
        ThreatSeverity.MEDIUM,
    ),
    (
        "generic_secret",
        re.compile(
            r"(?i)(secret|password|passwd|token)\s*[:=]\s*['\"]?[A-Za-z0-9\-_!@#$%^&*]{8,}"
        ),
        ThreatSeverity.MEDIUM,
    ),
    ("openai_api_key", re.compile(r"sk-proj-[A-Za-z0-9]{20,}"), ThreatSeverity.HIGH),
    (
        "bearer_token",
        re.compile(r"Bearer\s+[A-Za-z0-9\-_.~+/]+=*"),
        ThreatSeverity.HIGH,
    ),
    (
        "private_key",
        re.compile(r"-----BEGIN\s+(?:RSA\s+|EC\s+|DSA\s+)?PRIVATE\s+KEY-----"),
        ThreatSeverity.HIGH,
    ),
    (
        "jwt",
        re.compile(r"eyJ[A-Za-z0-9\-_]+\.eyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+"),
        ThreatSeverity.MEDIUM,
    ),
]


def _mask_match(matched: str) -> str:
    if len(matched) <= 8:
        return matched[:4] + "..."
    return matched[:8] + "..."


class SecretsScanner:
    def scan(self, text: str) -> ScanResult:
        threats: list[ThreatMatch] = []
        for name, pattern, severity in _PATTERNS:
            for match in pattern.finditer(text):
                matched = match.group(0)
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.SECRET,
                        pattern_name=name,
                        matched_text=_mask_match(matched),
                        masked_text=_mask_match(matched),
                        severity=severity,
                        confidence=0.95,
                    )
                )
        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="secrets",
        )
