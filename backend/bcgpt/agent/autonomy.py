"""Pure autonomy-level resolution (no config/DB imports → unit-testable).

``config.py`` layers the system default on top of these helpers; everything
here works on a plain model dict / pydantic object and never touches the app.
"""

from __future__ import annotations

from typing import Any, Optional

from bcgpt.agent.types import AgentAutonomyLevel

# The model's meta JSON (ModelMeta, extra="allow") carries the per-agent
# autonomy level under this key — no DB migration required.
AUTONOMY_META_KEY = "autonomy_level"


def extract_meta(model: Any) -> dict:
    """Return the ``meta`` dict from a model regardless of its shape.

    Accepts a raw runtime model dict (which nests the persisted record under
    ``info``), a ``ModelModel`` / ``ModelMeta`` pydantic object, or a plain
    meta dict.
    """
    if model is None:
        return {}
    if isinstance(model, dict):
        info = model.get("info")
        if isinstance(info, dict) and isinstance(info.get("meta"), dict):
            return info["meta"]
        if isinstance(model.get("meta"), dict):
            return model["meta"]
        if AUTONOMY_META_KEY in model or "capabilities" in model:
            return model
        return {}
    meta = getattr(model, "meta", None)
    if meta is not None:
        if hasattr(meta, "model_dump"):
            return meta.model_dump()
        if isinstance(meta, dict):
            return meta
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return {}


def read_meta_autonomy(model: Any) -> Optional[str]:
    """Return the raw autonomy string from meta (or legacy capabilities), else None."""
    meta = extract_meta(model)
    value = meta.get(AUTONOMY_META_KEY)
    if value is None:
        caps = meta.get("capabilities")
        if isinstance(caps, dict):
            value = caps.get(AUTONOMY_META_KEY)
    return value


def resolve_autonomy_level(
    model: Any, default: AgentAutonomyLevel
) -> AgentAutonomyLevel:
    value = read_meta_autonomy(model)
    if value is None:
        return default
    return AgentAutonomyLevel.from_value(value)
