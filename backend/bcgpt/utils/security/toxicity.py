import re
import unicodedata

from . import ScanResult, ThreatMatch, ThreatSeverity, ThreatType

_PROFANITY_EN: list[str] = [
    "fuck",
    "shit",
    "damn",
    "ass",
    "bitch",
    "bastard",
    "crap",
    "dick",
    "piss",
    "hell",
]

_PROFANITY_KO: list[str] = [
    "씨발",
    "시발",
    "좆",
    "병신",
    "개새",
    "개새끼",
    "쌍놈",
    "지랄",
    "염병",
    "꺼져",
    "미친놈",
    "닥쳐",
    "쓰레기",
    "멍청이",
    "바보",
]

_THREAT_EN: list[str] = [
    "kill",
    "bomb",
    "murder",
    "terrorist",
    "terrorism",
    "threat",
    "attack",
    "weapon",
    "explode",
]

_THREAT_KO: list[str] = [
    "죽여",
    "죽이겠",
    "폭발",
    "테러",
    "위협",
    "공격",
    "무기",
]

_HATE_SPEECH_EN: list[str] = [
    "nigger",
    "nigga",
    "faggot",
    "retard",
    "chink",
]

_HATE_SPEECH_KO: list[str] = [
    "짱깨",
    "쪽바리",
    "흑형",
    "혐오",
    "차별",
]


def _is_cjk(s: str) -> bool:
    for ch in s:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0xAC00 <= cp <= 0xD7AF
            or 0x3040 <= cp <= 0x30FF
        ):
            return True
    return False


def _build_pattern(words: list[str]) -> re.Pattern[str]:
    en_words = [re.escape(w) for w in words if not _is_cjk(w)]
    ko_words = [re.escape(w) for w in words if _is_cjk(w)]
    parts: list[str] = []
    if en_words:
        parts.append(r"\b(?:{})\b".format("|".join(en_words)))
    if ko_words:
        parts.append("(?:{})".format("|".join(ko_words)))
    if not parts:
        return re.compile(r"(?!)")
    return re.compile("|".join(parts), re.IGNORECASE)


_WORD_CATEGORIES: list[tuple[list[str], ThreatSeverity, str]] = [
    (_THREAT_EN + _THREAT_KO, ThreatSeverity.HIGH, "threat"),
    (_HATE_SPEECH_EN + _HATE_SPEECH_KO, ThreatSeverity.HIGH, "hate_speech"),
    (_PROFANITY_EN + _PROFANITY_KO, ThreatSeverity.MEDIUM, "profanity"),
]


class ToxicityScanner:
    def scan(self, text: str, custom_words: str = "") -> ScanResult:
        threats: list[ThreatMatch] = []
        custom_list = (
            [w.strip() for w in custom_words.split(",") if w.strip()]
            if custom_words
            else []
        )

        for word_list, severity, category in _WORD_CATEGORIES:
            all_words = word_list + [w for w in custom_list if category == "profanity"]
            if not all_words:
                continue
            pattern = _build_pattern(all_words)
            for match in pattern.finditer(text):
                threats.append(
                    ThreatMatch(
                        threat_type=ThreatType.TOXICITY,
                        pattern_name=f"{category}:{match.group(0).lower()}",
                        matched_text=match.group(0)[:50],
                        masked_text="[REDACTED]",
                        severity=severity,
                        confidence=0.8,
                    )
                )
        return ScanResult(
            is_safe=len(threats) == 0,
            threats=threats,
            scanner_name="toxicity",
        )
