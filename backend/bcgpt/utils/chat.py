"""Chat completion orchestration and lifecycle handlers.

This module is the central hub for generating chat completions. It coordinates
model resolution, access control, arena routing, provider dispatch, streaming,
pipeline filters, and post-completion lifecycle hooks (actions, outlet filters).

Public API:
    - :func:`generate_chat_completion` — main entry point for completions
    - :func:`generate_direct_chat_completion` — completions proxied through socket events
    - :func:`chat_completed` — post-completion outlet processing
    - :func:`chat_action` — execute a user-triggered action function
    - ``chat_completion`` — alias for ``generate_chat_completion``
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import secrets
import sys
import uuid
from typing import Any, Optional

from fastapi import Request
from starlette.responses import StreamingResponse

from bcgpt.env import BYPASS_MODEL_ACCESS_CONTROL, GLOBAL_LOG_LEVEL, SRC_LOG_LEVELS
from bcgpt.functions import generate_function_chat_completion
from bcgpt.models import Functions, Models, UserModel
from bcgpt.providers import get_provider
from bcgpt.routers.ollama import (
    generate_chat_completion as generate_ollama_chat_completion,
)
from bcgpt.routers.openai import (
    generate_chat_completion as generate_openai_chat_completion,
)
from bcgpt.routers.pipelines import (
    process_pipeline_inlet_filter,
    process_pipeline_outlet_filter,
)
from bcgpt.socket.main import get_event_call, get_event_emitter, sio
from bcgpt.utils import (
    check_model_access,
    convert_payload_openai_to_ollama,
    get_all_models,
    load_function_module_by_id,
)
from bcgpt.utils.filter import get_sorted_filter_ids, process_filter_functions
from bcgpt.utils.llm_gateway import get_gateway
from bcgpt.utils.resilience import make_retryable_llm_call
from bcgpt.utils.response import (
    convert_response_ollama_to_openai,
    convert_streaming_response_ollama_to_openai,
)

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Model resolution helpers
# ---------------------------------------------------------------------------


def _resolve_models(request: Request) -> dict:
    """Return the model registry, scoped to a single model for direct connections."""
    if getattr(request.state, "direct", False) and hasattr(request.state, "model"):
        return {request.state.model["id"]: request.state.model}
    return request.app.state.MODELS


def _get_or_init_gateway(request: Request):
    """Lazily initialise the LiteLLM gateway from app config, or return ``None``."""
    try:
        urls = request.app.state.config.OPENAI_API_BASE_URLS
        keys = request.app.state.config.OPENAI_API_KEYS
        fallback = getattr(request.app.state.config, "LITELLM_FALLBACK_MODEL", "")
        num_retries = getattr(request.app.state.config, "LITELLM_NUM_RETRIES", 3)
        timeout = getattr(request.app.state.config, "LITELLM_TIMEOUT", 60)

        return get_gateway(
            primary_model="default",
            fallback_model=fallback,
            api_base=urls[0] if urls else "",
            api_key=keys[0] if keys else "",
            num_retries=num_retries,
            timeout=timeout,
        )
    except Exception:
        return None


def _build_event_metadata(data: dict, user: Any) -> dict:
    """Build the metadata dict used for event emitters / callers."""
    return {
        "chat_id": data["chat_id"],
        "message_id": data["id"],
        "session_id": data["session_id"],
        "user_id": user.id,
    }


def _build_extra_params(
    data: dict,
    user: Any,
    model: dict,
    request: Request,
) -> dict:
    """Build the extra-parameters dict injected into filter / action functions."""
    metadata = _build_event_metadata(data, user)
    return {
        "__event_emitter__": get_event_emitter(metadata),
        "__event_call__": get_event_call(metadata),
        "__user__": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
        "__metadata__": metadata,
        "__request__": request,
        "__model__": model,
    }


# ---------------------------------------------------------------------------
# Arena model routing
# ---------------------------------------------------------------------------


def _resolve_arena_model(
    request: Request,
    form_data: dict,
    model: dict,
) -> str:
    """Pick a random non-arena model, respecting exclude filters.

    Returns the selected model ID and mutates ``form_data["model"]``.
    """
    model_ids = model.get("info", {}).get("meta", {}).get("model_ids")
    filter_mode = model.get("info", {}).get("meta", {}).get("filter_mode")

    # Build candidate list excluding arena models
    all_non_arena = [
        m["id"]
        for m in request.app.state.MODELS.values()
        if m.get("owned_by") != "arena"
    ]

    if model_ids and filter_mode == "exclude":
        candidates = [mid for mid in all_non_arena if mid not in model_ids]
    elif isinstance(model_ids, list) and model_ids:
        candidates = list(model_ids)
    else:
        candidates = all_non_arena

    if not candidates:
        raise Exception("No models available for arena routing")

    selected = secrets.choice(candidates)
    form_data["model"] = selected
    return selected


# ---------------------------------------------------------------------------
# LLM provider dispatch
# ---------------------------------------------------------------------------


@make_retryable_llm_call
async def _call_llm_provider(
    request: Request,
    form_data: dict,
    user: Any,
    bypass_filter: bool,
    model: dict,
) -> Any:
    """Dispatch a chat completion to the appropriate LLM backend.

    Tries the LiteLLM gateway first (non-streaming only), then falls back
    to the provider system, and finally to the generic OpenAI/Ollama routers.
    """
    # Attempt LiteLLM gateway for non-streaming requests
    gateway_enabled = getattr(
        request.app.state.config, "LITELLM_GATEWAY_ENABLED", False
    )
    if gateway_enabled and not form_data.get("stream"):
        gateway = _get_or_init_gateway(request)
        if gateway is not None:
            try:
                result = await gateway.completion(
                    model=form_data.get("model"),
                    messages=form_data.get("messages", []),
                    temperature=form_data.get("temperature"),
                    top_p=form_data.get("top_p"),
                    max_tokens=form_data.get("max_tokens"),
                    max_completion_tokens=form_data.get("max_completion_tokens"),
                )
                return result.model_dump()
            except Exception as exc:
                log.warning("LiteLLM gateway failed, falling back to direct call: %s", exc)

    # Provider-based dispatch
    provider = get_provider(model)
    if provider:
        return await provider.chat_completions(
            request=request,
            form_data=form_data,
            user=user,
            bypass_filter=bypass_filter,
        )

    # Generic OpenAI router fallback
    return await generate_openai_chat_completion(
        request=request,
        form_data=form_data,
        user=user,
        bypass_filter=bypass_filter,
    )


# ---------------------------------------------------------------------------
# Direct (socket-proxied) chat completion
# ---------------------------------------------------------------------------


async def generate_direct_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    models: dict,
):
    """Generate a chat completion proxied through a socket event.

    For streaming requests, returns a :class:`StreamingResponse` backed by
    a socket message queue. For non-streaming, returns the raw result dict.
    """
    metadata = form_data.pop("metadata", {})
    user_id = metadata.get("user_id")
    session_id = metadata.get("session_id")
    request_id = str(uuid.uuid4())

    event_caller = get_event_call(metadata)
    channel = f"{user_id}:{session_id}:{request_id}"

    payload = {
        "type": "request:chat:completion",
        "data": {
            "form_data": form_data,
            "model": models[form_data["model"]],
            "channel": channel,
            "session_id": session_id,
        },
    }

    if form_data.get("stream"):
        return await _handle_direct_stream(event_caller, channel, payload)
    return await _handle_direct_non_stream(event_caller, payload)


async def _handle_direct_stream(event_caller, channel: str, payload: dict):
    """Handle a streaming direct-completion request via socket queue."""
    q: asyncio.Queue = asyncio.Queue()

    async def _on_message(sid, data):
        await q.put(data)

    sio.on(channel, _on_message)
    res = await event_caller(payload)
    log.info("direct stream res: %s", res)

    if not res.get("status", False):
        raise Exception(str(res))

    async def _event_generator():
        try:
            while True:
                data = await q.get()
                if isinstance(data, dict):
                    if data.get("done"):
                        break
                    yield f"data: {json.dumps(data)}\n\n"
                elif isinstance(data, str):
                    yield data
        except Exception as exc:
            log.debug("Error in event generator: %s", exc)

    async def _cleanup():
        try:
            del sio.handlers["/"][channel]
        except Exception:
            pass

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        background=_cleanup,
    )


async def _handle_direct_non_stream(event_caller, payload: dict):
    """Handle a non-streaming direct-completion request."""
    res = await event_caller(payload)
    if res.get("error"):
        raise Exception(res["error"])
    return res


# ---------------------------------------------------------------------------
# Main chat completion entry point
# ---------------------------------------------------------------------------


async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    bypass_filter: bool = False,
):
    """Generate a chat completion for the given request.

    This is the primary entry point called by routers and middleware. It handles:

    1. Metadata merging from request state
    2. Model lookup and access control
    3. Direct-connection proxying
    4. Arena model random routing
    5. Pipe (function) model dispatch
    6. Standard LLM provider dispatch

    Args:
        request: The incoming FastAPI request.
        form_data: Chat completion payload (messages, model, params, etc.).
        user: The authenticated user object.
        bypass_filter: Skip model access-control checks.

    Returns:
        A completion response (dict or :class:`StreamingResponse`).

    Raises:
        Exception: If the model is not found or access is denied.
    """
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    # Merge metadata from request state
    if hasattr(request.state, "metadata"):
        form_data["metadata"] = {
            **(form_data.get("metadata") or {}),
            **request.state.metadata,
        }

    models = _resolve_models(request)
    model_id = form_data["model"]

    if model_id not in models:
        raise Exception("Model not found")

    model = models[model_id]

    # --- Direct connection path ------------------------------------------------
    if getattr(request.state, "direct", False):
        return await generate_direct_chat_completion(
            request, form_data, user=user, models=models,
        )

    # --- Access control --------------------------------------------------------
    if not bypass_filter and user.role == "user":
        check_model_access(user, model)

    # --- Arena routing ---------------------------------------------------------
    if model.get("owned_by") == "arena":
        return await _handle_arena_completion(request, form_data, user, model)

    # --- Pipe (function) model -------------------------------------------------
    if model.get("pipe"):
        return await generate_function_chat_completion(
            request, form_data, user=user, models=models,
        )

    # --- Standard LLM provider -------------------------------------------------
    return await _call_llm_provider(
        request=request,
        form_data=form_data,
        user=user,
        bypass_filter=bypass_filter,
        model=model,
    )


async def _handle_arena_completion(
    request: Request,
    form_data: dict,
    user: Any,
    model: dict,
):
    """Route an arena request to a randomly selected model."""
    selected_model_id = _resolve_arena_model(request, form_data, model)

    if form_data.get("stream"):
        response = await generate_chat_completion(
            request, form_data, user, bypass_filter=True,
        )
        selection_event = f"data: {json.dumps({'selected_model_id': selected_model_id})}\n\n"

        async def _stream_with_selection(body):
            yield selection_event
            async for chunk in body:
                yield chunk

        return StreamingResponse(
            _stream_with_selection(response.body_iterator),
            media_type="text/event-stream",
            background=response.background,
        )

    return {
        **(await generate_chat_completion(request, form_data, user, bypass_filter=True)),
        "selected_model_id": selected_model_id,
    }


# Public alias used by the lazy-import system
chat_completion = generate_chat_completion


# ---------------------------------------------------------------------------
# Post-completion lifecycle
# ---------------------------------------------------------------------------


async def chat_completed(request: Request, form_data: dict, user: Any):
    """Process outlet filters after a chat completion finishes.

    Runs pipeline outlet filters and per-model filter functions (outlet type),
    then returns the processed data. Used for post-processing hooks like
    logging, analytics, and content moderation.
    """
    if not request.app.state.MODELS:
        await get_all_models(request, user=user)

    models = _resolve_models(request)
    data = form_data
    model_id = data["model"]

    if model_id not in models:
        raise Exception("Model not found")

    model = models[model_id]

    # Pipeline outlet filter
    try:
        data = await process_pipeline_outlet_filter(request, data, user, models)
    except Exception as exc:
        return Exception(f"Error: {exc}")

    # Per-model filter functions (outlet)
    extra_params = _build_extra_params(data, user, model, request)

    try:
        filter_functions = [
            Functions.get_function_by_id(fid)
            for fid in get_sorted_filter_ids(model)
        ]
        result, _ = await process_filter_functions(
            request=request,
            filter_functions=filter_functions,
            filter_type="outlet",
            form_data=data,
            extra_params=extra_params,
        )
        return result
    except Exception as exc:
        return Exception(f"Error: {exc}")


# ---------------------------------------------------------------------------
# Chat actions
# ---------------------------------------------------------------------------


async def chat_action(
    request: Request,
    action_id: str,
    form_data: dict,
    user: Any,
):
    """Execute a user-triggered action function.

    Loads and runs the action function identified by *action_id* (optionally
    with a sub-action), injecting the standard extra parameters
    (``__event_emitter__``, ``__user__``, etc.) based on the function signature.

    Args:
        request: The incoming FastAPI request.
        action_id: Dotted action identifier (``"func_id"`` or ``"func_id.sub"``).
        form_data: Action payload containing chat/message metadata.
        user: The authenticated user object.

    Returns:
        The result of the action function, or an ``Exception`` on failure.
    """
    # Parse dotted action ID
    if "." in action_id:
        action_id, sub_action_id = action_id.split(".", 1)
    else:
        sub_action_id = None

    action = Functions.get_function_by_id(action_id)
    if not action:
        raise Exception(f"Action not found: {action_id}")

    if not request.app.state.MODELS:
        await get_all_models(request, user=user)

    models = _resolve_models(request)
    data = form_data
    model_id = data["model"]

    if model_id not in models:
        raise Exception("Model not found")
    model = models[model_id]

    # Load function module
    if action_id in request.app.state.FUNCTIONS:
        function_module = request.app.state.FUNCTIONS[action_id]
    else:
        function_module, _, _ = load_function_module_by_id(action_id)
        request.app.state.FUNCTIONS[action_id] = function_module

    # Apply global valves
    if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
        valves = Functions.get_function_valves_by_id(action_id)
        function_module.valves = function_module.Valves(**(valves or {}))

    # Execute the action
    if not hasattr(function_module, "action"):
        return data

    try:
        return await _execute_action(
            function_module=function_module,
            action_id=action_id,
            sub_action_id=sub_action_id,
            data=data,
            model=model,
            request=request,
            user=user,
        )
    except Exception as exc:
        return Exception(f"Error: {exc}")


async def _execute_action(
    function_module,
    action_id: str,
    sub_action_id: str | None,
    data: dict,
    model: dict,
    request: Request,
    user: Any,
):
    """Invoke the action callable with signature-aware parameter injection."""
    action_fn = function_module.action
    sig = inspect.signature(action_fn)
    params: dict[str, Any] = {"body": data}

    # Metadata for event emitter / caller
    metadata = _build_event_metadata(data, user)
    event_emitter = get_event_emitter(metadata)
    event_call = get_event_call(metadata)

    # Inject extra parameters matching function signature
    extra_params = {
        "__model__": model,
        "__id__": sub_action_id if sub_action_id is not None else action_id,
        "__event_emitter__": event_emitter,
        "__event_call__": event_call,
        "__request__": request,
    }
    for key, value in extra_params.items():
        if key in sig.parameters:
            params[key] = value

    # Inject user with valves if the function expects __user__
    if "__user__" in sig.parameters:
        user_dict: dict[str, Any] = {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        }
        try:
            if hasattr(function_module, "UserValves"):
                user_dict["valves"] = function_module.UserValves(
                    **Functions.get_user_valves_by_id_and_user_id(action_id, user.id)
                )
        except Exception as exc:
            log.exception("Failed to get user valves: %s", exc)

        params["__user__"] = user_dict

    # Dispatch (sync or async)
    if inspect.iscoroutinefunction(action_fn):
        return await action_fn(**params)
    return action_fn(**params)
