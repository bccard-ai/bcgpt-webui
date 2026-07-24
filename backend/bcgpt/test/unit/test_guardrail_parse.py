"""Unit tests for GuardrailScanner._parse_response — parsing untrusted LLM output.

The scanner itself is LLM-backed (not unit-testable), but `_parse_response` is a
pure function over the model's JSON reply: it handles raw + markdown-fenced JSON,
**fails OPEN** on unparseable output, and clamps confidence. `GuardrailScanner(None)`
constructs trivially (it only stores config, which `_parse_response` never reads).

    python -m pytest bcgpt/test/unit/test_guardrail_parse.py
"""

from bcgpt.utils.security import ThreatSeverity, ThreatType
from bcgpt.utils.security.guardrail_scanner import GuardrailScanner


def _parse(content: str):
    return GuardrailScanner(config=None)._parse_response(content)


def test_safe_json_is_safe():
    r = _parse('{"safe": true}')
    assert r.is_safe is True
    assert r.threats == []


def test_unsafe_high_confidence():
    r = _parse(
        '{"safe": false, "threat_type": "instruction_override", "confidence": 0.95}'
    )
    assert r.is_safe is False
    t = r.threats[0]
    assert t.pattern_name == "guardrail:instruction_override"
    assert t.threat_type == ThreatType.PROMPT_INJECTION
    assert t.severity == ThreatSeverity.HIGH


def test_unsafe_medium_confidence_and_default_threat_type():
    r = _parse('{"safe": false, "confidence": 0.5}')
    assert r.is_safe is False
    assert r.threats[0].severity == ThreatSeverity.MEDIUM
    assert r.threats[0].pattern_name == "guardrail:other"  # threat_type defaulted


def test_markdown_fenced_json_is_extracted():
    content = '```json\n{"safe": false, "threat_type": "role_playing", "confidence": 0.9}\n```'
    r = _parse(content)
    assert r.is_safe is False
    assert r.threats[0].pattern_name == "guardrail:role_playing"


def test_unparseable_output_fails_open():
    # SECURITY tradeoff (locked here): if the classifier reply can't be parsed, the
    # scanner fails OPEN (treats input as safe) rather than blocking legitimate traffic.
    assert _parse("not json at all {{{").is_safe is True
    assert _parse("").is_safe is True


def test_confidence_is_clamped_and_defaulted():
    assert _parse('{"safe": false, "confidence": 1.5}').threats[0].confidence == 1.0
    assert _parse('{"safe": false, "confidence": -2}').threats[0].confidence == 0.0
    assert _parse('{"safe": false, "confidence": "bad"}').threats[0].confidence == 0.5
