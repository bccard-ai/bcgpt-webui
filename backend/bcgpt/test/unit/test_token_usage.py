"""Unit tests for the token/cost FinOps model (open-moai adoption 2.1).

The DB-backed persistence (``insert_usage`` / aggregations) and the ``usage``
router import chain run migrations on import and are not exercised here; these
tests lock the two security/correctness-relevant *pure-ish* pieces:

  * ``_normalize_token_counts`` -- the 2026-06-22 hardening that clamps provider
    token counts to non-negative ints, so a malformed response cannot corrupt
    cost/usage aggregates (the budget limiter already guards its own counter).
  * ``ModelPricings.compute_cost`` -- the USD cost formula with 6-dp rounding
    and the "unpriced model -> 0.0" invariant (never a wrong non-zero estimate).

``compute_cost`` is tested with ``get_pricing`` monkeypatched, so no DB is
needed. The admin-only ``usage`` router (IDOR-clean -- every endpoint is
``get_admin_user``-gated) was verified by review.

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_token_usage.py -q
"""

from __future__ import annotations

import pytest

from bcgpt.models.token_usage import ModelPricings, _normalize_token_counts
from bcgpt.models.token_usage import ModelPricingModel

# ---------------------------------------------------------------------------
# _normalize_token_counts -- non-negative coercion (the hardening fix)
# ---------------------------------------------------------------------------


def test_normalize_none_to_zero():
    assert _normalize_token_counts(None, None) == (0, 0)


def test_normalize_negative_clamped_to_zero():
    assert _normalize_token_counts(-5, -10) == (0, 0)


def test_normalize_valid_passthrough():
    assert _normalize_token_counts(100, 200) == (100, 200)


def test_normalize_mixed_negative_and_valid():
    assert _normalize_token_counts(-5, 100) == (0, 100)


def test_normalize_float_truncated_to_int():
    assert _normalize_token_counts(5.9, 3.1) == (5, 3)


def test_normalize_zero_is_zero():
    assert _normalize_token_counts(0, 0) == (0, 0)


def test_normalize_non_numeric_to_zero():
    # A non-numeric value must not raise; it maps to 0 (the other field intact).
    assert _normalize_token_counts("not-a-number", 50) == (0, 50)


def test_normalize_numeric_string_coerced():
    assert _normalize_token_counts("100", 50) == (100, 50)


# ---------------------------------------------------------------------------
# ModelPricings.compute_cost -- cost formula (get_pricing monkeypatched)
# ---------------------------------------------------------------------------


def _pricing(inp: float, out: float) -> ModelPricingModel:
    return ModelPricingModel(
        model="x", input_per_1k=inp, output_per_1k=out, updated_at=0
    )


def test_compute_cost_basic(monkeypatch):
    # 1000 prompt @ 0.0025 + 500 completion @ 0.01 = 0.0025 + 0.005 = 0.0075
    monkeypatch.setattr(
        ModelPricings, "get_pricing", lambda model: _pricing(0.0025, 0.01)
    )
    assert ModelPricings.compute_cost("x", 1000, 500) == 0.0075


def test_compute_cost_unpriced_is_zero(monkeypatch):
    """An unpriced model must never produce a wrong non-zero estimate."""
    monkeypatch.setattr(ModelPricings, "get_pricing", lambda model: None)
    assert ModelPricings.compute_cost("mystery-model", 9999, 9999) == 0.0


def test_compute_cost_rounding_to_six_dp(monkeypatch):
    monkeypatch.setattr(
        ModelPricings, "get_pricing", lambda model: _pricing(0.0001, 0.0)
    )
    # 1234/1000 * 0.0001 = 0.0001234 -> round to 6 dp -> 0.000123
    assert ModelPricings.compute_cost("x", 1234, 0) == 0.000123


def test_compute_cost_zero_tokens(monkeypatch):
    monkeypatch.setattr(
        ModelPricings, "get_pricing", lambda model: _pricing(0.0025, 0.01)
    )
    assert ModelPricings.compute_cost("x", 0, 0) == 0.0


def test_compute_cost_empty_model_is_zero(monkeypatch):
    """get_pricing('') returns None (no model) -> cost 0.0, no error."""
    monkeypatch.setattr(ModelPricings, "get_pricing", lambda model: None)
    assert ModelPricings.compute_cost("", 100, 100) == 0.0
