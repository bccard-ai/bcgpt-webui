"""
BCGPT OpenAI-Compatible Proxy Router
=====================================

Clean rewrite of the OpenAI-compatible API proxy. Provides multi-connection
support, provider detection, model registry caching, chat completions with
streaming SSE, speech synthesis, and generic proxy pass-through.

Public endpoints (unchanged from prior version):
    GET  /config
    POST /config/update
    POST /audio/speech
    GET  /models
    GET  /models/{url_idx}
    POST /verify
    POST /chat/completions
    ANY  /{path:path}  (generic proxy)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Optional

import aiohttp
import orjson
import requests as _sync_requests  # sync only for speech caching
from aiocache import cached
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from starlette.background import BackgroundTask

from bcgpt.config import CACHE_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import (
    AIOHTTP_CLIENT_TIMEOUT,
    AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
    BYPASS_MODEL_ACCESS_CONTROL,
    ENABLE_FORWARD_USER_INFO_HEADERS,
    SRC_LOG_LEVELS,
)
from bcgpt.models import Models
from bcgpt.models import UserModel
from bcgpt.utils import get_admin_user, get_verified_user, has_access
from bcgpt.utils.http_client import get_client_session
from bcgpt.utils.misc import convert_logit_bias_input_to_json
from bcgpt.utils.openai_reasoning import (
    is_reasoning_model,
    transform_reasoning_payload,
)
from bcgpt.utils.payload import (
    apply_model_params_to_body_openai,
    apply_model_system_prompt_to_body,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["OPENAI"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Model families filtered from the OpenAI model list (non-chat helpers).
_OPENAI_EXCLUDED_MODEL_SUBSTRINGS = (
    "babbage",
    "dall-e",
    "davinci",
    # NOTE: "embedding" intentionally kept — embedding models should appear
    # in the aggregated model list for RAG / embedding selectors.
    "moderation",
    "tts",
    "whisper",
)

_SPEECH_CACHE_DIR = CACHE_DIR / "audio" / "speech"

# ---------------------------------------------------------------------------
# Provider detection
# ---------------------------------------------------------------------------

_PROVIDER_HOST_MAP: dict[str, str] = {
    "api.openai.com": "openai",
    "api.deepseek.com": "deepseek",
    "api.perplexity.ai": "perplexity",
    "open.bigmodel.cn": "glm",
    "generativelanguage.googleapis.com": "gemini",
    "api.anthropic.com": "claude",
}


def detect_provider(url: str) -> str:
    """Return a provider identifier from a base URL."""
    lowered = url.lower()
    for host, provider in _PROVIDER_HOST_MAP.items():
        if host in lowered:
            return provider
    return "openai"


# ---------------------------------------------------------------------------
# Header helpers
# ---------------------------------------------------------------------------


def _auth_header(key: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"} if key else {}


def _user_info_headers(user: UserModel | None) -> dict[str, str]:
    if not ENABLE_FORWARD_USER_INFO_HEADERS or not user:
        return {}
    return {
        "X-BCGPT-User-Name": user.name,
        "X-BCGPT-User-Id": user.id,
        "X-BCGPT-User-Email": user.email,
        "X-BCGPT-User-Role": user.role,
    }


def _openrouter_headers(url: str) -> dict[str, str]:
    if "openrouter.ai" not in url:
        return {}
    return {
        "HTTP-Referer": "https://BCGPT.com/",
        "X-Title": "BCGPT",
    }


# ---------------------------------------------------------------------------
# Connection config helper
# ---------------------------------------------------------------------------


def _get_api_config(
    configs: dict, urls: list[str], idx: int
) -> dict:
    """Resolve per-connection config (supports legacy URL-keyed configs)."""
    url = urls[idx] if idx < len(urls) else ""
    return configs.get(str(idx), configs.get(url, {}))


def _sync_keys_to_urls(config: Any) -> None:
    """Ensure OPENAI_API_KEYS length matches OPENAI_API_BASE_URLS."""
    urls = config.OPENAI_API_BASE_URLS
    keys = config.OPENAI_API_KEYS
    n_urls, n_keys = len(urls), len(keys)
    if n_keys == n_urls:
        return
    if n_keys > n_urls:
        config.OPENAI_API_KEYS = keys[:n_urls]
    else:
        config.OPENAI_API_KEYS = keys + [""] * (n_urls - n_keys)


# ---------------------------------------------------------------------------
# Shared GET request
# ---------------------------------------------------------------------------


async def _fetch_json(
    url: str,
    *,
    key: str | None = None,
    user: UserModel | None = None,
    timeout: int | None = None,
) -> dict | list | None:
    """Perform an async GET and return parsed JSON (or None on failure)."""
    session = await get_client_session()
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=timeout),
            headers={
                **_auth_header(key),
                **_user_info_headers(user),
            },
        ) as resp:
            return await resp.json()
    except Exception as exc:
        log.error("Connection error: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Streaming response cleanup
# ---------------------------------------------------------------------------


async def _close_response(response: aiohttp.ClientResponse | None, _: Any = None):
    if response:
        response.close()


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


# ======================== Config endpoints ================================


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    return {
        "ENABLE_OPENAI_API": request.app.state.config.ENABLE_OPENAI_API,
        "OPENAI_API_BASE_URLS": request.app.state.config.OPENAI_API_BASE_URLS,
        "OPENAI_API_KEYS": request.app.state.config.OPENAI_API_KEYS,
        "OPENAI_API_CONFIGS": request.app.state.config.OPENAI_API_CONFIGS,
    }


class OpenAIConfigForm(BaseModel):
    ENABLE_OPENAI_API: Optional[bool] = None
    OPENAI_API_BASE_URLS: list[str]
    OPENAI_API_KEYS: list[str]
    OPENAI_API_CONFIGS: dict


@router.post("/config/update")
async def update_config(
    request: Request, form_data: OpenAIConfigForm, user=Depends(get_admin_user)
):
    cfg = request.app.state.config
    cfg.ENABLE_OPENAI_API = form_data.ENABLE_OPENAI_API
    cfg.OPENAI_API_BASE_URLS = form_data.OPENAI_API_BASE_URLS
    cfg.OPENAI_API_KEYS = form_data.OPENAI_API_KEYS
    _sync_keys_to_urls(cfg)

    cfg.OPENAI_API_CONFIGS = form_data.OPENAI_API_CONFIGS
    # Prune configs whose key is out of range
    valid_keys = set(map(str, range(len(cfg.OPENAI_API_BASE_URLS))))
    cfg.OPENAI_API_CONFIGS = {
        k: v for k, v in cfg.OPENAI_API_CONFIGS.items() if k in valid_keys
    }

    return {
        "ENABLE_OPENAI_API": cfg.ENABLE_OPENAI_API,
        "OPENAI_API_BASE_URLS": cfg.OPENAI_API_BASE_URLS,
        "OPENAI_API_KEYS": cfg.OPENAI_API_KEYS,
        "OPENAI_API_CONFIGS": cfg.OPENAI_API_CONFIGS,
    }


# ======================== Speech synthesis ================================


@router.post("/audio/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    urls = request.app.state.config.OPENAI_API_BASE_URLS

    # Locate the OpenAI connection
    try:
        idx = urls.index("https://api.openai.com/v1")
    except ValueError:
        raise HTTPException(status_code=401, detail=ERROR_MESSAGES.OPENAI_NOT_FOUND)

    body = await request.body()
    name = hashlib.sha256(body).hexdigest()

    _SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    file_path = _SPEECH_CACHE_DIR / f"{name}.mp3"
    body_path = _SPEECH_CACHE_DIR / f"{name}.json"

    # Serve from cache
    if file_path.is_file():
        return FileResponse(file_path)

    url = urls[idx]
    key = request.app.state.config.OPENAI_API_KEYS[idx]

    resp = None
    try:
        resp = _sync_requests.post(
            url=f"{url}/audio/speech",
            data=body,
            headers={
                "Content-Type": "application/json",
                **_auth_header(key),
                **_openrouter_headers(url),
                **_user_info_headers(user),
            },
            stream=True,
        )
        resp.raise_for_status()

        with open(file_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        with open(body_path, "w") as f:
            orjson.dump(orjson.loads(body), f)

        return FileResponse(file_path)

    except Exception as exc:
        log.exception("Speech synthesis error: %s", exc)
        detail = None
        if resp is not None:
            try:
                res = resp.json()
                if "error" in res:
                    detail = f"External: {res['error']}"
            except Exception:
                detail = f"External: {exc}"

        raise HTTPException(
            status_code=resp.status_code if resp else 500,
            detail=detail or "BCGPT: Server Connection Error",
        )


# ======================== Model registry ==================================


async def _fetch_all_provider_models(
    request: Request, user: UserModel
) -> list[dict | list | None]:
    """Collect raw model-list responses from every configured connection."""
    cfg = request.app.state.config
    if not cfg.ENABLE_OPENAI_API:
        return []

    _sync_keys_to_urls(cfg)
    urls = cfg.OPENAI_API_BASE_URLS
    keys = cfg.OPENAI_API_KEYS
    configs = cfg.OPENAI_API_CONFIGS

    tasks: list[asyncio.Task | asyncio.Future] = []

    for idx, url in enumerate(urls):
        api_cfg = _get_api_config(configs, urls, idx)

        # Not configured at all → fetch normally
        if str(idx) not in configs and url not in configs:
            tasks.append(
                asyncio.ensure_future(
                    _fetch_json(
                        f"{url}/models",
                        key=keys[idx],
                        user=user,
                        timeout=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
                    )
                )
            )
            continue

        enabled = api_cfg.get("enable", True)
        model_ids = api_cfg.get("model_ids", [])

        if not enabled:
            tasks.append(asyncio.ensure_future(asyncio.sleep(0, None)))
        elif model_ids:
            provider = detect_provider(url)
            synthetic = {
                "object": "list",
                "data": [
                    {
                        "id": mid,
                        "name": mid,
                        "owned_by": provider,
                        "openai": {"id": mid},
                        "urlIdx": idx,
                    }
                    for mid in model_ids
                ],
            }
            tasks.append(asyncio.ensure_future(asyncio.sleep(0, synthetic)))
        else:
            tasks.append(
                asyncio.ensure_future(
                    _fetch_json(
                        f"{url}/models",
                        key=keys[idx],
                        user=user,
                        timeout=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST,
                    )
                )
            )

    responses = await asyncio.gather(*tasks)

    # Post-process: apply prefix_id and tags from per-connection config
    for idx, resp in enumerate(responses):
        if not resp:
            continue
        api_cfg = _get_api_config(configs, urls, idx)
        prefix_id = api_cfg.get("prefix_id")
        tags = api_cfg.get("tags", [])

        items = resp if isinstance(resp, list) else resp.get("data", [])
        if prefix_id:
            for m in items:
                m["id"] = f"{prefix_id}.{m['id']}"
        if tags:
            for m in items:
                m["tags"] = tags

    return responses


def _extract_data(response: Any) -> list | None:
    """Normalise a provider response into a plain list of model dicts."""
    if response and "data" in response:
        return response["data"]
    if isinstance(response, list):
        return response
    return None


def _is_openai_chat_model(url: str, model_id: str) -> bool:
    """True for models we want to expose (filters out OpenAI helper models)."""
    if "api.openai.com" not in url:
        return True
    return not any(substr in model_id for substr in _OPENAI_EXCLUDED_MODEL_SUBSTRINGS)


def _merge_model_lists(
    responses: list, urls: list[str]
) -> list[dict]:
    """Flatten and annotate provider model lists into a single merged list."""
    merged: list[dict] = []
    for idx, models in enumerate(responses):
        if models is None or (isinstance(models, dict) and "error" in models):
            continue
        url = urls[idx]
        provider = detect_provider(url)
        for m in models:
            mid = m.get("id") or m.get("name")
            if not mid:
                continue
            if not _is_openai_chat_model(url, mid):
                continue
            merged.append(
                {
                    **m,
                    "name": m.get("name", mid),
                    "owned_by": provider,
                    "openai": m,
                    "urlIdx": idx,
                }
            )
    return merged


@cached(ttl=30)
async def get_all_models(request: Request, user: UserModel) -> dict[str, list]:
    """Aggregate models from all connections with a 30-second cache."""
    log.info("get_all_models()")

    cfg = request.app.state.config
    if not cfg.ENABLE_OPENAI_API:
        return {"data": []}

    responses = await _fetch_all_provider_models(request, user)
    extracted = [_extract_data(r) for r in responses]

    urls = cfg.OPENAI_API_BASE_URLS
    models_list = _merge_model_lists(extracted, urls)
    result = {"data": models_list}

    request.app.state.OPENAI_MODELS = {m["id"]: m for m in models_list}
    return result


async def _filter_models_by_access(models: dict, user: UserModel) -> list:
    """Keep only models the user is allowed to read."""
    filtered: list[dict] = []
    for model in models.get("data", []):
        info = Models.get_model_by_id(model["id"])
        if info and (
            user.id == info.user_id
            or has_access(user.id, type="read", access_control=info.access_control)
        ):
            filtered.append(model)
    return filtered


@router.get("/models")
@router.get("/models/{url_idx}")
async def get_models(
    request: Request,
    url_idx: Optional[int] = None,
    user=Depends(get_verified_user),
):
    cfg = request.app.state.config

    if url_idx is None:
        models = await get_all_models(request, user=user)
    else:
        url = cfg.OPENAI_API_BASE_URLS[url_idx]
        key = cfg.OPENAI_API_KEYS[url_idx]

        session = await get_client_session()
        try:
            async with session.get(
                f"{url}/models",
                timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
                headers={
                    **_auth_header(key),
                    "Content-Type": "application/json",
                    **_user_info_headers(user),
                },
            ) as r:
                if r.status != 200:
                    error_detail = f"HTTP Error: {r.status}"
                    try:
                        res = await r.json()
                        if "error" in res:
                            error_detail = f"External Error: {res['error']}"
                    except Exception:
                        pass
                    log.error(
                        "OpenAI provider error (url_idx=%s): %s", url_idx, error_detail
                    )
                    raise HTTPException(status_code=500, detail=error_detail)

                response_data = await r.json()

                if "api.openai.com" in url:
                    response_data["data"] = [
                        m
                        for m in response_data.get("data", [])
                        if not any(s in m["id"] for s in _OPENAI_EXCLUDED_MODEL_SUBSTRINGS)
                    ]

                models = response_data

        except HTTPException:
            raise
        except aiohttp.ClientError as exc:
            log.error("Client error: %s", exc)
            raise HTTPException(
                status_code=500, detail="BCGPT: Server Connection Error"
            )
        except Exception as exc:
            log.exception("Unexpected error: %s", exc)
            raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")

    if user.role == "user" and not BYPASS_MODEL_ACCESS_CONTROL:
        models["data"] = await _filter_models_by_access(models, user)

    return models


# ======================== Connection verification =========================


class ConnectionVerificationForm(BaseModel):
    url: str
    key: str


@router.post("/verify")
async def verify_connection(
    form_data: ConnectionVerificationForm, user=Depends(get_admin_user)
):
    session = await get_client_session()
    try:
        async with session.get(
            f"{form_data.url}/models",
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST),
            headers={
                **_auth_header(form_data.key),
                "Content-Type": "application/json",
                **_user_info_headers(user),
            },
        ) as r:
            if r.status != 200:
                error_detail = f"HTTP Error: {r.status}"
                try:
                    res = await r.json()
                    if "error" in res:
                        error_detail = f"External Error: {res['error']}"
                except Exception:
                    pass
                log.error("OpenAI connection verify error: %s", error_detail)
                raise HTTPException(status_code=500, detail=error_detail)

            return await r.json()

    except HTTPException:
        raise
    except aiohttp.ClientError as exc:
        log.error("Client error: %s", exc)
        raise HTTPException(status_code=500, detail="BCGPT: Server Connection Error")
    except Exception as exc:
        log.exception("Unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Unexpected error: {exc}")


# ======================== Chat completions =================================


async def _resolve_connection_index(
    request: Request, model_id: str, user: UserModel
) -> tuple[int, dict]:
    """Return (connection_index, model_meta) for a given model_id.

    Falls back to single-connection routing or registry refresh when the
    model is absent from the transient registry.
    """
    registry: dict = request.app.state.OPENAI_MODELS
    model = registry.get(model_id)

    if model:
        return model["urlIdx"], model

    urls = request.app.state.config.OPENAI_API_BASE_URLS

    # Single connection — route directly
    if len(urls) == 1:
        log.info(
            "Model '%s' not in OpenAI registry (size=%d); "
            "routing to the sole configured connection (idx=0)",
            model_id,
            len(registry),
        )
        return 0, {"id": model_id, "urlIdx": 0}

    # Multiple connections — refresh once then give up
    log.info("Model '%s' not in OpenAI registry; refreshing model list", model_id)
    try:
        await get_all_models(request, user=user)
    except Exception as exc:
        log.warning("OpenAI model registry refresh failed: %s", exc)

    model = registry.get(model_id)
    if model:
        return model["urlIdx"], model

    raise HTTPException(status_code=404, detail="Model not found")


def _prepare_chat_payload(
    payload: dict,
    model_id: str,
    user: UserModel,
    bypass_filter: bool,
) -> tuple[dict, str]:
    """Validate access, apply model params, and return (processed_payload, actual_model_id)."""
    model_info = Models.get_model_by_id(model_id)

    if model_info:
        if model_info.base_model_id:
            payload["model"] = model_info.base_model_id
            model_id = model_info.base_model_id

        params = model_info.params.model_dump()
        payload = apply_model_params_to_body_openai(params, payload)
        payload = apply_model_system_prompt_to_body(params, payload, None, user)

        if not bypass_filter and user.role == "user":
            if not (
                user.id == model_info.user_id
                or has_access(
                    user.id, type="read", access_control=model_info.access_control
                )
            ):
                raise HTTPException(status_code=403, detail="Model not found")
    elif not bypass_filter:
        if user.role != "admin":
            raise HTTPException(status_code=403, detail="Model not found")

    return payload, model_id


@router.post("/chat/completions")
async def generate_chat_completion(
    request: Request,
    form_data: dict,
    user=Depends(get_verified_user),
    bypass_filter: Optional[bool] = False,
):
    if BYPASS_MODEL_ACCESS_CONTROL:
        bypass_filter = True

    payload = {**form_data}
    metadata = payload.pop("metadata", None)
    model_id = form_data.get("model")

    payload, model_id = _prepare_chat_payload(payload, model_id, user, bypass_filter)

    idx, model_meta = await _resolve_connection_index(request, model_id, user)

    cfg = request.app.state.config
    api_config = _get_api_config(cfg.OPENAI_API_CONFIGS, cfg.OPENAI_API_BASE_URLS, idx)

    # Strip prefix_id from model name
    prefix = api_config.get("prefix_id")
    if prefix:
        payload["model"] = payload["model"].replace(f"{prefix}.", "")

    # Attach user context for pipeline models
    if "pipeline" in model_meta and model_meta.get("pipeline"):
        payload["user"] = {
            "name": user.name,
            "id": user.id,
            "email": user.email,
            "role": user.role,
        }

    url = cfg.OPENAI_API_BASE_URLS[idx]
    key = cfg.OPENAI_API_KEYS[idx]

    # Remove internal keys
    payload = {k: v for k, v in payload.items() if not k.startswith("__")}

    # Reasoning model payload transformation
    payload = transform_reasoning_payload(payload)
    if not is_reasoning_model(payload["model"]) and "api.openai.com" not in url:
        if "max_completion_tokens" in payload:
            payload["max_tokens"] = payload.pop("max_completion_tokens")

    if "max_tokens" in payload and "max_completion_tokens" in payload:
        del payload["max_tokens"]

    if "logit_bias" in payload:
        payload["logit_bias"] = orjson.loads(
            convert_logit_bias_input_to_json(payload["logit_bias"])
        )

    encoded_payload = orjson.dumps(payload)

    # ---- Send request ----
    r = None
    streaming = False
    parsed: Any = None

    try:
        session = await get_client_session()
        r = await session.request(
            method="POST",
            url=f"{url}/chat/completions",
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            data=encoded_payload,
            headers={
                **_auth_header(key),
                "Content-Type": "application/json",
                **_openrouter_headers(url),
                **_user_info_headers(user),
            },
        )

        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True
            return StreamingResponse(
                r.content,
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(_close_response, r),
            )

        try:
            parsed = await r.json()
        except Exception:
            parsed = await r.text()

        r.raise_for_status()
        return parsed

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Chat completion error: %s", exc)

        detail = None
        if isinstance(parsed, dict) and "error" in parsed:
            err = parsed["error"]
            detail = err.get("message", err) if isinstance(err, dict) else err
        elif isinstance(parsed, str):
            detail = parsed

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail or "BCGPT: Server Connection Error",
        )
    finally:
        if not streaming and r:
            r.close()


# ======================== Generic proxy ===================================


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(path: str, request: Request, user=Depends(get_verified_user)):
    """Pass-through proxy to the first configured OpenAI connection."""
    cfg = request.app.state.config
    idx = 0
    url = cfg.OPENAI_API_BASE_URLS[idx]
    key = cfg.OPENAI_API_KEYS[idx]

    body = await request.body()
    r = None
    streaming = False

    try:
        session = await get_client_session()
        r = await session.request(
            method=request.method,
            url=f"{url}/{path}",
            data=body,
            headers={
                **_auth_header(key),
                "Content-Type": "application/json",
                **_user_info_headers(user),
            },
        )
        r.raise_for_status()

        if "text/event-stream" in r.headers.get("Content-Type", ""):
            streaming = True
            return StreamingResponse(
                r.content,
                status_code=r.status,
                headers=dict(r.headers),
                background=BackgroundTask(_close_response, r),
            )

        return await r.json()

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Proxy error: %s", exc)

        detail = None
        if r is not None:
            try:
                res = await r.json()
                if "error" in res:
                    err = res["error"]
                    detail = (
                        f"External: {err['message']}"
                        if isinstance(err, dict) and "message" in err
                        else f"External: {err}"
                    )
            except Exception:
                detail = f"External: {exc}"

        raise HTTPException(
            status_code=r.status if r else 500,
            detail=detail or "BCGPT: Server Connection Error",
        )
    finally:
        if not streaming and r:
            r.close()
