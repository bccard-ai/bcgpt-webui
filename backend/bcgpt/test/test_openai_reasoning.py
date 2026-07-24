"""Unit tests for the OpenAI reasoning-model adapter.

These are pure-function tests (no DB / network) covering detection and the
payload transform for the o-series and GPT-5 families.
"""

import importlib.util
import os

import pytest

# Load the module directly from its file so the test does not depend on the
# full `bcgpt` package (and its backend dependencies) being importable.
_MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "utils", "openai_reasoning.py"
)
_spec = importlib.util.spec_from_file_location("_openai_reasoning", _MODULE_PATH)
oai = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(oai)


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "model_id",
    [
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        "o3-2025-04-16",
        "o4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-2025-08-07",
        "openai/o3",
        "azure/gpt-5-mini",
    ],
)
def test_is_reasoning_model_true(model_id):
    assert oai.is_reasoning_model(model_id) is True


@pytest.mark.parametrize(
    "model_id",
    [
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4.1",
        "gpt-5-chat",
        "gpt-5-chat-latest",  # non-reasoning chat variant
        "omni-moderation-latest",
        "openchat",
        "chatgpt-4o-latest",
        "",
        None,
    ],
)
def test_is_reasoning_model_false(model_id):
    assert oai.is_reasoning_model(model_id) is False


def test_family_classification():
    assert oai.is_gpt5("gpt-5-mini") is True
    assert oai.is_gpt5("o3") is False
    assert oai.is_o_series("o4-mini") is True
    assert oai.is_o_series("gpt-5") is False
    assert oai.is_o1_legacy("o1-preview") is True
    assert oai.is_o1_legacy("o1") is False
    assert oai.is_o1_legacy("o3-mini") is False


# --------------------------------------------------------------------------- #
# Transform
# --------------------------------------------------------------------------- #


def _base_payload(model):
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": "be helpful"},
            {"role": "user", "content": "hi"},
        ],
        "temperature": 0.7,
        "top_p": 0.9,
        "frequency_penalty": 0.5,
        "presence_penalty": 0.3,
        "logit_bias": {"123": 1},
        "logprobs": True,
        "top_logprobs": 3,
        "max_tokens": 256,
        "stream": True,
    }


def test_strips_unsupported_params_and_renames_max_tokens():
    out = oai.transform_reasoning_payload(_base_payload("gpt-5"))
    for k in (
        "temperature",
        "top_p",
        "frequency_penalty",
        "presence_penalty",
        "logit_bias",
        "logprobs",
        "top_logprobs",
        "max_tokens",
    ):
        assert k not in out, f"{k} should have been stripped"
    assert out["max_completion_tokens"] == 256
    assert out["stream"] is True  # unrelated params preserved


def test_system_role_becomes_developer_for_o3_and_gpt5():
    for model in ("o3", "o3-mini", "o4-mini", "gpt-5", "gpt-5-mini"):
        out = oai.transform_reasoning_payload(_base_payload(model))
        assert out["messages"][0]["role"] == "developer", model


def test_system_role_becomes_user_for_legacy_o1():
    for model in ("o1-mini", "o1-preview"):
        out = oai.transform_reasoning_payload(_base_payload(model))
        assert out["messages"][0]["role"] == "user", model


@pytest.mark.parametrize("model", ["o1-mini", "o3", "o4-mini", "gpt-5", "gpt-5-mini"])
def test_stop_n_and_parallel_tool_calls_stripped_for_all(model):
    out = oai.transform_reasoning_payload(
        {
            "model": model,
            "messages": [],
            "stop": ["\n"],
            "n": 2,
            "parallel_tool_calls": True,
        }
    )
    assert "stop" not in out
    assert "n" not in out
    assert "parallel_tool_calls" not in out


def test_legacy_o1_drops_reasoning_effort():
    out = oai.transform_reasoning_payload(
        {"model": "o1-mini", "messages": [], "reasoning_effort": "high"}
    )
    assert "reasoning_effort" not in out


def test_reasoning_effort_normalization():
    # minimal is valid for gpt-5
    out = oai.transform_reasoning_payload(
        {"model": "gpt-5", "messages": [], "reasoning_effort": "minimal"}
    )
    assert out["reasoning_effort"] == "minimal"

    # none/xhigh are valid for the gpt-5 family (5.1+, codex-max)
    assert (
        oai.transform_reasoning_payload(
            {"model": "gpt-5", "messages": [], "reasoning_effort": "NONE"}
        )["reasoning_effort"]
        == "none"
    )

    # minimal degrades to low for the o-series
    out = oai.transform_reasoning_payload(
        {"model": "o3", "messages": [], "reasoning_effort": "MINIMAL"}
    )
    assert out["reasoning_effort"] == "low"

    # garbage falls back to the default
    out = oai.transform_reasoning_payload(
        {"model": "o3", "messages": [], "reasoning_effort": "ludicrous"}
    )
    assert out["reasoning_effort"] == "medium"


def test_verbosity_kept_only_for_gpt5():
    g = oai.transform_reasoning_payload(
        {"model": "gpt-5", "messages": [], "verbosity": "HIGH"}
    )
    assert g["verbosity"] == "high"

    o = oai.transform_reasoning_payload(
        {"model": "o3", "messages": [], "verbosity": "high"}
    )
    assert "verbosity" not in o


def test_verbosity_stripped_from_non_reasoning_models():
    """Regression: verbosity must never leak to non-GPT-5 models (would 400)."""
    for model in ("gpt-4o", "gpt-4o-mini", "gpt-5-chat", "o4-mini"):
        out = oai.transform_reasoning_payload(
            {"model": model, "messages": [], "verbosity": "low"}
        )
        assert "verbosity" not in out, model


@pytest.mark.parametrize(
    "model,expected",
    [
        ("gpt-5.1", True),
        ("gpt-5-codex", True),
        ("gpt-5-pro", True),
        ("gpt-5-chat-latest", False),
        ("gpt-5.1-chat", False),
    ],
)
def test_extended_gpt5_family_detection(model, expected):
    assert oai.is_reasoning_model(model) is expected


def test_noop_for_non_reasoning_model():
    payload = _base_payload("gpt-4o")
    out = oai.transform_reasoning_payload(payload)
    assert out["temperature"] == 0.7
    assert out["max_tokens"] == 256
    assert "max_completion_tokens" not in out
    assert out["messages"][0]["role"] == "system"


def test_idempotent():
    once = oai.transform_reasoning_payload(_base_payload("gpt-5-mini"))
    twice = oai.transform_reasoning_payload(dict(once))
    assert once == twice


def test_existing_max_completion_tokens_wins():
    out = oai.transform_reasoning_payload(
        {
            "model": "o3",
            "messages": [],
            "max_tokens": 100,
            "max_completion_tokens": 500,
        }
    )
    assert out["max_completion_tokens"] == 500
    assert "max_tokens" not in out
