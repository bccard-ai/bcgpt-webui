import re

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType


def _luhn_validate(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 2:
        return False
    checksum = 0
    reverse_digits = digits[::-1]
    for i, d in enumerate(reverse_digits):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def _korean_rrn_validate(rrn: str) -> bool:
    digits = [int(c) for c in rrn if c.isdigit()]
    if len(digits) != 13:
        return False
    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    total = sum(d * w for d, w in zip(digits[:12], weights))
    check = (11 - (total % 11)) % 10
    return check == digits[12]


_PATTERNS: list[tuple[str, re.Pattern[str], str, ThreatSeverity]] = [
    (
        "email",
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "[REDACTED_EMAIL]",
        ThreatSeverity.HIGH,
    ),
    (
        "us_phone",
        re.compile(r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"),
        "[REDACTED_PHONE]",
        ThreatSeverity.MEDIUM,
    ),
    (
        "korean_phone",
        re.compile(r"01[016789]-?\d{3,4}-?\d{4}"),
        "[REDACTED_PHONE]",
        ThreatSeverity.MEDIUM,
    ),
    (
        "us_ssn",
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "[REDACTED_SSN]",
        ThreatSeverity.HIGH,
    ),
    (
        "korean_rrn",
        re.compile(r"\d{6}-[1-4]\d{6}"),
        "[REDACTED_KOREAN_RRN]",
        ThreatSeverity.HIGH,
    ),
    (
        "credit_card",
        re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
        "[REDACTED_CREDIT_CARD]",
        ThreatSeverity.HIGH,
    ),
    (
        "korean_bank_account",
        re.compile(r"\b\d{3,6}-?\d{2,6}-?\d{2,6}\b"),
        "[REDACTED_BANK_ACCOUNT]",
        ThreatSeverity.MEDIUM,
    ),
]


class PIIScanner:
    def scan(self, text: str) -> ScanResult:
        threats: list[ThreatMatch] = []
        rrn_spans: list[tuple[int, int]] = []
        for name, pattern, redaction, severity in _PATTERNS:
            for match in pattern.finditer(text):
                matched = match.group(0)
                if name == "credit_card":
                    digits_only = re.sub(r"[-\s]", "", matched)
                    if not _luhn_validate(digits_only):
                        continue
                if name == "korean_rrn":
                    if not _korean_rrn_validate(matched):
                        continue
                    rrn_spans.append(match.span())
                if name == "us_ssn":
                    parts = matched.split("-")
                    if all(p == "0" * len(p) for p in parts):
                        continue
                    if parts[0] == "666" or parts[0].startswith("9"):
                        if int(parts[2]) < 1:
                            continue
                if name == "korean_bank_account" and rrn_spans:
                    if any(
                        s <= match.start() and match.end() <= e for s, e in rrn_spans
                    ):
                        continue
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.PII,
                        pattern_name=name,
                        matched_text=matched[:50],
                        masked_text=redaction,
                        severity=severity,
                        confidence=0.95,
                    )
                )
        masked = self.mask(text) if threats else None
        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="pii",
            masked_text=masked,
        )

    def mask(self, text: str) -> str:
        result = text
        for name, pattern, redaction, severity in _PATTERNS:

            def _replacer(
                m: re.Match, _redaction: str = redaction, _name: str = name
            ) -> str:
                if _name == "credit_card":
                    digits_only = re.sub(r"[-\s]", "", m.group(0))
                    if not _luhn_validate(digits_only):
                        return m.group(0)
                if _name == "korean_rrn":
                    if not _korean_rrn_validate(m.group(0)):
                        return m.group(0)
                return _redaction

            result = pattern.sub(_replacer, result)
        return result

    def mask_verified(self, text: str, verified_threats: list) -> str:
        """Mask only the specific PII matches that were verified by LLM."""
        if not verified_threats:
            return text

        redaction_map = {}
        for name, pattern, redaction, severity in _PATTERNS:
            redaction_map[name] = redaction

        result = text
        for threat in verified_threats:
            if threat.threat_type.value != "pii":
                continue
            redaction = redaction_map.get(threat.pattern_name, "[REDACTED]")
            matched = threat.matched_text
            if matched and matched in result:
                result = result.replace(matched, redaction)

        return result
