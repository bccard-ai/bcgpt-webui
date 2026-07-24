"""Unit tests for the model-capability helper (P0.5)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.agent.capabilities import model_capability_enabled


def _model(caps=None, meta=None):
    """Lightweight stand-in for a persisted Model with a pydantic-ish meta."""
    if meta is None:
        meta = {"capabilities": caps or {}}
    # support both dict meta and an object with model_dump()
    return SimpleNamespace(id="m1", meta=meta)


def test_capability_true_when_declared():
    assert model_capability_enabled(_model({"web_search": True}), "web_search") is True


def test_capability_false_when_absent():
    assert model_capability_enabled(_model({}), "web_search") is False


def test_capability_false_when_capabilities_missing():
    assert model_capability_enabled(_model(None), "web_search") is False
    # meta without capabilities key at all
    assert (
        model_capability_enabled(
            SimpleNamespace(meta={"description": "x"}), "hybrid_search"
        )
        is False
    )


def test_capability_resilient_when_no_meta():
    assert model_capability_enabled(SimpleNamespace(meta=None), "web_search") is False
    assert model_capability_enabled(SimpleNamespace(), "web_search") is False


def test_capability_truthiness():
    # falsy values are False
    assert model_capability_enabled(_model({"web_search": 0}), "web_search") is False
    assert model_capability_enabled(_model({"web_search": ""}), "web_search") is False
    # truthy non-bool counts as enabled
    assert model_capability_enabled(_model({"web_search": 1}), "web_search") is True
