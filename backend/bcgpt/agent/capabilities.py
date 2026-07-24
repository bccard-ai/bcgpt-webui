"""Model capability helpers for the agent subsystem.

Centralises reads of ``model.meta.capabilities`` so the workflow generator,
tool-loop executors, and any future server-side check agree on what a model
declares (e.g. ``web_search``, ``hybrid_search``).

Layering note: the live chat path in ``utils/middleware.py`` consumes
request-level ``features.web_search`` rather than reading the model capability
directly. That feature flag is assembled client-side (see ``Chat.svelte``) from
this same capability OR-ed with the user's web-search preference, so forcing a
server-side model-capability AND on the chat path would regress the user's
ability to toggle web search on a model that does not declare it. The helper
below is therefore the canonical *model-declared* capability reader; the chat
path's ``features`` layer is intentionally separate.
"""

from __future__ import annotations

from typing import Any


def _meta_dict(model: Any) -> dict:
    meta = getattr(model, "meta", None)
    if meta is None:
        return {}
    return meta.model_dump() if hasattr(meta, "model_dump") else dict(meta)


def model_capability_enabled(model: Any, capability: str) -> bool:
    """Return whether *model* declares *capability* enabled in ``meta.capabilities``."""
    caps = _meta_dict(model).get("capabilities") or {}
    return bool(caps.get(capability))
