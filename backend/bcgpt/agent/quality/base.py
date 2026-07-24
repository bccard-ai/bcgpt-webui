"""Shared helper: ask an LLM for strict JSON and parse it robustly."""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from bcgpt.agent.llm import extract_content, llm_complete

log = logging.getLogger(__name__)


def parse_json(text: str) -> Any:
    """Extract the first JSON value from a (possibly fenced) LLM response."""
    if not text:
        return None
    # strip code fences
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```", 2)
        stripped = stripped[1] if len(stripped) > 1 else text
        if stripped.lstrip().startswith("json"):
            stripped = stripped.lstrip()[4:]
    try:
        return json.loads(stripped.strip())
    except json.JSONDecodeError:
        pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


async def judge_json(
    request: Any,
    user: Any,
    model_id: str,
    system: str,
    prompt: str,
    *,
    params: Optional[dict] = None,
) -> Any:
    """Run a JSON-only LLM judgment. Returns parsed JSON or ``None`` on failure."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]
    merged = {"temperature": 0, **(params or {})}
    try:
        resp = await llm_complete(request, user, model_id, messages, params=merged)
        return parse_json(extract_content(resp))
    except Exception as e:  # noqa: BLE001 - quality must never break the response
        log.warning("quality judge_json failed: %s", e)
        return None
