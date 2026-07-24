"""
Ollama API proxy router for BCGPT.

Provides a clean proxy layer to one or more Ollama backend instances with:
  - Multi-instance aggregation (tags, versions, ps)
  - Round-robin model selection across instances
  - OpenAI-compatible endpoints (/v1/chat/completions, /v1/completions, /v1/models)
  - HuggingFace model download with progress streaming
  - Model upload with SHA-256 hash verification

Endpoint inventory (public API — do not change paths or shapes):
  HEAD/GET  /                               → health check
  POST      /verify                         → verify connection to an Ollama host
  GET/POST  /config, /config/update         → admin config read/write
  GET       /api/tags[/{url_idx}]            → list models
  GET       /api/version[/{url_idx}]         → get Ollama version
  GET       /api/ps                         → list loaded models across instances
  POST      /api/pull[/{url_idx}]            → pull a model
  DELETE    /api/push[/{url_idx}]            → push a model
  POST      /api/create[/{url_idx}]          → create a model
  POST      /api/copy[/{url_idx}]            → copy a model
  DELETE    /api/delete[/{url_idx}]          → delete a model
  POST      /api/show                       → show model info
  POST      /api/embed[/{url_idx}]           → batch embeddings
  POST      /api/embeddings[/{url_idx}]      → single embedding
  POST      /api/generate[/{url_idx}]        → generate completion
  POST      /api/chat[/{url_idx}]            → chat completion (Ollama native)
  POST      /v1/completions[/{url_idx}]      → OpenAI-compatible completion
  POST      /v1/chat/completions[/{url_idx}] → OpenAI-compatible chat
  GET       /v1/models[/{url_idx}]           → OpenAI-compatible model list
  POST      /models/download[/{url_idx}]     → download from HuggingFace
  POST      /models/upload[/{url_idx}]       → upload a GGUF file
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import secrets as _secrets
import time
from functools import lru_cache
from typing import Any, Optional, Union
from urllib.parse import urlparse

import aiohttp
import orjson
import requests
from aiocache import cached
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, validator
from starlette.background import BackgroundTask

from bcgpt.config import UPLOAD_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import (
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
    BYPASS_MODEL_ACCESS_CONTROL,
    ENABLE_FORWARD_USER_INFO_HEADERS,
    SRC_LOG_LEVELS,
)
from bcgpt.models import Models, UserModel
from bcgpt.utils import get_admin_user, get_verified_user, has_access
from bcgpt.utils.http_client import get_client_session
from bcgpt.utils.misc import calculate_sha256
from bcgpt.utils.payload import (
    apply_model_params_to_body_ollama,
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OLLAMA"])

# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()

# ---------------------------------------------------------------------------
# PII helpers
# ---------------------------------------------------------------------------


@lru_cache(maxsize=512)
def _hashed_pii(value: str) -> str:
    """Return a truncated SHA-256 hash for PII-safe logging / headers."""
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _user_info_headers(user: UserModel) -> dict[str, str]:
    """Build user-identity headers if forwarding is enabled."""
    if not ENABLE_FORWARD_USER_INFO_HEADERS or user is None:
        return {}
    return {
        "X-BCGPT-User-Name": user.name,
        "X-BCGPT-User-Id": _hashed_pii(user.id),
        "X-BCGPT-User-Email": _hashed_pii(user.email),
        "X-BCGPT-User-Role": user.role,
    }


def _auth_header(key: Optional[str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


# ---------------------------------------------------------------------------
# Config access helpers
# ---------------------------------------------------------------------------


def _cfg(request: Request):
    """Shorthand for the app-level config object."""
    return request.app.state.config


def _api_key(idx: int, url: str, configs: dict) -> Optional[str]:
    """Resolve the API key for a given Ollama instance index or URL."""
    parsed = urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    return configs.get(str(idx), configs.get(base, {})).get("key")


def _api_config(request: Request, idx: int, url: str) -> dict:
    """Return the per-instance config dict, with legacy URL-key fallback."""
    return _cfg(request).OLLAMA_API_CONFIGS.get(
        str(idx),
        _cfg(request).OLLAMA_API_CONFIGS.get(url, {}),
    )


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


async def _get_json(
    url: str,
    *,
    key: Optional[str] = None,
    user: Optional[UserModel] = None,
) -> Any:
    """GET a JSON response from *url*. Returns parsed JSON or *None* on error."""
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST)
    session = await get_client_session()
    headers = {
        "Content-Type": "application/json",
        **_auth_header(key),
        **_user_info_headers(user),  # type: ignore[arg-type]
    }
    try:
        async with session.get(url, timeout=timeout, headers=headers) as resp:
            return await resp.json()
    except Exception as exc:
        log.error("GET %s failed: %s", url, exc)
        return None


async def _cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
) -> None:
    if response:
        response.close()
    if session:
        await session.close()


async def _post(
    url: str,
    payload: Union[str, bytes],
    *,
    stream: bool = True,
    key: Optional[str] = None,
    content_type: Optional[str] = None,
    user: Optional[UserModel] = None,
):
    """POST *payload* to *url*. Returns StreamingResponse (stream=True) or JSON."""
    session = await get_client_session()
    headers = {
        "Content-Type": "application/json",
        **_auth_header(key),
        **_user_info_headers(user),  # type: ignore[arg-type]
    }

    r = None
    try:
        r = await session.post(
            url,
            data=payload,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            headers=headers,
        )
        r.raise_for_status()

        if stream:
            resp_headers = dict(r.headers)
            if content_type:
                resp_headers["Content-Type"] = content_type
            return StreamingResponse(
                r.content,
                status_code=r.status,
                headers=resp_headers,
                background=BackgroundTask(_cleanup_response, response=r, session=None),
            )
        else:
            data = await r.json()
            r.close()
            return data

    except Exception as exc:
        detail = None
        if r is not None:
            try:
                res = await r.json()
                if "error" in res:
                    detail = f"Ollama: {res.get('error', 'Unknown error')}"
            except Exception:
                detail = f"Ollama: {exc}"

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail or "BCGPT: Server Connection Error",
        )


def _sync_request(
    method: str,
    url: str,
    *,
    key: Optional[str] = None,
    user: Optional[UserModel] = None,
    data: Optional[bytes] = None,
):
    """Synchronous HTTP request (requests library). Used where async streaming
    proxy isn't needed — returns the raw :class:`requests.Response` so callers
    can inspect status / body."""
    headers = {
        "Content-Type": "application/json",
        **_auth_header(key),
        **_user_info_headers(user),  # type: ignore[arg-type]
    }
    return requests.request(method=method, url=url, headers=headers, data=data)


def _raise_from_sync(r: Optional[requests.Response], exc: Exception) -> None:
    """Raise a consistent HTTPException from a failed synchronous request."""
    detail = None
    if r is not None:
        try:
            res = r.json()
            if "error" in res:
                detail = f"Ollama: {res['error']}"
        except Exception:
            detail = f"Ollama: {exc}"

    raise HTTPException(
        status_code=r.status_code if r else 500,
        detail=detail or "BCGPT: Server Connection Error",
    )


# ---------------------------------------------------------------------------
# Model lookup helpers
# ---------------------------------------------------------------------------


async def _resolve_url_idx(
    request: Request,
    model_name: str,
    url_idx: Optional[int] = None,
) -> int:
    """Resolve *url_idx* by looking up *model_name* in the aggregated model map
    (with ``:latest`` suffix fallback) when *url_idx* is ``None``."""
    if url_idx is not None:
        return url_idx

    models = request.app.state.OLLAMA_MODELS
    key = model_name if ":" in model_name else f"{model_name}:latest"
    if key in models:
        return _secrets.choice(models[key]["urls"])

    raise HTTPException(
        status_code=400,
        detail=ERROR_MESSAGES.MODEL_NOT_FOUND(model_name),
    )


async def _resolve_url_and_config(
    request: Request,
    model_name: str,
    url_idx: Optional[int] = None,
):
    """Return ``(base_url, url_idx, api_config)`` for the chosen backend."""
    url_idx = await _resolve_url_idx(request, model_name, url_idx)
    base_url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    ac = _api_config(request, url_idx, base_url)
    return base_url, url_idx, ac


async def _get_ollama_url(request: Request, model: str, url_idx: Optional[int] = None):
    """Backward-compatible helper returning ``(url, url_idx)``."""
    idx = await _resolve_url_idx(request, model, url_idx)
    return _cfg(request).OLLAMA_BASE_URLS[idx], idx


# ---------------------------------------------------------------------------
# Model aggregation
# ---------------------------------------------------------------------------


@cached(ttl=30)
async def get_all_models(request: Request, user: Optional[UserModel] = None) -> dict:
    """Fetch model lists from all enabled Ollama instances and merge them."""
    cfg = _cfg(request)

    if not cfg.ENABLE_OLLAMA_API:
        models: dict[str, Any] = {"models": []}
        request.app.state.OLLAMA_MODELS = {}
        return models

    # Build per-instance fetch tasks
    tasks: list[asyncio.Task | asyncio.Future] = []
    for idx, url in enumerate(cfg.OLLAMA_BASE_URLS):
        ac = _api_config(request, idx, url)

        if str(idx) not in cfg.OLLAMA_API_CONFIGS and url not in cfg.OLLAMA_API_CONFIGS:
            tasks.append(_get_json(f"{url}/api/tags", user=user))
        else:
            if ac.get("enable", True):
                tasks.append(
                    _get_json(f"{url}/api/tags", key=ac.get("key"), user=user)
                )
            else:
                tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))

    responses = await asyncio.gather(*tasks)

    # Apply per-instance filtering and tagging
    for idx, resp in enumerate(responses):
        if not resp:
            continue
        url = cfg.OLLAMA_BASE_URLS[idx]
        ac = _api_config(request, idx, url)

        # Filter to allowed model IDs
        model_ids = ac.get("model_ids", [])
        if model_ids and "models" in resp:
            resp["models"] = [
                m for m in resp["models"] if m["model"] in model_ids
            ]

        # Namespace prefix
        prefix_id = ac.get("prefix_id")
        if prefix_id:
            for m in resp.get("models", []):
                m["model"] = f"{prefix_id}.{m['model']}"

        # Extra tags
        tags = ac.get("tags", [])
        if tags:
            for m in resp.get("models", []):
                m["tags"] = tags

    # Merge into a single list, tracking which instances serve each model
    merged: dict[str, dict] = {}
    for idx, resp in enumerate(responses):
        if resp is None:
            continue
        for model in resp.get("models", []):
            mid = model["model"]
            if mid not in merged:
                model["urls"] = [idx]
                merged[mid] = model
            else:
                merged[mid]["urls"].append(idx)

    result = {"models": list(merged.values())}
    request.app.state.OLLAMA_MODELS = {
        m["model"]: m for m in result["models"]
    }
    return result


async def _filtered_models(models: dict, user: UserModel) -> list[dict]:
    """Return only models the user is allowed to read."""
    filtered = []
    for model in models.get("models", []):
        info = Models.get_model_by_id(model["model"])
        if info and (
            user.id == info.user_id
            or has_access(user.id, type="read", access_control=info.access_control)
        ):
            filtered.append(model)
    return filtered


# ---------------------------------------------------------------------------
# Pydantic forms
# ---------------------------------------------------------------------------


class ConnectionVerificationForm(BaseModel):
    url: str
    key: Optional[str] = None


class OllamaConfigForm(BaseModel):
    ENABLE_OLLAMA_API: Optional[bool] = None
    OLLAMA_BASE_URLS: list[str]
    OLLAMA_API_CONFIGS: dict


class ModelNameForm(BaseModel):
    name: str


class PushModelForm(BaseModel):
    name: str
    insecure: Optional[bool] = None
    stream: Optional[bool] = None


class CreateModelForm(BaseModel):
    model: Optional[str] = None
    stream: Optional[bool] = None
    path: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class CopyModelForm(BaseModel):
    source: str
    destination: str


class GenerateEmbedForm(BaseModel):
    model: str
    input: list[str] | str
    truncate: Optional[bool] = None
    options: Optional[dict] = None
    keep_alive: Optional[Union[int, str]] = None


class GenerateEmbeddingsForm(BaseModel):
    model: str
    prompt: str
    options: Optional[dict] = None
    keep_alive: Optional[Union[int, str]] = None


class GenerateCompletionForm(BaseModel):
    model: str
    prompt: str
    suffix: Optional[str] = None
    images: Optional[list[str]] = None
    format: Optional[str] = None
    options: Optional[dict] = None
    system: Optional[str] = None
    template: Optional[str] = None
    context: Optional[list[int]] = None
    stream: Optional[bool] = True
    raw: Optional[bool] = None
    keep_alive: Optional[Union[int, str]] = None


class ChatMessage(BaseModel):
    role: str
    content: Optional[str] = None
    tool_calls: Optional[list[dict]] = None
    images: Optional[list[str]] = None

    @validator("content", pre=True)
    @classmethod
    def check_at_least_one_field(cls, field_value, values, **kwargs):
        if field_value is None and (
            "tool_calls" not in values or values["tool_calls"] is None
        ):
            raise ValueError(
                "At least one of 'content' or 'tool_calls' must be provided"
            )
        return field_value


class GenerateChatCompletionForm(BaseModel):
    model: str
    messages: list[ChatMessage]
    format: Optional[Union[dict, str]] = None
    options: Optional[dict] = None
    template: Optional[str] = None
    stream: Optional[bool] = True
    keep_alive: Optional[Union[int, str]] = None
    tools: Optional[list[dict]] = None


class OpenAIChatMessageContent(BaseModel):
    type: str
    model_config = ConfigDict(extra="allow")


class OpenAIChatMessage(BaseModel):
    role: str
    content: Union[str, list[OpenAIChatMessageContent]]
    model_config = ConfigDict(extra="allow")


class OpenAIChatCompletionForm(BaseModel):
    model: str
    messages: list[OpenAIChatMessage]
    model_config = ConfigDict(extra="allow")


class OpenAICompletionForm(BaseModel):
    model: str
    prompt: str
    model_config = ConfigDict(extra="allow")


class UrlForm(BaseModel):
    url: str


class UploadBlobForm(BaseModel):
    filename: str


# ---------------------------------------------------------------------------
# Health & config endpoints
# ---------------------------------------------------------------------------


@router.head("/")
@router.get("/")
async def get_status():
    return {"status": True}


@router.post("/verify")
async def verify_connection(
    form_data: ConnectionVerificationForm, user=Depends(get_admin_user)
):
    url = form_data.url
    key = form_data.key
    session = await get_client_session()

    try:
        async with session.get(
            f"{url}/api/version",
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
            headers={
                **_auth_header(key),
                **_user_info_headers(user),
            },
        ) as r:
            if r.status != 200:
                detail = f"HTTP Error: {r.status}"
                try:
                    res = await r.json()
                    if "error" in res:
                        detail = f"External Error: {res['error']}"
                except Exception:
                    pass
                log.error("Ollama provider error: %s", detail)
                raise HTTPException(status_code=500, detail=detail)
            return await r.json()

    except HTTPException:
        raise
    except aiohttp.ClientError as exc:
        log.error("Client error: %s", exc)
        raise HTTPException(status_code=500, detail="BCGPT: Server Connection Error")
    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        raise HTTPException(
            status_code=500, detail=f"Unexpected error: {exc}"
        )


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ENABLE_OLLAMA_API": _cfg(request).ENABLE_OLLAMA_API,
        "OLLAMA_BASE_URLS": _cfg(request).OLLAMA_BASE_URLS,
        "OLLAMA_API_CONFIGS": _cfg(request).OLLAMA_API_CONFIGS,
    }


@router.post("/config/update")
async def update_config(
    request: Request, form_data: OllamaConfigForm, user=Depends(get_admin_user)
):
    cfg = _cfg(request)
    cfg.ENABLE_OLLAMA_API = form_data.ENABLE_OLLAMA_API
    cfg.OLLAMA_BASE_URLS = form_data.OLLAMA_BASE_URLS
    cfg.OLLAMA_API_CONFIGS = form_data.OLLAMA_API_CONFIGS

    # Prune configs that don't correspond to any configured URL
    valid_keys = set(map(str, range(len(cfg.OLLAMA_BASE_URLS))))
    cfg.OLLAMA_API_CONFIGS = {
        k: v for k, v in cfg.OLLAMA_API_CONFIGS.items() if k in valid_keys
    }

    return {
        "ENABLE_OLLAMA_API": cfg.ENABLE_OLLAMA_API,
        "OLLAMA_BASE_URLS": cfg.OLLAMA_BASE_URLS,
        "OLLAMA_API_CONFIGS": cfg.OLLAMA_API_CONFIGS,
    }


# ---------------------------------------------------------------------------
# Ollama-native endpoints — models, versions, ps
# ---------------------------------------------------------------------------


@router.get("/api/tags")
@router.get("/api/tags/{url_idx}")
async def get_ollama_tags(
    request: Request, url_idx: Optional[int] = None, user=Depends(get_verified_user)
):
    if url_idx is None:
        models = await get_all_models(request, user=user)
    else:
        url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
        key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

        r = None
        try:
            r = _sync_request("GET", f"{url}/api/tags", key=key, user=user)
            r.raise_for_status()
            models = r.json()
        except Exception as exc:
            log.exception(exc)
            _raise_from_sync(r, exc)

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        models["models"] = await _filtered_models(models, user)

    return models


@router.get("/api/version")
@router.get("/api/version/{url_idx}")
async def get_ollama_versions(request: Request, url_idx: Optional[int] = None):
    if not _cfg(request).ENABLE_OLLAMA_API:
        return {"version": False}

    if url_idx is None:
        tasks = []
        for idx, url in enumerate(_cfg(request).OLLAMA_BASE_URLS):
            ac = _api_config(request, idx, url)
            if ac.get("enable", True):
                tasks.append(_get_json(f"{url}/api/version", key=ac.get("key")))

        responses = [r for r in await asyncio.gather(*tasks) if r is not None]
        if responses:
            lowest = min(
                responses,
                key=lambda x: tuple(
                    map(int, re.sub(r"^v|-.*", "", x["version"]).split("."))
                ),
            )
            return {"version": lowest["version"]}
        return {"version": False}

    # Specific instance
    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    r = None
    try:
        r = _sync_request("GET", f"{url}/api/version")
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


@router.get("/api/ps")
async def get_ollama_loaded_models(request: Request, user=Depends(get_verified_user)):
    """List models currently loaded into Ollama memory, keyed by base URL."""
    if not _cfg(request).ENABLE_OLLAMA_API:
        return {}

    tasks = []
    for idx, url in enumerate(_cfg(request).OLLAMA_BASE_URLS):
        ac = _api_config(request, idx, url)
        tasks.append(_get_json(f"{url}/api/ps", key=ac.get("key"), user=user))

    responses = await asyncio.gather(*tasks)
    return dict(zip(_cfg(request).OLLAMA_BASE_URLS, responses))


# ---------------------------------------------------------------------------
# Ollama-native endpoints — CRUD
# ---------------------------------------------------------------------------


@router.post("/api/pull")
@router.post("/api/pull/{url_idx}")
async def pull_model(
    request: Request,
    form_data: ModelNameForm,
    url_idx: int = 0,
    user=Depends(get_admin_user),
):
    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    log.info("Pulling model %s from %s", form_data.name, url)

    payload = {**form_data.model_dump(exclude_none=True), "insecure": True}
    return await _post(
        url=f"{url}/api/pull",
        payload=orjson.dumps(payload),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.delete("/api/push")
@router.delete("/api/push/{url_idx}")
async def push_model(
    request: Request,
    form_data: PushModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS
        if form_data.name in models:
            url_idx = models[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    log.debug("Pushing model %s to %s", form_data.name, url)

    return await _post(
        url=f"{url}/api/push",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.post("/api/create")
@router.post("/api/create/{url_idx}")
async def create_model(
    request: Request,
    form_data: CreateModelForm,
    url_idx: int = 0,
    user=Depends(get_admin_user),
):
    log.debug("Creating model: %s", form_data)
    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]

    return await _post(
        url=f"{url}/api/create",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.post("/api/copy")
@router.post("/api/copy/{url_idx}")
async def copy_model(
    request: Request,
    form_data: CopyModelForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS
        if form_data.source in models:
            url_idx = models[form_data.source]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.source),
            )

    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

    r = None
    try:
        r = _sync_request(
            "POST",
            f"{url}/api/copy",
            key=key,
            user=user,
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()
        log.debug("Copy result: %s", r.text)
        return True
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


@router.delete("/api/delete")
@router.delete("/api/delete/{url_idx}")
async def delete_model(
    request: Request,
    form_data: ModelNameForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        await get_all_models(request, user=user)
        models = request.app.state.OLLAMA_MODELS
        if form_data.name in models:
            url_idx = models[form_data.name]["urls"][0]
        else:
            raise HTTPException(
                status_code=400,
                detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
            )

    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

    r = None
    try:
        r = _sync_request(
            "DELETE",
            f"{url}/api/delete",
            key=key,
            user=user,
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()
        log.debug("Delete result: %s", r.text)
        return True
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


@router.post("/api/show")
async def show_model_info(
    request: Request, form_data: ModelNameForm, user=Depends(get_verified_user)
):
    await get_all_models(request, user=user)
    models = request.app.state.OLLAMA_MODELS

    if form_data.name not in models:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.MODEL_NOT_FOUND(form_data.name),
        )

    url_idx = _secrets.choice(models[form_data.name]["urls"])
    url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

    r = None
    try:
        r = _sync_request(
            "POST",
            f"{url}/api/show",
            key=key,
            user=user,
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


# ---------------------------------------------------------------------------
# Ollama-native endpoints — embeddings
# ---------------------------------------------------------------------------


@router.post("/api/embed")
@router.post("/api/embed/{url_idx}")
async def embed(
    request: Request,
    form_data: GenerateEmbedForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    log.info("embed: model=%s", form_data.model)

    url, url_idx, _ = await _resolve_url_and_config(
        request, form_data.model, url_idx
    )
    key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

    r = None
    try:
        r = _sync_request(
            "POST",
            f"{url}/api/embed",
            key=key,
            user=user,
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


@router.post("/api/embeddings")
@router.post("/api/embeddings/{url_idx}")
async def embeddings(
    request: Request,
    form_data: GenerateEmbeddingsForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    log.info("embeddings: model=%s", form_data.model)

    url, url_idx, _ = await _resolve_url_and_config(
        request, form_data.model, url_idx
    )
    key = _api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS)

    r = None
    try:
        r = _sync_request(
            "POST",
            f"{url}/api/embeddings",
            key=key,
            user=user,
            data=form_data.model_dump_json(exclude_none=True).encode(),
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.exception(exc)
        _raise_from_sync(r, exc)


# ---------------------------------------------------------------------------
# Ollama-native endpoints — generation & chat
# ---------------------------------------------------------------------------


@router.post("/api/generate")
@router.post("/api/generate/{url_idx}")
async def generate_completion(
    request: Request,
    form_data: GenerateCompletionForm,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    url, url_idx, ac = await _resolve_url_and_config(
        request, form_data.model, url_idx
    )

    # Strip prefix before forwarding to backend
    prefix_id = ac.get("prefix_id")
    if prefix_id:
        form_data.model = form_data.model.replace(f"{prefix_id}.", "")

    return await _post(
        url=f"{url}/api/generate",
        payload=form_data.model_dump_json(exclude_none=True).encode(),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.post("/api/chat")
@router.post("/api/chat/{url_idx}")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
):
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    metadata = form_data.pop("metadata", None)

    try:
        form_data = GenerateChatCompletionForm(**form_data)
    except Exception as exc:
        log.exception(exc)
        raise HTTPException(status_code=400, detail=str(exc))

    payload = form_data.model_dump(exclude_none=True)
    payload.pop("metadata", None)

    # --- model resolution & access control ---
    payload = _apply_model_overrides_chat(payload, metadata, user, bypass_filter)

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await _get_ollama_url(request, payload["model"], url_idx)
    ac = _api_config(request, url_idx, url)

    prefix_id = ac.get("prefix_id")
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await _post(
        url=f"{url}/api/chat",
        payload=orjson.dumps(payload),
        stream=form_data.stream,
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        content_type="application/x-ndjson",
        user=user,
    )


# ---------------------------------------------------------------------------
# OpenAI-compatible layer
# ---------------------------------------------------------------------------


@router.post("/v1/completions")
@router.post("/v1/completions/{url_idx}")
async def generate_openai_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    try:
        form_data = OpenAICompletionForm(**form_data)
    except Exception as exc:
        log.exception(exc)
        raise HTTPException(status_code=400, detail=str(exc))

    payload = form_data.model_dump(exclude_none=True, exclude=["metadata"])
    payload.pop("metadata", None)

    model_id = form_data.model
    if ":" not in model_id:
        model_id = f"{model_id}:latest"

    payload = _apply_model_overrides_openai(payload, model_id, user)

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await _get_ollama_url(request, payload["model"], url_idx)
    ac = _api_config(request, url_idx, url)

    prefix_id = ac.get("prefix_id")
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await _post(
        url=f"{url}/v1/completions",
        payload=orjson.dumps(payload),
        stream=payload.get("stream", False),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.post("/v1/chat/completions")
@router.post("/v1/chat/completions/{url_idx}")
async def generate_openai_chat_completion(
    request: Request,
    form_data: dict,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    metadata = form_data.pop("metadata", None)

    try:
        completion_form = OpenAIChatCompletionForm(**form_data)
    except Exception as exc:
        log.exception(exc)
        raise HTTPException(status_code=400, detail=str(exc))

    payload = completion_form.model_dump(exclude_none=True, exclude=["metadata"])
    payload.pop("metadata", None)

    model_id = completion_form.model
    if ":" not in model_id:
        model_id = f"{model_id}:latest"

    payload = _apply_model_overrides_openai(
        payload, model_id, user, metadata=metadata
    )

    if ":" not in payload["model"]:
        payload["model"] = f"{payload['model']}:latest"

    url, url_idx = await _get_ollama_url(request, payload["model"], url_idx)
    ac = _api_config(request, url_idx, url)

    prefix_id = ac.get("prefix_id")
    if prefix_id:
        payload["model"] = payload["model"].replace(f"{prefix_id}.", "")

    return await _post(
        url=f"{url}/v1/chat/completions",
        payload=orjson.dumps(payload),
        stream=payload.get("stream", False),
        key=_api_key(url_idx, url, _cfg(request).OLLAMA_API_CONFIGS),
        user=user,
    )


@router.get("/v1/models")
@router.get("/v1/models/{url_idx}")
async def get_openai_models(
    request: Request,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    if url_idx is None:
        model_list = await get_all_models(request, user=user)
        models = [
            {
                "id": m["model"],
                "object": "model",
                "created": int(time.time()),
                "owned_by": "openai",
            }
            for m in model_list["models"]
        ]
    else:
        url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
        r = None
        try:
            r = _sync_request("GET", f"{url}/api/tags")
            r.raise_for_status()

            raw = r.json()
            models = [
                {
                    "id": m["model"],
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "openai",
                }
                for m in raw.get("models", [])
            ]
        except Exception as exc:
            log.exception(exc)
            _raise_from_sync(r, exc)

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        filtered = []
        for model in models:
            info = Models.get_model_by_id(model["id"])
            if info and (
                user.id == info.user_id
                or has_access(user.id, type="read", access_control=info.access_control)
            ):
                filtered.append(model)
        models = filtered

    return {"data": models, "object": "list"}


# ---------------------------------------------------------------------------
# Access-control / model-override helpers (shared by chat & OpenAI layers)
# ---------------------------------------------------------------------------


def _apply_model_overrides_chat(
    payload: dict,
    metadata: Optional[dict],
    user: UserModel,
    bypass_filter: bool,
) -> dict:
    """Apply model params, system prompts, and access control for /api/chat."""
    model_id = payload["model"]
    info = Models.get_model_by_id(model_id)

    if info:
        if info.base_model_id:
            payload["model"] = info.base_model_id

        params = info.params.model_dump()
        if params:
            if payload.get("options") is None:
                payload["options"] = {}
            payload["options"] = apply_model_params_to_body_ollama(
                params, payload["options"]
            )
            payload = apply_model_system_prompt_to_body(params, payload, metadata, user)

        if not bypass_filter and user.role == "user":
            if not (
                user.id == info.user_id
                or has_access(user.id, type="read", access_control=info.access_control)
            ):
                raise HTTPException(status_code=403, detail="Model not found")

    elif not bypass_filter:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Model not found")

    return payload


def _apply_model_overrides_openai(
    payload: dict,
    model_id: str,
    user: UserModel,
    metadata: Optional[dict] = None,
) -> dict:
    """Apply model params, system prompts, and access control for /v1/ endpoints."""
    info = Models.get_model_by_id(model_id)

    if info:
        if info.base_model_id:
            payload["model"] = info.base_model_id

        params = info.params.model_dump()
        if params:
            payload = apply_model_params_to_body_openai(params, payload)
            if metadata is not None:
                payload = apply_model_system_prompt_to_body(
                    params, payload, metadata, user
                )

        if user.role == "user":
            if not (
                user.id == info.user_id
                or has_access(user.id, type="read", access_control=info.access_control)
            ):
                raise HTTPException(status_code=403, detail="Model not found")
    else:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Model not found")

    return payload


# ---------------------------------------------------------------------------
# HuggingFace download / upload
# ---------------------------------------------------------------------------


def _parse_huggingface_url(hf_url: str) -> Optional[str]:
    """Extract the filename component from a HuggingFace (or GitHub) URL."""
    try:
        return urlparse(hf_url).path.split("/")[-1]
    except (ValueError, IndexError):
        return None


async def _download_file_stream(
    ollama_url: str,
    file_url: str,
    file_path: str,
    file_name: str,
    chunk_size: int = 1024 * 1024,
):
    """Stream-download *file_url* to *file_path*, yielding SSE progress events.
    On completion, POST the file as a blob to Ollama and clean up."""
    current_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

    headers = {"Range": f"bytes={current_size}-"} if current_size > 0 else {}
    timeout = aiohttp.ClientTimeout(total=600)
    session = await get_client_session()

    async with session.get(file_url, headers=headers, timeout=timeout) as resp:
        total_size = int(resp.headers.get("content-length", 0)) + current_size

        with open(file_path, "ab+") as f:
            async for chunk in resp.content.iter_chunked(chunk_size):
                current_size += len(chunk)
                f.write(chunk)

                done = current_size == total_size
                progress = round((current_size / total_size) * 100, 2)
                yield f'data: {{"progress": {progress}, "completed": {current_size}, "total": {total_size}}}\n\n'

            if done:
                f.seek(0)
                hashed = calculate_sha256(f, chunk_size)
                f.seek(0)

                blob_resp = requests.post(
                    f"{ollama_url}/api/blobs/sha256:{hashed}", data=f
                )
                if blob_resp.ok:
                    res = {
                        "done": done,
                        "blob": f"sha256:{hashed}",
                        "name": file_name,
                    }
                    os.remove(file_path)
                    yield f"data: {orjson.dumps(res).decode()}\n\n"
                else:
                    raise RuntimeError(
                        "Ollama: Could not create blob, Please try again."
                    )


@router.post("/models/download")
@router.post("/models/download/{url_idx}")
async def download_model(
    request: Request,
    form_data: UrlForm,
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    allowed_hosts = ("https://huggingface.co/", "https://github.com/")
    if not form_data.url.startswith(allowed_hosts):
        raise HTTPException(
            status_code=400,
            detail="Invalid file_url. Only URLs from allowed hosts are permitted.",
        )

    if url_idx is None:
        url_idx = 0

    ollama_url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    file_name = _parse_huggingface_url(form_data.url)

    if not file_name:
        return None

    file_path = os.path.join(UPLOAD_DIR, file_name)
    return StreamingResponse(
        _download_file_stream(ollama_url, form_data.url, file_path, file_name),
    )


@router.post("/models/upload")
@router.post("/models/upload/{url_idx}")
async def upload_model(
    request: Request,
    file: UploadFile = File(...),
    url_idx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    if url_idx is None:
        url_idx = 0

    ollama_url = _cfg(request).OLLAMA_BASE_URLS[url_idx]
    file_path = os.path.join(UPLOAD_DIR, os.path.basename(file.filename))
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    # Phase 1: Save uploaded file to disk
    chunk_size = 2 * 1024 * 1024  # 2 MB
    with open(file_path, "wb") as out_f:
        while True:
            chunk = file.file.read(chunk_size)
            if not chunk:
                break
            out_f.write(chunk)

    async def _file_process_stream():
        nonlocal ollama_url
        total_size = os.path.getsize(file_path)
        log.info("Upload total size: %d bytes", total_size)

        try:
            # Phase 2: SHA-256 hash + SSE progress
            file_hash = calculate_sha256(file_path, chunk_size)
            log.info("Upload hash: %s", file_hash)

            with open(file_path, "rb") as f:
                bytes_read = 0
                while chunk := f.read(chunk_size):
                    bytes_read += len(chunk)
                    progress = round(bytes_read / total_size * 100, 2)
                    msg = {
                        "progress": progress,
                        "total": total_size,
                        "completed": bytes_read,
                    }
                    yield f"data: {orjson.dumps(msg).decode()}\n\n"

            # Phase 3: POST blob to Ollama
            with open(file_path, "rb") as f:
                blob_resp = requests.post(
                    f"{ollama_url}/api/blobs/sha256:{file_hash}", data=f
                )

            if blob_resp.ok:
                log.info("Blob uploaded to /api/blobs")
                os.remove(file_path)

                model_name, _ = os.path.splitext(file.filename)
                log.info("Creating model: %s", model_name)

                create_payload = {
                    "model": model_name,
                    "files": {file.filename: f"sha256:{file_hash}"},
                }
                log.info("Model payload: %s", create_payload)

                create_resp = requests.post(
                    url=f"{ollama_url}/api/create",
                    headers={"Content-Type": "application/json"},
                    data=orjson.dumps(create_payload),
                )

                if create_resp.ok:
                    log.info("Model created successfully")
                    done_msg = {
                        "done": True,
                        "blob": f"sha256:{file_hash}",
                        "name": file.filename,
                        "model_created": model_name,
                    }
                    yield f"data: {orjson.dumps(done_msg).decode()}\n\n"
                else:
                    raise Exception(
                        f"Failed to create model in Ollama. {create_resp.text}"
                    )
            else:
                raise Exception("Ollama: Could not create blob, Please try again.")

        except Exception as exc:
            yield f"data: {orjson.dumps({'error': str(exc)}).decode()}\n\n"

    return StreamingResponse(_file_process_stream(), media_type="text/event-stream")
