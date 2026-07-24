"""Tests for security-scanner TTFT hardening.

These guard the changes that stop the security pipeline from inflating
time-to-first-token: ``skip_llm`` now suppresses *every* LLM-based scanner
(LLM scanner, guardrail, and PII verification), the two input LLM scanners run
concurrently and fail open, the multi-turn scan is capped to the most recent
user turns, and LLM scan calls are bounded by a configurable timeout.
"""

import asyncio
from types import SimpleNamespace

from bcgpt.utils.security import (
    ScanResult,
    SecurityPipeline,
    ThreatMatch,
    ThreatSeverity,
    ThreatType,
    scanner_timeout,
)


def _cfg(**over):
    base = dict(
        SECURITY_PROMPT_INJECTION_ENABLED=False,
        SECURITY_JAILBREAK_ENABLED=False,
        SECURITY_PII_ENABLED=False,
        SECURITY_TOXICITY_ENABLED=False,
        SECURITY_TOXICITY_CUSTOM_WORD_LIST="",
        SECURITY_SECRETS_ENABLED=False,
        SECURITY_LLM_SCANNER_ENABLED=True,
        SECURITY_GUARDRAIL_ENABLED=True,
        SECURITY_CONFIDENCE_THRESHOLD=0.0,
        SECURITY_LOG_DETECTIONS=False,
        SECURITY_CONVERSATION_THRESHOLD=2.0,
        SECURITY_CONVERSATION_MAX_MESSAGES=10,
        SECURITY_OUTPUT_FILTER_ENABLED=False,
    )
    base.update(over)
    return SimpleNamespace(**base)


class _Recorder:
    """Async stub that records call count + first positional arg."""

    def __init__(self, result=None, exc=None):
        self.calls = 0
        self.args = []
        self._result = result
        self._exc = exc

    async def __call__(self, *a, **k):
        self.calls += 1
        if a:
            self.args.append(a[0])
        if self._exc is not None:
            raise self._exc
        return self._result


def test_skip_llm_suppresses_all_llm_scanners():
    p = SecurityPipeline(_cfg())
    llm = _Recorder(result=ScanResult(is_safe=True))
    gr = _Recorder(result=ScanResult(is_safe=True))
    p._llm_scanner.scan_input = llm
    p._guardrail.scan = gr

    # skip_llm=True (used by conversation scan + shadow critical path): no LLM calls.
    asyncio.run(p.scan_input("hello", {}, request=object(), skip_llm=True))
    assert llm.calls == 0 and gr.calls == 0

    # skip_llm=False: both LLM scanners invoked.
    asyncio.run(p.scan_input("hello", {}, request=object(), skip_llm=False))
    assert llm.calls == 1 and gr.calls == 1


def test_input_llm_scanners_fail_open_independently():
    """If one LLM scanner raises, the other's findings still count; no raise."""
    p = SecurityPipeline(_cfg())
    p._llm_scanner.scan_input = _Recorder(exc=RuntimeError("boom"))
    threat = ThreatMatch(
        threat_type=ThreatType.LLM_DETECTION,
        pattern_name="guardrail:test",
        matched_text="",
        confidence=1.0,
        severity=ThreatSeverity.HIGH,
    )
    p._guardrail.scan = _Recorder(result=ScanResult(is_safe=False, threats=[threat]))

    res = asyncio.run(p.scan_input("hello", {}, request=object(), skip_llm=False))
    assert any(t.pattern_name == "guardrail:test" for t in res.threats)


def test_conversation_scan_capped_to_recent_user_turns():
    p = SecurityPipeline(_cfg(SECURITY_CONVERSATION_MAX_MESSAGES=2))
    rec = _Recorder(result=ScanResult(is_safe=True))
    p.scan_input = rec  # spy on per-message scans

    msgs = [{"role": "user", "content": f"m{i}"} for i in range(5)]
    asyncio.run(p.scan_conversation(msgs, {}, request=object()))

    # Only the last 2 user turns are inspected.
    assert rec.calls == 2
    assert rec.args == ["m3", "m4"]


def test_scanner_timeout_resolution():
    # explicit positive value honored
    assert scanner_timeout(SimpleNamespace(SECURITY_SCANNER_TIMEOUT=3)) == 3.0
    # missing / blank / invalid -> positive default
    assert scanner_timeout(SimpleNamespace()) > 0
    assert scanner_timeout(SimpleNamespace(SECURITY_SCANNER_TIMEOUT="")) > 0
    assert scanner_timeout(SimpleNamespace(SECURITY_SCANNER_TIMEOUT="bad")) > 0
    # non-positive -> default, never <= 0
    assert scanner_timeout(SimpleNamespace(SECURITY_SCANNER_TIMEOUT=0)) > 0
