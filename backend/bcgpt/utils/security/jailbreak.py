import re

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType

_PATTERNS: list[tuple[str, re.Pattern[str], ThreatSeverity]] = [
    (
        "dan_do_anything_now",
        re.compile(r"do\s+anything\s+now", re.IGNORECASE),
        ThreatSeverity.HIGH,
    ),
    ("dan_mode", re.compile(r"dan\s+mode", re.IGNORECASE), ThreatSeverity.HIGH),
    ("dan_version", re.compile(r"dan\s+\d+\.\d+", re.IGNORECASE), ThreatSeverity.HIGH),
    ("jailbreak", re.compile(r"jailbreak(ed)?", re.IGNORECASE), ThreatSeverity.HIGH),
    (
        "pretend_no_rules",
        re.compile(
            r"pretend\s+you\s+(are|have)\s+no\s+(rules|restrictions|limits)",
            re.IGNORECASE,
        ),
        ThreatSeverity.MEDIUM,
    ),
    (
        "imagine_unfiltered",
        re.compile(
            r"imagine\s+you\s+are\s+(an?\s+)?(unfiltered|unrestricted|uncensored)",
            re.IGNORECASE,
        ),
        ThreatSeverity.MEDIUM,
    ),
    (
        "roleplay_evil",
        re.compile(
            r"roleplay\s+as\s+(an?\s+)?(evil|unfiltered|uncensored)", re.IGNORECASE
        ),
        ThreatSeverity.MEDIUM,
    ),
    (
        "act_no_rules",
        re.compile(
            r"act\s+as\s+(if\s+|though\s+)?you\s+(are|have)\s+no\s+(rules|restrictions)",
            re.IGNORECASE,
        ),
        ThreatSeverity.MEDIUM,
    ),
    (
        "hypothetical_scenario",
        re.compile(
            r"this\s+is\s+a\s+(test|experiment|hypothetical|fictional)\s+scenario",
            re.IGNORECASE,
        ),
        ThreatSeverity.LOW,
    ),
    (
        "bypass_safety",
        re.compile(
            r"(bypass|circumvent|evade)\s+(your\s+|all\s+|the\s+)?(safety|security|content)",
            re.IGNORECASE,
        ),
        ThreatSeverity.LOW,
    ),
    ("ko_remove_limits", re.compile(r"모든\s*제한.*해제"), ThreatSeverity.HIGH),
    ("ko_bypass_filter", re.compile(r"필터.*우회"), ThreatSeverity.HIGH),
    ("ko_no_limits", re.compile(r"제한\s*없이"), ThreatSeverity.MEDIUM),
    ("ko_no_censorship", re.compile(r"검열\s*없이"), ThreatSeverity.MEDIUM),
]


class JailbreakScanner:
    def scan(self, text: str) -> ScanResult:
        threats: list[ThreatMatch] = []
        for name, pattern, severity in _PATTERNS:
            for match in pattern.finditer(text):
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.JAILBREAK,
                        pattern_name=name,
                        matched_text=match.group(0)[:50],
                        masked_text="[REDACTED]",
                        severity=severity,
                        confidence=0.85,
                    )
                )
        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="jailbreak",
        )
