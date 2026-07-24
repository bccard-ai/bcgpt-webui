"""Model aggregation and access-control utilities for BCGPT WebUI.

Collects available LLM models from all configured providers (OpenAI,
Ollama, Gemini, Claude), merges them with custom model definitions
and arena models, resolves action bindings, and caches the result on
``app.state.MODELS``.

Public exports (re-exported via ``bcgpt.utils.__init__``):
    get_all_base_models, get_all_models, check_model_access
"""

from __future__ import annotations

import logging
import sys
import time

from fastapi import Request

from bcgpt.config import DEFAULT_ARENA_MODEL
from bcgpt.env import GLOBAL_LOG_LEVEL, SRC_LOG_LEVELS
from bcgpt.functions import get_function_models
from bcgpt.models import Functions, Models, UserModel
from bcgpt.providers.claude import ClaudeProvider
from bcgpt.providers.gemini import GeminiProvider
from bcgpt.routers import ollama, openai
from bcgpt.utils import has_access, load_function_module_by_id

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# ---------------------------------------------------------------------------
# Base model collection
# ---------------------------------------------------------------------------


async def get_all_base_models(
    request: Request, user: UserModel | None = None
) -> list[dict]:
    """Aggregate models from all enabled LLM providers.

    Queries each provider (OpenAI, Ollama, Gemini, Claude) and the
    function-model registry in parallel, returning a flat list of
    model descriptor dicts.

    Args:
        request: The incoming FastAPI request (used to access app state).
        user: The current user, passed through to provider query methods.

    Returns:
        A list of model descriptor dictionaries.
    """
    openai_models: list[dict] = []
    ollama_models: list[dict] = []
    gemini_models: list[dict] = []
    claude_models: list[dict] = []

    if request.app.state.config.ENABLE_OPENAI_API:
        openai_models = await openai.get_all_models(request, user=user)
        openai_models = openai_models["data"]

    if request.app.state.config.ENABLE_OLLAMA_API:
        try:
            raw = await ollama.get_all_models(request, user=user)
            ollama_models = [
                _normalise_ollama_model(m) for m in raw.get("models", [])
            ]
        except Exception as exc:
            log.warning("Failed to fetch Ollama models: %s", exc)

    if getattr(request.app.state.config, "ENABLE_GEMINI_API", False):
        try:
            gemini_models = await GeminiProvider(
                request.app.state.config
            ).get_models(request, user=user)
        except Exception:
            pass

    if getattr(request.app.state.config, "ENABLE_CLAUDE_API", False):
        try:
            claude_models = await ClaudeProvider(
                request.app.state.config
            ).get_models(request, user=user)
        except Exception:
            pass

    function_models = await get_function_models(request)

    return function_models + openai_models + ollama_models + gemini_models + claude_models


# ---------------------------------------------------------------------------
# Full model list (with arena + custom models + actions)
# ---------------------------------------------------------------------------


async def get_all_models(
    request: Request, user: UserModel | None = None
) -> list[dict]:
    """Build the complete model list for the requesting user.

    This is the main entry point called by the models API router.  It
    performs the following steps:

    1. Collects all base models via :func:`get_all_base_models`.
    2. Appends arena evaluation models when enabled.
    3. Merges custom model definitions (active overrides and presets).
    4. Resolves action function bindings.
    5. Caches the result on ``request.app.state.MODELS``.

    Args:
        request: The incoming FastAPI request.
        user: The current user (used for access filtering).

    Returns:
        A list of fully resolved model descriptor dictionaries.
    """
    models = await get_all_base_models(request, user=user)

    if not models:
        return []

    models = _append_arena_models(request, models)
    models = _merge_custom_models(models)

    global_action_ids = [
        fn.id for fn in Functions.get_global_action_functions()
    ]
    enabled_action_ids = [
        fn.id for fn in Functions.get_functions_by_type("action", active_only=True)
    ]

    _resolve_model_actions(request, models, global_action_ids, enabled_action_ids)

    log.debug("get_all_models() returned %d models", len(models))
    request.app.state.MODELS = {m["id"]: m for m in models}
    return models


# ---------------------------------------------------------------------------
# Model access check
# ---------------------------------------------------------------------------


def check_model_access(user: UserModel, model: dict) -> None:
    """Verify that *user* is allowed to read *model*.

    For arena models the access control is read from the model's metadata.
    For regular models the database record is consulted.

    Args:
        user: The user requesting access.
        model: A model descriptor dict (must contain ``"id"`` and
            optionally ``"arena"`` / ``"info"``).

    Raises:
        Exception: If the user does not have read access to the model.
    """
    if model.get("arena"):
        access_control = (
            model.get("info", {}).get("meta", {}).get("access_control", {})
        )
        if not has_access(user.id, type="read", access_control=access_control):
            raise Exception("Model not found")
        return

    model_info = Models.get_model_by_id(model.get("id"))
    if not model_info:
        raise Exception("Model not found")

    if user.id != model_info.user_id and not has_access(
        user.id, type="read", access_control=model_info.access_control
    ):
        raise Exception("Model not found")


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalise_ollama_model(model: dict) -> dict:
    """Convert a raw Ollama model dict to the standard descriptor format."""
    return {
        "id": model["model"],
        "name": model["name"],
        "object": "model",
        "created": int(time.time()),
        "owned_by": "ollama",
        "ollama": model,
        "tags": model.get("tags", []),
    }


def _append_arena_models(request: Request, models: list[dict]) -> list[dict]:
    """Append arena evaluation models when the feature is enabled."""
    if not request.app.state.config.ENABLE_EVALUATION_ARENA_MODELS:
        return models

    configured = request.app.state.config.EVALUATION_ARENA_MODELS
    if configured:
        arena_list = [
            _arena_descriptor(m) for m in configured
        ]
    else:
        arena_list = [_arena_descriptor(DEFAULT_ARENA_MODEL)]

    return models + arena_list


def _arena_descriptor(cfg: dict) -> dict:
    """Build a model descriptor dict from an arena configuration entry."""
    return {
        "id": cfg["id"],
        "name": cfg["name"],
        "info": {"meta": cfg["meta"]},
        "object": "model",
        "created": int(time.time()),
        "owned_by": "arena",
        "arena": True,
    }


def _merge_custom_models(models: list[dict]) -> list[dict]:
    """Overlay custom model definitions on top of the base model list.

    Active custom models with a ``base_model_id`` that matches an
    existing model override its name and info.  Custom models *without*
    a matching base are appended as presets.

    Models that are **not** active are removed from the list.
    """
    custom_models = Models.get_all_models()
    model_ids = {m["id"] for m in models}

    for custom in custom_models:
        if custom.base_model_id is None:
            # Attempt to match against an existing base model
            _apply_base_model_override(custom, models)
        elif custom.is_active and custom.id not in model_ids:
            models.append(_build_preset_model(custom, models))

    return models


def _apply_base_model_override(custom, models: list[dict]) -> None:
    """Override an existing base model's name/info with custom settings.

    If the custom model is inactive the matched base model is removed.
    """
    for model in models:
        if custom.id != model["id"] and custom.id != model["id"].split(":")[0]:
            continue

        if custom.is_active:
            model["name"] = custom.name
            model["info"] = custom.model_dump()
            action_ids: list[str] = []
            if "info" in model and "meta" in model["info"]:
                action_ids.extend(model["info"]["meta"].get("actionIds", []))
            model["action_ids"] = action_ids
        else:
            models.remove(model)
        return  # only the first match


def _build_preset_model(custom, models: list[dict]) -> dict:
    """Build a preset model descriptor from a custom model definition."""
    owned_by = "openai"
    pipe = None

    for model in models:
        if (
            custom.base_model_id == model["id"]
            or custom.base_model_id == model["id"].split(":")[0]
        ):
            owned_by = model.get("owned_by", "unknown owner")
            if "pipe" in model:
                pipe = model["pipe"]
            break

    action_ids: list[str] = []
    if custom.meta:
        meta = custom.meta.model_dump()
        if "actionIds" in meta:
            action_ids.extend(meta["actionIds"])

    return {
        "id": custom.id,
        "name": custom.name,
        "object": "model",
        "created": custom.created_at,
        "owned_by": owned_by,
        "info": custom.model_dump(),
        "preset": True,
        **({"pipe": pipe} if pipe is not None else {}),
        "action_ids": action_ids,
    }


def _resolve_model_actions(
    request: Request,
    models: list[dict],
    global_action_ids: list[str],
    enabled_action_ids: list[str],
) -> None:
    """Resolve action function bindings for every model in *models*."""
    for model in models:
        raw_action_ids = model.pop("action_ids", [])
        merged = list(set(raw_action_ids + global_action_ids))
        action_ids = [aid for aid in merged if aid in enabled_action_ids]

        model["actions"] = []
        for action_id in action_ids:
            action_fn = Functions.get_function_by_id(action_id)
            if action_fn is None:
                raise Exception(f"Action not found: {action_id}")

            module = _get_function_module(request, action_id)
            model["actions"].extend(
                _action_items_from_module(action_fn, module)
            )


def _get_function_module(request: Request, function_id: str):
    """Load and cache a function module in ``app.state.FUNCTIONS``."""
    cached = request.app.state.FUNCTIONS.get(function_id)
    if cached is not None:
        return cached

    module, _, _ = load_function_module_by_id(function_id)
    request.app.state.FUNCTIONS[function_id] = module
    return module


def _action_items_from_module(function, module) -> list[dict]:
    """Build action descriptor dicts from a function module.

    If the module exposes an ``actions`` list, each action is rendered
    separately.  Otherwise a single-item list is returned.
    """
    if hasattr(module, "actions"):
        return [
            {
                "id": f"{function.id}.{action['id']}",
                "name": action.get("name", f"{function.name} ({action['id']})"),
                "description": function.meta.description,
                "icon_url": action.get(
                    "icon_url",
                    function.meta.manifest.get("icon_url"),
                ),
            }
            for action in module.actions
        ]

    return [
        {
            "id": function.id,
            "name": function.name,
            "description": function.meta.description,
            "icon_url": function.meta.manifest.get("icon_url"),
        }
    ]
