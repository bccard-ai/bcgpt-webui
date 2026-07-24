"""
OpenAI Reasoning Model Adapter
==============================

The GPT-5 family (``gpt-5``, ``gpt-5-mini``, ``gpt-5-nano``) and the o-series
(``o1``, ``o3``, ``o4-mini`` …) are *reasoning* models. They do **not** accept
several parameters that a classic GPT-4o Chat Completions payload includes
(``temperature``, ``top_p``, the penalties, ``logit_bias``/``logprobs``,
``max_tokens`` …). Sending those fields makes the API answer with **HTTP 400
``unsupported_parameter`` / ``unsupported_value``** errors.

This module is the single boundary that rewrites an OpenAI-style chat
completions payload so it is accepted by these models. It is intentionally
endpoint-agnostic: a caller hands it an OpenAI ``form_data``/``payload`` dict
and gets a transformed dict back. It is *in-place safe* and *idempotent* —
running it twice yields the same result, and it is a no-op for non-reasoning
models.

What it does for a detected reasoning model:

* ``max_tokens``                  → ``max_completion_tokens``
* strips unsupported sampling/penalty params
  (``temperature``, ``top_p``, ``frequency_penalty``, ``presence_penalty``,
  ``logit_bias``, ``logprobs``, ``top_logprobs``)
* strips the other reasoning-model rejects (``n``, ``stop``,
  ``parallel_tool_calls``) so the server applies its own default
* normalises ``reasoning_effort`` to a value the family supports
  (o-series: ``low|medium|high``; GPT-5: ``minimal|none|low|medium|high|xhigh``)
  and removes it entirely for the legacy ``o1-mini`` / ``o1-preview`` models
* keeps ``verbosity`` only for GPT-5 and clamps it to ``low|medium|high``
* rewrites the ``system`` role to ``developer`` — or to ``user`` for the
  legacy ``o1-mini`` / ``o1-preview`` models which reject both ``system`` and
  ``developer`` roles

Public API
----------
``is_reasoning_model(model_id)``      → bool
``is_gpt5(model_id)`` / ``is_o_series(model_id)``
``transform_reasoning_payload(payload)`` → dict (the main entry point)
"""

import logging
import re
from typing import Iterable, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Parameter support matrix
# ---------------------------------------------------------------------------

#: Sampling / penalty parameters that reasoning models reject. They are only
#: accepted at their default value (e.g. ``temperature=1``); rather than guess
#: the default we simply drop them so the server applies its own default.
UNSUPPORTED_SAMPLING_PARAMS: tuple[str, ...] = (
    "temperature",
    "top_p",
    "frequency_penalty",
    "presence_penalty",
    "logit_bias",
    "logprobs",
    "top_logprobs",
)

#: Other Chat Completions fields the current o-series / GPT-5 reasoning models
#: reject (o3 / o4-mini explicitly reject ``stop`` and ``n>1``; reasoning
#: models only do ``n=1`` and ignore client-side ``parallel_tool_calls``).
#: Dropping them is safe — the server falls back to its own default.
UNSUPPORTED_REASONING_PARAMS: tuple[str, ...] = (
    "n",
    "stop",
    "parallel_tool_calls",
)

#: ``reasoning_effort`` values accepted by the o-series.
REASONING_EFFORTS_O_SERIES: tuple[str, ...] = ("low", "medium", "high")
#: GPT-5 family across snapshots: ``minimal`` (gpt-5 gen-1), ``none`` (gpt-5.1+),
#: ``xhigh`` (codex-max) plus the common low/medium/high.
REASONING_EFFORTS_GPT5: tuple[str, ...] = (
    "minimal",
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
)
#: ``verbosity`` values (GPT-5 only).
VALID_VERBOSITY: tuple[str, ...] = ("low", "medium", "high")

_DEFAULT_EFFORT = "medium"
_DEFAULT_VERBOSITY = "medium"

# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

# o-series reasoning models: o1, o1-mini, o1-preview, o3, o3-mini, o4-mini, …
# Matches an ``o`` immediately followed by a digit (so it never matches names
# such as "omni" or "openchat").
_O_SERIES_RE = re.compile(r"^o\d")
# Legacy o1 models that reject the system/developer role entirely.
_O1_LEGACY_RE = re.compile(r"^o1-(mini|preview)")


def _normalize_model_id(model_id: Optional[str]) -> str:
    """Lower-case the id and drop any provider routing prefix.

    Handles ids such as ``openai/o3`` or ``azure/gpt-5`` (OpenRouter / proxies)
    by keeping only the segment after the last ``/``.
    """
    if not model_id:
        return ""
    mid = str(model_id).strip().lower()
    if "/" in mid:
        mid = mid.rsplit("/", 1)[-1]
    return mid


def is_gpt5(model_id: Optional[str]) -> bool:
    """True for GPT-5 *reasoning* models.

    ``gpt-5-chat`` / ``gpt-5-chat-latest`` are the non-reasoning chat variants
    (they accept temperature etc.) and are intentionally excluded.
    """
    mid = _normalize_model_id(model_id)
    if not mid.startswith("gpt-5"):
        return False
    # The chat variants (gpt-5-chat, gpt-5-chat-latest, gpt-5.1-chat, …) are
    # NON-reasoning models — they accept temperature etc. and reject
    # reasoning_effort/verbosity, so they must NOT be treated as reasoning.
    if "chat" in mid:
        return False
    return True


def is_o_series(model_id: Optional[str]) -> bool:
    """True for o-series reasoning models (o1/o3/o4/…)."""
    return bool(_O_SERIES_RE.match(_normalize_model_id(model_id)))


def is_o1_legacy(model_id: Optional[str]) -> bool:
    """True for the legacy ``o1-mini`` / ``o1-preview`` models."""
    return bool(_O1_LEGACY_RE.match(_normalize_model_id(model_id)))


def is_reasoning_model(model_id: Optional[str]) -> bool:
    """Whether *model_id* needs the reasoning-model payload transform."""
    return is_o_series(model_id) or is_gpt5(model_id)


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------


def _normalize_effort(value, gpt5: bool) -> str:
    effort = str(value).strip().lower()
    if gpt5:
        return effort if effort in REASONING_EFFORTS_GPT5 else _DEFAULT_EFFORT
    # o-series: only low/medium/high. ``minimal``/``none`` degrade to ``low``.
    if effort in REASONING_EFFORTS_O_SERIES:
        return effort
    if effort in ("minimal", "none"):
        return "low"
    return _DEFAULT_EFFORT


def _rewrite_system_role(messages: Iterable[dict], role: str) -> None:
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "system":
            msg["role"] = role


def transform_reasoning_payload(payload: dict) -> dict:
    """Rewrite an OpenAI chat-completions *payload* for a reasoning model.

    Mutates and returns *payload*. No-op when the model is not a reasoning
    model, and idempotent when it is.
    """
    if not isinstance(payload, dict):
        return payload

    model_id = payload.get("model", "")
    gpt5 = is_gpt5(model_id)

    # `verbosity` is a GPT-5-only Chat Completions field. Strip it from every
    # non-GPT-5 model (plain gpt-4o, the o-series, …) so it can never trigger an
    # `unsupported_parameter` 400. For GPT-5 it is clamped further down. This
    # runs before the early-return so it also protects non-reasoning models.
    if not gpt5:
        payload.pop("verbosity", None)

    if not is_reasoning_model(model_id):
        return payload

    legacy = is_o1_legacy(model_id)

    # 1. max_tokens → max_completion_tokens (keep an explicit one if present)
    if "max_tokens" in payload:
        payload.setdefault("max_completion_tokens", payload["max_tokens"])
        del payload["max_tokens"]

    # 2. drop unsupported sampling/penalty params and the other reasoning-model
    #    rejects (n / stop / parallel_tool_calls). Omitting them lets the server
    #    apply its own default instead of returning HTTP 400.
    for key in UNSUPPORTED_SAMPLING_PARAMS:
        payload.pop(key, None)
    for key in UNSUPPORTED_REASONING_PARAMS:
        payload.pop(key, None)

    # 3. reasoning_effort: legacy o1 rejects it outright; otherwise normalize to
    #    a value the family accepts.
    if legacy:
        payload.pop("reasoning_effort", None)
    elif payload.get("reasoning_effort") is not None:
        payload["reasoning_effort"] = _normalize_effort(
            payload["reasoning_effort"], gpt5
        )

    # 5. verbosity (GPT-5 only) — clamp to a value the API accepts.
    #    (Non-GPT-5 models already had it stripped above.)
    if gpt5 and "verbosity" in payload:
        v = str(payload["verbosity"]).strip().lower()
        payload["verbosity"] = v if v in VALID_VERBOSITY else _DEFAULT_VERBOSITY

    # 6. system role → developer (or user for legacy o1)
    messages = payload.get("messages")
    if isinstance(messages, list) and messages:
        _rewrite_system_role(messages, "user" if legacy else "developer")

    log.debug(
        "transform_reasoning_payload: model=%s gpt5=%s legacy=%s -> keys=%s",
        model_id,
        gpt5,
        legacy,
        sorted(payload.keys()),
    )
    return payload
