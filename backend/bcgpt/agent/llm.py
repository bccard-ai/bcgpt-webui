"""Thin async helpers for invoking an LLM through BCGPT's existing stack.

All agent components (workflow LLM node, ReAct tool loop, quality pipeline,
multi-agent executors) funnel through :func:`llm_complete`, which wraps
``bcgpt.utils.chat.generate_chat_completion`` in non-streaming mode and returns
the OpenAI-compatible response dict. Imports are lazy to avoid import cycles and
to keep the pure engine modules importable without the whole app.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

log = logging.getLogger(__name__)


async def llm_complete(
    request: Any,
    user: Any,
    model_id: str,
    messages: list[dict],
    *,
    params: Optional[dict] = None,
    tools: Optional[list[dict]] = None,
    bypass_filter: bool = True,
    extra: Optional[dict] = None,
) -> dict:
    """Run a single non-streaming chat completion. Returns the OpenAI dict.

    ``request`` must be a FastAPI Request whose ``app.state.MODELS`` contains
    ``model_id`` (always true when invoked from a request handler). ``params``
    carries sampling settings (temperature, max_tokens, ...). ``tools`` is
    forwarded for forward-compatibility with native function calling; current
    providers ignore it, so the ReAct loop also uses a prompt protocol.
    """
    if request is None or model_id is None:
        raise RuntimeError("llm_complete requires a request and model_id")

    from bcgpt.utils.chat import generate_chat_completion

    form_data: dict = {
        "model": model_id,
        "messages": messages,
        "stream": False,
    }
    if params:
        form_data["params"] = params
    if tools:
        form_data["tools"] = tools
    if extra:
        form_data.update(extra)

    resp = await generate_chat_completion(
        request, form_data, user, bypass_filter=bypass_filter
    )
    # We requested stream=False, so providers return a dict. Guard anyway.
    if not isinstance(resp, dict):
        raise RuntimeError("Expected a non-streaming completion dict")
    return resp


def extract_message(resp: dict) -> dict:
    try:
        return resp["choices"][0]["message"] or {}
    except (KeyError, IndexError, TypeError):
        return {}


def extract_content(resp: dict) -> str:
    msg = extract_message(resp)
    content = msg.get("content")
    return content if isinstance(content, str) else ""
