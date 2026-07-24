"""
BCGPT Task Generation Router
=============================

Handles auxiliary LLM-powered tasks such as title generation, tagging,
query expansion, autocompletion, emoji selection, image-prompt processing,
Mixture-of-Agents synthesis, context compression, and smart-query refinement.

All endpoints delegate to :func:`bcgpt.utils.generate_chat_completion` after
building a single-user-message payload from a configurable prompt template.

Public endpoints (unchanged from prior version):
    GET  /config
    POST /config/update
    POST /title/completions
    POST /tags/completions
    POST /image_prompt/completions
    POST /image_prompt/translate
    POST /image_prompt/expand
    POST /queries/completions
    POST /auto/completions
    POST /emoji/completions
    POST /moa/completions
    POST /context/compression/completions
    POST /smart-query/completions
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from bcgpt.config import (
    DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_CONTEXT_COMPRESSION_PROMPT_TEMPLATE,
    DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_EXPANSION_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_IMAGE_PROMPT_TRANSLATION_TEMPLATE,
    DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_SMART_QUERY_PROMPT_TEMPLATE,
    DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE,
    DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
)
from bcgpt.constants import TASKS
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.routers import process_pipeline_inlet_filter
from bcgpt.utils import generate_chat_completion, get_admin_user, get_verified_user
from bcgpt.utils import get_task_model_id
from bcgpt.utils.task import (
    autocomplete_generation_template,
    context_compression_template,
    emoji_generation_template,
    image_prompt_expansion_template,
    image_prompt_generation_template,
    image_prompt_translation_template,
    moa_response_generation_template,
    query_generation_template,
    smart_query_template,
    tags_generation_template,
    title_generation_template,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()

# ---------------------------------------------------------------------------
# Regex for stripping reasoning <details> blocks from message content
# ---------------------------------------------------------------------------

_REASONING_DETAIL_RE = re.compile(
    r'<details\s+type="reasoning"[^>]*>.*?</details>',
    re.DOTALL,
)

# ---------------------------------------------------------------------------
# Config field list — used by both GET /config and POST /config/update
# ---------------------------------------------------------------------------

_CONFIG_FIELDS: tuple[str, ...] = (
    "TASK_MODEL",
    "TASK_MODEL_EXTERNAL",
    "TITLE_GENERATION_PROMPT_TEMPLATE",
    "IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE",
    "ENABLE_AUTOCOMPLETE_GENERATION",
    "AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH",
    "TAGS_GENERATION_PROMPT_TEMPLATE",
    "ENABLE_TAGS_GENERATION",
    "ENABLE_TITLE_GENERATION",
    "ENABLE_SEARCH_QUERY_GENERATION",
    "ENABLE_RETRIEVAL_QUERY_GENERATION",
    "QUERY_GENERATION_PROMPT_TEMPLATE",
    "TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE",
    "ENABLE_CONTEXT_COMPRESSION",
    "CONTEXT_COMPRESSION_MODEL",
    "CONTEXT_COMPRESSION_PROMPT_TEMPLATE",
    "ENABLE_SMART_QUERY",
    "SMART_QUERY_MODEL",
    "SMART_QUERY_PROMPT_TEMPLATE",
)


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _read_config(request: Request) -> dict[str, Any]:
    """Return a dict of all task-related config fields from app state."""
    cfg = request.app.state.config
    return {field: getattr(cfg, field) for field in _CONFIG_FIELDS}


def _user_context(user: Any, *, include_location: bool = False) -> dict[str, Any]:
    """Build a user-info dict suitable for prompt template substitution."""
    ctx: dict[str, Any] = {"name": user.name}
    if include_location:
        ctx["location"] = user.info.get("location") if user.info else None
    return ctx


def _resolve_models(request: Request) -> dict[str, Any]:
    """Return the model map, preferring the direct-request override if set."""
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        return {request.state.model["id"]: request.state.model}
    return request.app.state.MODELS


def _resolve_task_model(
    request: Request,
    model_id: str,
    models: dict[str, Any],
) -> str:
    """Validate *model_id* exists and return the effective task model id."""
    if model_id not in models:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found",
        )
    cfg = request.app.state.config
    return get_task_model_id(
        model_id,
        cfg.TASK_MODEL,
        cfg.TASK_MODEL_EXTERNAL,
        models,
    )


def _resolve_template(config_value: str, default: str) -> str:
    """Return *config_value* if non-empty (after stripping), else *default*."""
    return config_value if config_value.strip() else default


def _build_metadata(
    request: Request,
    task_type: TASKS,
    form_data: dict,
) -> dict[str, Any]:
    """Construct the standard ``metadata`` block for a task payload."""
    base = getattr(request.state, "metadata", None)
    return {
        **({} if base is None else base),
        "task": str(task_type),
        "task_body": form_data,
        "chat_id": form_data.get("chat_id"),
    }


def _ollama_token_key(models: dict, task_model_id: str, tokens: int) -> dict[str, int]:
    """Return ``{max_tokens: N}`` for Ollama or ``{max_completion_tokens: N}`` otherwise."""
    if models.get(task_model_id, {}).get("owned_by") == "ollama":
        return {"max_tokens": tokens}
    return {"max_completion_tokens": tokens}


def _strip_reasoning_details(messages: list[dict[str, Any]]) -> None:
    """Remove ``<details type="reasoning">…</details>`` blocks in-place."""
    for msg in messages:
        msg["content"] = _REASONING_DETAIL_RE.sub("", msg["content"]).strip()


async def _run_pipeline_and_complete(
    request: Request,
    payload: dict[str, Any],
    user: Any,
    models: dict[str, Any],
) -> Any:
    """Run the inlet filter pipeline, then call :func:`generate_chat_completion`.

    Returns the completion result or a :class:`JSONResponse` error.
    """
    try:
        payload = await process_pipeline_inlet_filter(request, payload, user, models)
    except Exception:
        raise

    try:
        return await generate_chat_completion(request, form_data=payload, user=user)
    except Exception as exc:
        log.error("Task completion failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "An internal error has occurred."},
        )


def _make_simple_payload(
    task_model_id: str,
    content: str,
    metadata: dict[str, Any],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the standard single-user-message payload used by most tasks."""
    payload: dict[str, Any] = {
        "model": task_model_id,
        "messages": [{"role": "user", "content": content}],
        "stream": False,
        "metadata": metadata,
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_task_config(request: Request, user=Depends(get_verified_user)):
    """Return the current task configuration."""
    return _read_config(request)


class TaskConfigForm(BaseModel):
    """Form body for ``POST /config/update``."""

    TASK_MODEL: Optional[str] = None
    TASK_MODEL_EXTERNAL: Optional[str] = None
    ENABLE_TITLE_GENERATION: bool
    TITLE_GENERATION_PROMPT_TEMPLATE: str
    IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_AUTOCOMPLETE_GENERATION: bool
    AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH: int
    TAGS_GENERATION_PROMPT_TEMPLATE: str
    ENABLE_TAGS_GENERATION: bool
    ENABLE_SEARCH_QUERY_GENERATION: bool
    ENABLE_RETRIEVAL_QUERY_GENERATION: bool
    QUERY_GENERATION_PROMPT_TEMPLATE: str
    TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE: str
    ENABLE_CONTEXT_COMPRESSION: bool
    CONTEXT_COMPRESSION_MODEL: Optional[str] = None
    CONTEXT_COMPRESSION_PROMPT_TEMPLATE: str
    ENABLE_SMART_QUERY: bool
    SMART_QUERY_MODEL: Optional[str] = None
    SMART_QUERY_PROMPT_TEMPLATE: str


@router.post("/config/update")
async def update_task_config(
    request: Request,
    form_data: TaskConfigForm,
    user=Depends(get_admin_user),
):
    """Persist updated task configuration and return the new state."""
    cfg = request.app.state.config
    for field in _CONFIG_FIELDS:
        setattr(cfg, field, getattr(form_data, field))
    return _read_config(request)


# ---------------------------------------------------------------------------
# Title generation
# ---------------------------------------------------------------------------


@router.post("/title/completions")
async def generate_title(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate a short title for a chat conversation."""
    if not request.app.state.config.ENABLE_TITLE_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Title generation is disabled"},
        )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Generating title with model %s for %s", task_model_id, user.email)

    template = _resolve_template(
        request.app.state.config.TITLE_GENERATION_PROMPT_TEMPLATE,
        DEFAULT_TITLE_GENERATION_PROMPT_TEMPLATE,
    )

    messages = form_data["messages"]
    _strip_reasoning_details(messages)

    content = title_generation_template(
        template,
        messages,
        _user_context(user, include_location=True),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.TITLE_GENERATION, form_data),
        extra=_ollama_token_key(models, task_model_id, 1000),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Tags generation
# ---------------------------------------------------------------------------


@router.post("/tags/completions")
async def generate_chat_tags(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate tags for a chat conversation."""
    if not request.app.state.config.ENABLE_TAGS_GENERATION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Tags generation is disabled"},
        )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Generating tags with model %s for %s", task_model_id, user.email)

    template = _resolve_template(
        request.app.state.config.TAGS_GENERATION_PROMPT_TEMPLATE,
        DEFAULT_TAGS_GENERATION_PROMPT_TEMPLATE,
    )

    content = tags_generation_template(
        template, form_data["messages"], _user_context(user),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.TAGS_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Image prompt generation
# ---------------------------------------------------------------------------


@router.post("/image_prompt/completions")
async def generate_image_prompt(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate an image-generation prompt from conversation messages."""
    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Generating image prompt with model %s for %s", task_model_id, user.email)

    template = _resolve_template(
        request.app.state.config.IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
        DEFAULT_IMAGE_PROMPT_GENERATION_PROMPT_TEMPLATE,
    )

    content = image_prompt_generation_template(
        template,
        form_data["messages"],
        user=_user_context(user),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.IMAGE_PROMPT_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Image prompt translation
# ---------------------------------------------------------------------------


@router.post("/image_prompt/translate")
async def translate_image_prompt(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Translate an image prompt to English."""
    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Translating image prompt with model %s for %s", task_model_id, user.email)

    template = _resolve_template(
        request.app.state.config.IMAGE_PROMPT_TRANSLATION_TEMPLATE,
        DEFAULT_IMAGE_PROMPT_TRANSLATION_TEMPLATE,
    )

    content = image_prompt_translation_template(template, form_data["prompt"])

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.IMAGE_PROMPT_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Image prompt expansion
# ---------------------------------------------------------------------------


@router.post("/image_prompt/expand")
async def expand_image_prompt(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Expand / enrich an image prompt with additional detail."""
    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Expanding image prompt with model %s for %s", task_model_id, user.email)

    template = _resolve_template(
        request.app.state.config.IMAGE_PROMPT_EXPANSION_TEMPLATE,
        DEFAULT_IMAGE_PROMPT_EXPANSION_TEMPLATE,
    )

    content = image_prompt_expansion_template(template, form_data["prompt"])

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.IMAGE_PROMPT_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Search / retrieval query generation
# ---------------------------------------------------------------------------


@router.post("/queries/completions")
async def generate_queries(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate search or retrieval queries from conversation context."""
    query_type = form_data.get("type")
    if query_type == "web_search":
        if not request.app.state.config.ENABLE_SEARCH_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search query generation is disabled",
            )
    elif query_type == "retrieval":
        if not request.app.state.config.ENABLE_RETRIEVAL_QUERY_GENERATION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query generation is disabled",
            )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug(
        "Generating %s queries with model %s for %s",
        query_type,
        task_model_id,
        user.email,
    )

    template = _resolve_template(
        request.app.state.config.QUERY_GENERATION_PROMPT_TEMPLATE,
        DEFAULT_QUERY_GENERATION_PROMPT_TEMPLATE,
    )

    content = query_generation_template(
        template, form_data["messages"], _user_context(user),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.QUERY_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Autocompletion
# ---------------------------------------------------------------------------


@router.post("/auto/completions")
async def generate_autocompletion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate an autocomplete suggestion for the user's current input."""
    if not request.app.state.config.ENABLE_AUTOCOMPLETE_GENERATION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Autocompletion generation is disabled",
        )

    prompt = form_data.get("prompt")
    messages = form_data.get("messages")
    auto_type = form_data.get("type")

    max_len = request.app.state.config.AUTOCOMPLETE_GENERATION_INPUT_MAX_LENGTH
    if max_len > 0 and len(prompt) > max_len:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input prompt exceeds maximum length of %d" % max_len,
        )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug(
        "Generating autocompletion with model %s for %s",
        task_model_id,
        user.email,
    )

    template = _resolve_template(
        request.app.state.config.AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
        DEFAULT_AUTOCOMPLETE_GENERATION_PROMPT_TEMPLATE,
    )

    content = autocomplete_generation_template(
        template, prompt, messages, auto_type, _user_context(user),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.AUTOCOMPLETE_GENERATION, form_data),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Emoji generation
# ---------------------------------------------------------------------------


@router.post("/emoji/completions")
async def generate_emoji(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Generate an emoji that represents the given prompt."""
    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Generating emoji with model %s for %s", task_model_id, user.email)

    content = emoji_generation_template(
        DEFAULT_EMOJI_GENERATION_PROMPT_TEMPLATE,
        form_data["prompt"],
        _user_context(user, include_location=True),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.EMOJI_GENERATION, form_data),
        extra=_ollama_token_key(models, task_model_id, 4),
    )
    payload["chat_id"] = form_data.get("chat_id")

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Mixture-of-Agents synthesis
# ---------------------------------------------------------------------------


@router.post("/moa/completions")
async def generate_moa_response(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Synthesize a Mixture-of-Agents response from multiple model outputs."""
    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    log.debug("Generating MOA response with model %s for %s", task_model_id, user.email)

    content = moa_response_generation_template(
        DEFAULT_MOA_GENERATION_PROMPT_TEMPLATE,
        form_data["prompt"],
        form_data["responses"],
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.MOA_RESPONSE_GENERATION, form_data),
    )
    payload["stream"] = form_data.get("stream", False)

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Context compression
# ---------------------------------------------------------------------------


@router.post("/context/compression/completions")
async def generate_context_compression(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Compress conversation context into a shorter representation."""
    if not request.app.state.config.ENABLE_CONTEXT_COMPRESSION:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Context compression is disabled"},
        )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    template = _resolve_template(
        request.app.state.config.CONTEXT_COMPRESSION_PROMPT_TEMPLATE,
        DEFAULT_CONTEXT_COMPRESSION_PROMPT_TEMPLATE,
    )

    messages = form_data["messages"]
    _strip_reasoning_details(messages)

    content = context_compression_template(
        template,
        messages,
        _user_context(user, include_location=True),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.CONTEXT_COMPRESSION, form_data),
        extra=_ollama_token_key(models, task_model_id, 2000),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)


# ---------------------------------------------------------------------------
# Smart query
# ---------------------------------------------------------------------------


@router.post("/smart-query/completions")
async def generate_smart_query(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
):
    """Refine a user query using smart-query analysis."""
    if not request.app.state.config.ENABLE_SMART_QUERY:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"detail": "Smart query is disabled"},
        )

    models = _resolve_models(request)
    task_model_id = _resolve_task_model(request, form_data["model"], models)

    template = _resolve_template(
        request.app.state.config.SMART_QUERY_PROMPT_TEMPLATE,
        DEFAULT_SMART_QUERY_PROMPT_TEMPLATE,
    )

    messages = form_data["messages"]
    _strip_reasoning_details(messages)

    content = smart_query_template(
        template,
        messages,
        _user_context(user, include_location=True),
    )

    payload = _make_simple_payload(
        task_model_id,
        content,
        _build_metadata(request, TASKS.SMART_QUERY, form_data),
        extra=_ollama_token_key(models, task_model_id, 1000),
    )

    return await _run_pipeline_and_complete(request, payload, user, models)
