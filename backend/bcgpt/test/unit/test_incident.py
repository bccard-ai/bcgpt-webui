"""Tests for AI-incident regulatory reporting deadlines (``compliance/models/incident.py``).

These pure helpers decide the breach/serious-incident reporting deadline for a detected
incident -- a wrong value or mapping means a missed regulatory filing (e.g. Korea PIPA's
72-hour breach-notification window) and potential fines. They are pure (dict lookup + ms
arithmetic), so exercised directly. The router/DB layer is not covered.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_incident.py -q
"""

from __future__ import annotations

from bcgpt.compliance.models.incident import (
    _MS_PER_SEC,
    _REGIME_DEADLINES,
    _SEC_PER_DAY,
    classify_reporting_regime,
    compute_reporting_deadline,
)

# ---------------------------------------------------------------------------
# classify_reporting_regime -- incident category -> reporting regime
# ---------------------------------------------------------------------------


def test_classify_known_categories():
    assert classify_reporting_regime("pii_leak") == "pipa_72h"
    assert classify_reporting_regime("credit_info_leak") == "credit_info_3d"
    assert classify_reporting_regime("critical_infra") == "eu_ai_act_2d"
    assert classify_reporting_regime("hallucination_harm") == "eu_ai_act_15d"
    assert classify_reporting_regime("prompt_injection") == "eu_ai_act_15d"
    assert classify_reporting_regime("bias") == "eu_ai_act_15d"
    assert classify_reporting_regime("model_drift") == "none"


def test_classify_unknown_and_none():
    assert classify_reporting_regime("something_new") == "none"
    assert classify_reporting_regime(None) == "none"
    assert classify_reporting_regime("") == "none"


# ---------------------------------------------------------------------------
# compute_reporting_deadline -- regime -> deadline (epoch ms)
# ---------------------------------------------------------------------------


def test_deadline_pipa_is_72_hours_after_detection():
    detected = 1_000_000
    deadline = compute_reporting_deadline("pipa_72h", detected)
    assert deadline == detected + 72 * 3600 * _MS_PER_SEC  # 72h in ms


def test_deadline_eu_ai_act_values():
    detected = 5_000_000
    assert (
        compute_reporting_deadline("eu_ai_act_2d", detected)
        == detected + 2 * _SEC_PER_DAY * _MS_PER_SEC
    )
    assert (
        compute_reporting_deadline("eu_ai_act_15d", detected)
        == detected + 15 * _SEC_PER_DAY * _MS_PER_SEC
    )


def test_deadline_credit_info_3_days():
    detected = 0
    assert (
        compute_reporting_deadline("credit_info_3d", detected)
        == 3 * _SEC_PER_DAY * _MS_PER_SEC
    )


def test_no_deadline_for_unknown_or_zero_regimes():
    assert compute_reporting_deadline("gdpr_unknown", 1000) is None
    assert compute_reporting_deadline("ai_basic_act", 1000) is None  # explicitly 0
    assert compute_reporting_deadline("none", 1000) is None


def test_all_regime_deadlines_are_positive_or_zero():
    # Every defined regime must have a non-negative deadline; the no-deadline regimes
    # are exactly 0 (so compute_reporting_deadline returns None for them).
    for regime, seconds in _REGIME_DEADLINES.items():
        assert seconds >= 0, regime
