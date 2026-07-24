"""Function (pipe) module loader and chat-completion dispatcher.

This module resolves user-defined Python function modules that expose a
``pipe`` callable, assembles their parameters, and executes them — returning
either a complete chat-completion payload or a ``StreamingResponse`` that
emits server-sent events (SSE).

Only three symbols are exported for external use:

* :func:`get_function_module_by_id`  – load / cache a function module
* :func:`get_function_models`         – list models exposed by pipe functions
* :func:`generate_function_chat_completion` – run a pipe and return its output
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import sys
from typing import Any, AsyncGenerator, Generator, Iterator

from fastapi import Request
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from bcgpt.env import GLOBAL_LOG_LEVEL, SRC_LOG_LEVELS
from bcgpt.models import Functions, Models
from bcgpt.socket.main import get_event_call, get_event_emitter
from bcgpt.utils import get_tools, load_function_module_by_id
from bcgpt.utils.misc import (
    openai_chat_chunk_message_template,
    openai_chat_completion_message_template,
)
from bcgpt.utils.openai_reasoning import transform_reasoning_payload
from bcgpt.utils.payload import (
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _resolve_pipes(module: Any) -> list[dict]:
    """Return the ``pipes`` list from *module*, handling sync/async callables.

    A module may define ``pipes`` as a plain list, a synchronous function,
    or an ``async`` function.  This helper normalises all three cases and
    returns an empty list on failure rather than propagating exceptions.
    """
    pipes_attr = getattr(module, "pipes", None)
    if pipes_attr is None:
        return []

    if callable(pipes_attr):
        try:
            if asyncio.iscoroutinefunction(pipes_attr):
                return await pipes_attr()  # type: ignore[no-any-return]
            return pipes_attr()  # type: ignore[no-any-return]
        except Exception:
            log.exception("Failed to resolve pipes from module")
            return []

    return list(pipes_attr)


def _build_model_entry(
    *,
    pipe_id: str,
    name: str,
    created_at: int,
    pipe_type: str,
) -> dict:
    """Create an OpenAI-compatible model descriptor dict."""
    return {
        "id": pipe_id,
        "name": name,
        "object": "model",
        "created": created_at,
        "owned_by": "openai",
        "pipe": {"type": pipe_type},
    }


async def _execute_pipe(pipe: Any, params: dict[str, Any]) -> Any:
    """Invoke *pipe* with *params*, awaiting if it is a coroutine function."""
    if inspect.iscoroutinefunction(pipe):
        return await pipe(**params)
    return pipe(**params)


async def _collect_string_content(result: str | Generator | AsyncGenerator) -> str:
    """Concatenate all chunks from a generator into a single string."""
    if isinstance(result, str):
        return result
    if isinstance(result, Generator):
        return "".join(map(str, result))
    if isinstance(result, AsyncGenerator):
        return "".join([str(chunk) async for chunk in result])
    return str(result)


def _extract_pipe_id(model: str) -> str:
    """Strip sub-pipe suffix after the first dot to get the base pipe id."""
    return model.split(".", 1)[0] if "." in model else model


def _sse_format_line(form_data: dict, line: Any) -> str:
    """Normalise a single streaming line into an SSE ``data:`` frame.

    * ``BaseModel`` instances and plain dicts are JSON-serialised.
    * Bytes are decoded to UTF-8 (silently ignored on failure).
    * Lines already starting with ``data:`` are passed through.
    * Bare strings are wrapped in an OpenAI chunk template.
    """
    if isinstance(line, BaseModel):
        line = f"data: {line.model_dump_json()}"
    elif isinstance(line, dict):
        line = f"data: {json.dumps(line)}"
    else:
        try:
            line = line.decode("utf-8")  # type: ignore[union-attr]
        except Exception:
            pass

        if isinstance(line, str) and line.startswith("data:"):
            return f"{line}\n\n"

    # At this point *line* is a string that needs wrapping.
    if isinstance(line, str) and line.startswith("data:"):
        return f"{line}\n\n"

    chunk = openai_chat_chunk_message_template(form_data["model"], str(line))
    return f"data: {json.dumps(chunk)}\n\n"


def _build_pipe_params(
    function_module: Any,
    form_data: dict,
    user: Any,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Construct keyword arguments for a module's ``pipe`` callable.

    Only parameters that exist in the pipe's signature are forwarded from
    *extra_params*.  If ``__user__`` is present and the module defines
    ``UserValves``, the user's valves are attached.
    """
    if extra_params is None:
        extra_params = {}

    pipe_id = _extract_pipe_id(form_data["model"])
    sig = inspect.signature(function_module.pipe)

    params: dict[str, Any] = {"body": form_data}
    params.update(
        {k: v for k, v in extra_params.items() if k in sig.parameters}
    )

    if "__user__" in params and hasattr(function_module, "UserValves"):
        user_valves = Functions.get_user_valves_by_id_and_user_id(
            pipe_id, user.id
        )
        try:
            params["__user__"]["valves"] = function_module.UserValves(
                **(user_valves or {})
            )
        except Exception:
            log.exception("Failed to initialise UserValves for %s", pipe_id)
            params["__user__"]["valves"] = function_module.UserValves()

    return params


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_function_module_by_id(request: Request, pipe_id: str) -> Any:
    """Load and cache a function module identified by *pipe_id*.

    Modules are stored in ``request.app.state.FUNCTIONS`` for reuse across
    requests.  If the module declares ``Valves``, they are hydrated from
    the database on every call so that runtime configuration changes take
    effect immediately.
    """
    cache = request.app.state.FUNCTIONS
    if pipe_id in cache:
        function_module = cache[pipe_id]
    else:
        function_module, _, _ = load_function_module_by_id(pipe_id)
        cache[pipe_id] = function_module

    if hasattr(function_module, "valves") and hasattr(function_module, "Valves"):
        valves = Functions.get_function_valves_by_id(pipe_id)
        function_module.valves = function_module.Valves(**(valves or {}))

    return function_module


async def get_function_models(request: Request) -> list[dict]:
    """Return model descriptors for all active pipe-type functions.

    Functions that expose a ``pipes`` attribute are treated as *manifolds*
    — each sub-pipe becomes a separate model entry.  Otherwise the function
    itself is exposed as a single model.
    """
    pipes = Functions.get_functions_by_type("pipe", active_only=True)
    models: list[dict] = []

    for pipe in pipes:
        function_module = get_function_module_by_id(request, pipe.id)
        sub_pipes = await _resolve_pipes(function_module)

        if sub_pipes:
            log.debug(
                "get_function_models: %s is a manifold with %d sub-pipes",
                pipe.id,
                len(sub_pipes),
            )
            parent_name = getattr(function_module, "name", "")
            for sp in sub_pipes:
                sub_id = f'{pipe.id}.{sp["id"]}'
                sub_name = f"{parent_name}{sp['name']}" if parent_name else sp["name"]
                models.append(
                    _build_model_entry(
                        pipe_id=sub_id,
                        name=sub_name,
                        created_at=pipe.created_at,
                        pipe_type=pipe.type,
                    )
                )
        else:
            log.debug(
                "get_function_models: %s is a single pipe (id=%s, name=%s)",
                pipe.id,
                pipe.id,
                pipe.name,
            )
            models.append(
                _build_model_entry(
                    pipe_id=pipe.id,
                    name=pipe.name,
                    created_at=pipe.created_at,
                    pipe_type="pipe",
                )
            )

    return models


async def generate_function_chat_completion(
    request: Request,
    form_data: dict,
    user: Any,
    models: dict | None = None,
) -> dict | StreamingResponse:
    """Execute a pipe function and return a chat-completion payload or SSE stream.

    Parameters
    ----------
    request:
        The incoming FastAPI request (used for app-state access).
    form_data:
        The OpenAI-compatible request body.  ``form_data["model"]`` is used
        to locate the target pipe module.
    user:
        The authenticated user object (must have ``id``, ``email``, ``name``,
        ``role`` attributes).
    models:
        Optional mapping of model-id to model-info dicts, used when the
        requested model is a wrapper around a base model.

    Returns
    -------
    dict | StreamingResponse
        A complete chat-completion dict (non-streaming) or an SSE
        ``StreamingResponse`` (streaming).
    """
    if models is None:
        models = {}

    model_id = form_data.get("model", "")
    model_info = Models.get_model_by_id(model_id)

    # ---- metadata & event plumbing ------------------------------------
    metadata = form_data.pop("metadata", {})
    files = metadata.get("files", [])
    tool_ids = metadata.get("tool_ids") or []

    event_emitter = None
    event_call = None
    task = None
    task_body = None

    if metadata and all(
        k in metadata for k in ("session_id", "chat_id", "message_id")
    ):
        event_emitter = get_event_emitter(metadata)
        event_call = get_event_call(metadata)

    task = metadata.get("task")
    task_body = metadata.get("task_body")

    # ---- extra parameters forwarded to pipe ---------------------------
    extra_params: dict[str, Any] = {
        "__event_emitter__": event_emitter,
        "__event_call__": event_call,
        "__chat_id__": metadata.get("chat_id"),
        "__session_id__": metadata.get("session_id"),
        "__message_id__": metadata.get("message_id"),
        "__task__": task,
        "__task_body__": task_body,
        "__files__": files,
        "__user__": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
        },
        "__metadata__": metadata,
        "__request__": request,
    }
    extra_params["__tools__"] = get_tools(
        request,
        tool_ids,
        user,
        {
            **extra_params,
            "__model__": models.get(model_id),
            "__messages__": form_data["messages"],
            "__files__": files,
        },
    )

    # ---- apply model-level overrides ----------------------------------
    if model_info:
        if model_info.base_model_id:
            form_data["model"] = model_info.base_model_id

        params = model_info.params.model_dump()
        form_data = apply_model_params_to_body_openai(params, form_data)
        form_data = apply_model_system_prompt_to_body(
            params, form_data, metadata, user
        )
        form_data = transform_reasoning_payload(form_data)

    # ---- resolve & execute the pipe -----------------------------------
    pipe_id = _extract_pipe_id(form_data["model"])
    function_module = get_function_module_by_id(request, pipe_id)
    pipe = function_module.pipe
    pipe_params = _build_pipe_params(function_module, form_data, user, extra_params)

    if form_data.get("stream", False):
        return StreamingResponse(
            _stream_pipe_output(pipe, pipe_params, form_data),
            media_type="text/event-stream",
        )

    # ---- non-streaming path -------------------------------------------
    try:
        result = await _execute_pipe(pipe, pipe_params)
    except Exception as exc:
        log.error("Pipe execution failed: %s", exc)
        return {"error": {"detail": str(exc)}}

    if isinstance(result, (StreamingResponse, dict)):
        return result
    if isinstance(result, BaseModel):
        return result.model_dump()

    content = await _collect_string_content(result)
    return openai_chat_completion_message_template(form_data["model"], content)


# ---------------------------------------------------------------------------
# Streaming generator (private)
# ---------------------------------------------------------------------------

async def _stream_pipe_output(
    pipe: Any,
    params: dict[str, Any],
    form_data: dict,
) -> AsyncGenerator[str, None]:
    """Yield SSE frames from a pipe execution.

    Handles all output types produced by pipe functions: bare strings,
    sync/async generators of lines, dicts, ``BaseModel`` instances, and
    ``StreamingResponse`` wrappers.
    """
    try:
        result = await _execute_pipe(pipe, params)
    except Exception as exc:
        log.error("Streaming pipe execution failed: %s", exc)
        yield f"data: {json.dumps({'error': {'detail': str(exc)}})}\n\n"
        return

    # Passthrough for already-streaming responses
    if isinstance(result, StreamingResponse):
        async for data in result.body_iterator:
            yield data
        return

    # Single dict response
    if isinstance(result, dict):
        yield f"data: {json.dumps(result)}\n\n"
        return

    # Plain string — emit as a single chunk
    if isinstance(result, str):
        message = openai_chat_chunk_message_template(form_data["model"], result)
        yield f"data: {json.dumps(message)}\n\n"

    # Sync iterator
    if isinstance(result, Iterator):
        for line in result:
            yield _sse_format_line(form_data, line)

    # Async iterator
    if isinstance(result, AsyncGenerator):
        async for line in result:
            yield _sse_format_line(form_data, line)

    # Emit stop sentinel for string / Generator outputs
    if isinstance(result, (str, Generator)):
        finish = openai_chat_chunk_message_template(form_data["model"], "")
        finish["choices"][0]["finish_reason"] = "stop"
        yield f"data: {json.dumps(finish)}\n\n"
        yield "data: [DONE]"
