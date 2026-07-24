"""Image generation configuration and generation router.

Provides endpoints for managing image generation settings across multiple
backends (OpenAI, AUTOMATIC1111, ComfyUI, Gemini), listing available models,
and generating images that are automatically persisted as uploaded files.
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import mimetypes
import re
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from pydantic import BaseModel

from bcgpt.config import CACHE_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import ENABLE_FORWARD_USER_INFO_HEADERS, SRC_LOG_LEVELS
from bcgpt.routers import upload_file
from bcgpt.utils import get_admin_user, get_verified_user
from bcgpt.utils.images.comfyui import (
    ComfyUIGenerateImageForm,
    ComfyUIWorkflow,
    comfyui_generate_image,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["IMAGES"])

IMAGE_CACHE_DIR = CACHE_DIR / "image" / "generations"
IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter()


# ---------------------------------------------------------------------------
# Config resolution helper
# ---------------------------------------------------------------------------


def _get_config_value(val):
    """Unwrap a PersistentConfig to its plain value, or return *val* as-is."""
    from bcgpt.config import PersistentConfig

    if isinstance(val, PersistentConfig):
        return val.value
    return val


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OpenAIConfigForm(BaseModel):
    """OpenAI image-generation backend settings."""

    OPENAI_API_BASE_URL: str
    OPENAI_API_KEY: str


class Automatic1111ConfigForm(BaseModel):
    """AUTOMATIC1111 / Stable Diffusion WebUI backend settings."""

    AUTOMATIC1111_BASE_URL: str
    AUTOMATIC1111_API_AUTH: str
    AUTOMATIC1111_CFG_SCALE: Optional[str | float | int] = None
    AUTOMATIC1111_SAMPLER: Optional[str] = None
    AUTOMATIC1111_SCHEDULER: Optional[str] = None


class ComfyUIConfigForm(BaseModel):
    """ComfyUI backend settings."""

    COMFYUI_BASE_URL: str
    COMFYUI_API_KEY: str
    COMFYUI_WORKFLOW: str
    COMFYUI_WORKFLOW_NODES: list[dict]


class GeminiConfigForm(BaseModel):
    """Gemini / Imagen backend settings."""

    GEMINI_API_BASE_URL: str
    GEMINI_API_KEY: str


class ConfigForm(BaseModel):
    """Full image-generation configuration payload."""

    enabled: bool
    engine: str
    prompt_generation: bool
    prompt_translation: bool
    prompt_expansion: bool
    openai: OpenAIConfigForm
    automatic1111: Automatic1111ConfigForm
    comfyui: ComfyUIConfigForm
    gemini: GeminiConfigForm


class ImageConfigForm(BaseModel):
    """Model / size / steps configuration for image generation."""

    MODEL: str
    IMAGE_SIZE: str
    IMAGE_STEPS: int


class GenerateImageForm(BaseModel):
    """Request body for image generation."""

    model: Optional[str] = None
    prompt: str
    size: Optional[str] = None
    n: int = 1
    negative_prompt: Optional[str] = None


# ---------------------------------------------------------------------------
# Config snapshot helpers
# ---------------------------------------------------------------------------


def _config_snapshot(config) -> dict:
    """Build a serialisable snapshot of every image-generation config field."""
    return {
        "enabled": _get_config_value(config.ENABLE_IMAGE_GENERATION),
        "engine": _get_config_value(config.IMAGE_GENERATION_ENGINE),
        "prompt_generation": _get_config_value(config.ENABLE_IMAGE_PROMPT_GENERATION),
        "prompt_translation": _get_config_value(config.ENABLE_IMAGE_PROMPT_TRANSLATION),
        "prompt_expansion": _get_config_value(config.ENABLE_IMAGE_PROMPT_EXPANSION),
        "openai": {
            "OPENAI_API_BASE_URL": _get_config_value(config.IMAGES_OPENAI_API_BASE_URL),
            "OPENAI_API_KEY": _get_config_value(config.IMAGES_OPENAI_API_KEY),
        },
        "automatic1111": {
            "AUTOMATIC1111_BASE_URL": _get_config_value(config.AUTOMATIC1111_BASE_URL),
            "AUTOMATIC1111_API_AUTH": _get_config_value(config.AUTOMATIC1111_API_AUTH),
            "AUTOMATIC1111_CFG_SCALE": _get_config_value(config.AUTOMATIC1111_CFG_SCALE),
            "AUTOMATIC1111_SAMPLER": _get_config_value(config.AUTOMATIC1111_SAMPLER),
            "AUTOMATIC1111_SCHEDULER": _get_config_value(config.AUTOMATIC1111_SCHEDULER),
        },
        "comfyui": {
            "COMFYUI_BASE_URL": _get_config_value(config.COMFYUI_BASE_URL),
            "COMFYUI_API_KEY": _get_config_value(config.COMFYUI_API_KEY),
            "COMFYUI_WORKFLOW": _get_config_value(config.COMFYUI_WORKFLOW),
            "COMFYUI_WORKFLOW_NODES": _get_config_value(config.COMFYUI_WORKFLOW_NODES),
        },
        "gemini": {
            "GEMINI_API_BASE_URL": _get_config_value(config.IMAGES_GEMINI_API_BASE_URL),
            "GEMINI_API_KEY": _get_config_value(config.IMAGES_GEMINI_API_KEY),
        },
    }


def _image_config_snapshot(config) -> dict:
    """Build a serialisable snapshot of model / size / steps."""
    return {
        "MODEL": _get_config_value(config.IMAGE_GENERATION_MODEL),
        "IMAGE_SIZE": _get_config_value(config.IMAGE_SIZE),
        "IMAGE_STEPS": _get_config_value(config.IMAGE_STEPS),
    }


# ---------------------------------------------------------------------------
# AUTOMATIC1111 auth helper
# ---------------------------------------------------------------------------


def get_automatic1111_api_auth(request: Request) -> str:
    """Return the ``Basic …`` authorization header value for AUTOMATIC1111.

    Returns an empty string when no auth is configured.
    """
    raw = request.app.state.config.AUTOMATIC1111_API_AUTH
    if not raw:
        return ""
    encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
    return f"Basic {encoded}"


# ---------------------------------------------------------------------------
# Image data loading helpers
# ---------------------------------------------------------------------------


def load_b64_image_data(b64_str: str) -> tuple[bytes, str] | None:
    """Decode a base64-encoded image string into ``(bytes, mime_type)``.

    Handles both raw base64 and data-URI format (``data:<mime>;base64,…``).
    Returns ``None`` on decode failure.
    """
    try:
        if "," in b64_str:
            header, encoded = b64_str.split(",", 1)
            mime_type = header.split(";")[0]
            img_data = base64.b64decode(encoded)
        else:
            mime_type = "image/png"
            img_data = base64.b64decode(b64_str)
        return img_data, mime_type
    except Exception as exc:
        log.exception("Error loading base64 image data: %s", exc)
        return None


def load_url_image_data(url: str, headers: dict | None = None) -> tuple[bytes, str] | None:
    """Fetch image bytes from *url* with SSRF-hardened settings.

    Redirects are disabled and a 15 s timeout is enforced.  The URL typically
    originates from a configured image backend (ComfyUI / AUTOMATIC1111), so
    the destination host is not IP-validated here.
    """
    try:
        r = requests.get(url, headers=headers, allow_redirects=False, timeout=15)
        r.raise_for_status()
        content_type = r.headers.get("content-type", "")
        if content_type.split("/")[0] == "image":
            return r.content, content_type
        log.error("URL does not point to an image: %s", url)
        return None
    except Exception as exc:
        log.exception("Error fetching image from URL: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Upload bridge helper
# ---------------------------------------------------------------------------


async def upload_image(
    request: Request,
    image_metadata: dict,
    image_data: bytes,
    content_type: str,
    user,
) -> str:
    """Persist generated image data as an uploaded file and return its URL path."""
    extension = mimetypes.guess_extension(content_type)
    file = UploadFile(
        file=io.BytesIO(image_data),
        filename=f"generated-image{extension}",
        headers={"content-type": content_type},
    )
    file_item = await upload_file(request, file, user, file_metadata=image_metadata)
    return request.app.url_path_for("get_file_content_by_id", id=file_item.id)


# ---------------------------------------------------------------------------
# Model management helpers
# ---------------------------------------------------------------------------


def set_image_model(request: Request, model: str) -> str:
    """Set the active image generation model.

    For AUTOMATIC1111 (or the default engine), this also pushes the model
    selection to the running AUTOMATIC1111 instance via its REST API.
    """
    log.info("Setting image model to %s", model)
    config = request.app.state.config
    config.IMAGE_GENERATION_MODEL = model

    engine = _get_config_value(config.IMAGE_GENERATION_ENGINE)
    if engine in ("", "automatic1111"):
        api_auth = get_automatic1111_api_auth(request)
        base_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
        r = requests.get(
            url=f"{base_url}/sdapi/v1/options",
            headers={"authorization": api_auth},
        )
        options = r.json()
        if model != options["sd_model_checkpoint"]:
            options["sd_model_checkpoint"] = model
            requests.post(
                url=f"{base_url}/sdapi/v1/options",
                json=options,
                headers={"authorization": api_auth},
            )
    return config.IMAGE_GENERATION_MODEL


def get_image_model(request: Request) -> str:
    """Return the current image generation model name.

    For AUTOMATIC1111 / default engine this queries the running instance.
    For other engines a sensible default is returned when no model is set.
    """
    config = request.app.state.config
    engine = _get_config_value(config.IMAGE_GENERATION_ENGINE)
    configured = _get_config_value(config.IMAGE_GENERATION_MODEL)

    if engine == "openai":
        return configured or "gpt-image-2"

    if engine == "gemini":
        return configured or "imagen-3.0-generate-002"

    if engine == "comfyui":
        return configured or ""

    # automatic1111 or empty (default)
    try:
        api_auth = get_automatic1111_api_auth(request)
        base_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
        r = requests.get(
            url=f"{base_url}/sdapi/v1/options",
            headers={"authorization": api_auth},
        )
        return r.json()["sd_model_checkpoint"]
    except Exception as exc:
        config.ENABLE_IMAGE_GENERATION = False
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(exc))


# ---------------------------------------------------------------------------
# Engine credential resolution
# ---------------------------------------------------------------------------


def _resolve_openai_credentials(config, model_name: str) -> tuple[str, str]:
    """Determine the OpenAI-compatible API URL and key for *model_name*.

    Checks the shared connection pool first, then falls back to the
    image-specific OpenAI settings.
    """
    api_url = None
    api_key = None

    # Try the shared model→connection mapping first
    openai_models = getattr(config, "OPENAI_MODELS", {}) if hasattr(config, "OPENAI_MODELS") else {}
    model_info = openai_models.get(model_name) if isinstance(openai_models, dict) else None

    if model_info:
        idx = model_info["urlIdx"]
        urls = config.OPENAI_API_BASE_URLS
        keys = config.OPENAI_API_KEYS
        if isinstance(urls, list) and isinstance(keys, list) and idx < len(urls) and idx < len(keys):
            api_url = urls[idx]
            api_key = keys[idx]

    # Scan shared connections for any valid pair
    if not api_url or not api_key:
        urls = config.OPENAI_API_BASE_URLS
        keys = config.OPENAI_API_KEYS
        if isinstance(urls, list) and isinstance(keys, list):
            for i in range(min(len(urls), len(keys))):
                if urls[i] and keys[i]:
                    api_url = urls[i]
                    api_key = keys[i]
                    break

    # Final fallback to image-specific settings
    if not api_url:
        api_url = _get_config_value(config.IMAGES_OPENAI_API_BASE_URL)
    if not api_key:
        api_key = _get_config_value(config.IMAGES_OPENAI_API_KEY)

    return api_url or "", api_key or ""


def _require_engine_credentials(engine: str, config) -> tuple[str, str]:
    """Validate and return ``(api_url, api_key)`` for the given *engine*.

    Raises HTTP 400 with a descriptive message when credentials are missing.
    """
    if engine == "openai":
        model_name = _get_config_value(config.IMAGE_GENERATION_MODEL) or "gpt-image-2"
        api_url, api_key = _resolve_openai_credentials(config, model_name)
        if not api_url or not api_key:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Image generation is not configured for model '{model_name}'. "
                    f"Please add a connection with the image generation model in "
                    f"Admin Settings > Connections, or set the API URL and Key in "
                    f"Admin Settings > Images."
                ),
            )
        return api_url, api_key

    if engine == "gemini":
        api_url = _get_config_value(config.IMAGES_GEMINI_API_BASE_URL)
        api_key = _get_config_value(config.IMAGES_GEMINI_API_KEY)
        if not api_url or not api_key:
            raise HTTPException(
                status_code=400,
                detail="Image generation is not configured. Please set the Gemini API Base URL and API Key in Admin Settings > Images.",
            )
        return api_url, api_key

    if engine == "comfyui":
        api_url = _get_config_value(config.COMFYUI_BASE_URL)
        if not api_url:
            raise HTTPException(
                status_code=400,
                detail="Image generation is not configured. Please set the ComfyUI Base URL in Admin Settings > Images.",
            )
        return api_url, ""

    # automatic1111 or empty (default)
    api_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
    if not api_url:
        raise HTTPException(
            status_code=400,
            detail="Image generation is not configured. Please set the Automatic1111 Base URL in Admin Settings > Images.",
        )
    return api_url, ""


# ---------------------------------------------------------------------------
# Engine verification
# ---------------------------------------------------------------------------


def _verify_automatic1111(config) -> None:
    """Probe the AUTOMATIC1111 options endpoint; raise on failure."""
    base_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
    auth_header = f"Basic {base64.b64encode(config.AUTOMATIC1111_API_AUTH.encode('utf-8')).decode('utf-8')}" if config.AUTOMATIC1111_API_AUTH else ""
    headers = {"authorization": auth_header} if auth_header else {}
    r = requests.get(url=f"{base_url}/sdapi/v1/options", headers=headers)
    r.raise_for_status()


def _verify_comfyui(config) -> None:
    """Probe the ComfyUI object_info endpoint; raise on failure."""
    base_url = _get_config_value(config.COMFYUI_BASE_URL)
    api_key = _get_config_value(config.COMFYUI_API_KEY)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else None
    r = requests.get(url=f"{base_url}/object_info", headers=headers)
    r.raise_for_status()


# ---------------------------------------------------------------------------
# Generation dispatch
# ---------------------------------------------------------------------------


async def _generate_openai(request: Request, form: GenerateImageForm, user, config) -> list[dict]:
    """Generate images via the OpenAI images API."""
    api_url, api_key = _require_engine_credentials("openai", config)

    headers: dict[str, str] = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if ENABLE_FORWARD_USER_INFO_HEADERS:
        headers["X-BCGPT-User-Name"] = user.name
        headers["X-BCGPT-User-Id"] = user.id
        headers["X-BCGPT-User-Email"] = user.email
        headers["X-BCGPT-User-Role"] = user.role

    model_name = _get_config_value(config.IMAGE_GENERATION_MODEL) or "gpt-image-2"
    size = form.size or _get_config_value(config.IMAGE_SIZE)

    data: dict = {
        "model": model_name,
        "prompt": form.prompt,
        "n": form.n,
        "size": size,
    }

    # Non-GPT-image models return base64; GPT-image models require >= 1024
    if not model_name.startswith("gpt-image"):
        data["response_format"] = "b64_json"
    else:
        w, h = map(int, size.split("x"))
        if w < 1024 or h < 1024:
            data["size"] = "1024x1024"

    r = await asyncio.to_thread(
        requests.post,
        url=f"{api_url}/images/generations",
        json=data,
        headers=headers,
    )
    r.raise_for_status()
    res = r.json()

    images = []
    for image in res["data"]:
        if image_url := image.get("url"):
            result = load_url_image_data(image_url, headers)
        else:
            result = load_b64_image_data(image["b64_json"])
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to load generated image data")
        image_data, content_type = result
        url = await upload_image(request, data, image_data, content_type, user)
        images.append({"url": url})
    return images


async def _generate_gemini(request: Request, form: GenerateImageForm, user, config) -> list[dict]:
    """Generate images via the Gemini / Imagen API."""
    _require_engine_credentials("gemini", config)

    api_key = _get_config_value(config.IMAGES_GEMINI_API_KEY)
    base_url = _get_config_value(config.IMAGES_GEMINI_API_BASE_URL)
    model = get_image_model(request)

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    data = {
        "instances": {"prompt": form.prompt},
        "parameters": {
            "sampleCount": form.n,
            "outputOptions": {"mimeType": "image/png"},
        },
    }

    r = await asyncio.to_thread(
        requests.post,
        url=f"{base_url}/models/{model}:predict",
        json=data,
        headers=headers,
    )
    r.raise_for_status()
    res = r.json()

    images = []
    for prediction in res["predictions"]:
        result = load_b64_image_data(prediction["bytesBase64Encoded"])
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to decode Gemini image data")
        image_data, content_type = result
        url = await upload_image(request, data, image_data, content_type, user)
        images.append({"url": url})
    return images


async def _generate_comfyui(request: Request, form: GenerateImageForm, user, config) -> list[dict]:
    """Generate images via ComfyUI."""
    _require_engine_credentials("comfyui", config)

    width, height = map(int, _get_config_value(config.IMAGE_SIZE).split("x"))
    data: dict = {
        "prompt": form.prompt,
        "width": width,
        "height": height,
        "n": form.n,
    }
    if config.IMAGE_STEPS is not None:
        data["steps"] = _get_config_value(config.IMAGE_STEPS)
    if form.negative_prompt is not None:
        data["negative_prompt"] = form.negative_prompt

    comfyui_form = ComfyUIGenerateImageForm(
        **{
            "workflow": ComfyUIWorkflow(
                workflow=_get_config_value(config.COMFYUI_WORKFLOW),
                nodes=_get_config_value(config.COMFYUI_WORKFLOW_NODES),
            ),
            **data,
        }
    )

    res = await comfyui_generate_image(
        _get_config_value(config.IMAGE_GENERATION_MODEL),
        comfyui_form,
        user.id,
        _get_config_value(config.COMFYUI_BASE_URL),
        _get_config_value(config.COMFYUI_API_KEY),
    )
    log.debug("ComfyUI response: %s", res)

    api_key = _get_config_value(config.COMFYUI_API_KEY)
    fetch_headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

    images = []
    for image in res["data"]:
        result = load_url_image_data(image["url"], fetch_headers)
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to load ComfyUI image data")
        image_data, content_type = result
        url = await upload_image(
            request, comfyui_form.model_dump(exclude_none=True), image_data, content_type, user
        )
        images.append({"url": url})
    return images


async def _generate_automatic1111(
    request: Request, form: GenerateImageForm, user, config
) -> list[dict]:
    """Generate images via AUTOMATIC1111 / Stable Diffusion WebUI."""
    _require_engine_credentials("automatic1111", config)

    if form.model:
        set_image_model(request, form.model)

    width, height = map(int, _get_config_value(config.IMAGE_SIZE).split("x"))
    data: dict = {
        "prompt": form.prompt,
        "batch_size": form.n,
        "width": width,
        "height": height,
    }

    if config.IMAGE_STEPS is not None:
        data["steps"] = _get_config_value(config.IMAGE_STEPS)
    if form.negative_prompt is not None:
        data["negative_prompt"] = form.negative_prompt
    if _get_config_value(config.AUTOMATIC1111_CFG_SCALE):
        data["cfg_scale"] = _get_config_value(config.AUTOMATIC1111_CFG_SCALE)
    if _get_config_value(config.AUTOMATIC1111_SAMPLER):
        data["sampler_name"] = _get_config_value(config.AUTOMATIC1111_SAMPLER)
    if _get_config_value(config.AUTOMATIC1111_SCHEDULER):
        data["scheduler"] = _get_config_value(config.AUTOMATIC1111_SCHEDULER)

    base_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
    r = await asyncio.to_thread(
        requests.post,
        url=f"{base_url}/sdapi/v1/txt2img",
        json=data,
        headers={"authorization": get_automatic1111_api_auth(request)},
    )
    res = r.json()
    log.debug("AUTOMATIC1111 response: %s", res)

    images = []
    for image_b64 in res["images"]:
        result = load_b64_image_data(image_b64)
        if result is None:
            raise HTTPException(status_code=500, detail="Failed to decode AUTOMATIC1111 image data")
        image_data, content_type = result
        url = await upload_image(
            request, {**data, "info": res["info"]}, image_data, content_type, user
        )
        images.append({"url": url})
    return images


# ---------------------------------------------------------------------------
# Error extraction helper
# ---------------------------------------------------------------------------


def _extract_error(exc: Exception, response: requests.Response | None) -> str:
    """Attempt to extract a human-readable error from *response* JSON; fall back to *exc*."""
    if response is None:
        return str(exc)
    try:
        payload = response.json()
        if isinstance(payload, dict) and "error" in payload:
            err = payload["error"]
            if isinstance(err, dict) and "message" in err:
                return err["message"]
            if isinstance(err, str):
                return err
            return str(err)
    except Exception:
        pass
    return str(exc)


# ---------------------------------------------------------------------------
# Endpoints — configuration
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_config(request: Request, user=Depends(get_admin_user)):
    """Return the full image-generation configuration snapshot."""
    return _config_snapshot(request.app.state.config)


@router.post("/config/update")
async def update_config(
    request: Request, form_data: ConfigForm, user=Depends(get_admin_user)
):
    """Persist updated image-generation settings and return the new snapshot."""
    config = request.app.state.config

    config.IMAGE_GENERATION_ENGINE = form_data.engine
    config.ENABLE_IMAGE_GENERATION = form_data.enabled
    config.ENABLE_IMAGE_PROMPT_GENERATION = form_data.prompt_generation
    config.ENABLE_IMAGE_PROMPT_TRANSLATION = form_data.prompt_translation
    config.ENABLE_IMAGE_PROMPT_EXPANSION = form_data.prompt_expansion

    config.IMAGES_OPENAI_API_BASE_URL = form_data.openai.OPENAI_API_BASE_URL
    config.IMAGES_OPENAI_API_KEY = form_data.openai.OPENAI_API_KEY

    config.IMAGES_GEMINI_API_BASE_URL = form_data.gemini.GEMINI_API_BASE_URL
    config.IMAGES_GEMINI_API_KEY = form_data.gemini.GEMINI_API_KEY

    config.AUTOMATIC1111_BASE_URL = form_data.automatic1111.AUTOMATIC1111_BASE_URL
    config.AUTOMATIC1111_API_AUTH = form_data.automatic1111.AUTOMATIC1111_API_AUTH

    config.AUTOMATIC1111_CFG_SCALE = (
        float(form_data.automatic1111.AUTOMATIC1111_CFG_SCALE)
        if form_data.automatic1111.AUTOMATIC1111_CFG_SCALE
        else None
    )
    config.AUTOMATIC1111_SAMPLER = (
        form_data.automatic1111.AUTOMATIC1111_SAMPLER
        if form_data.automatic1111.AUTOMATIC1111_SAMPLER
        else None
    )
    config.AUTOMATIC1111_SCHEDULER = (
        form_data.automatic1111.AUTOMATIC1111_SCHEDULER
        if form_data.automatic1111.AUTOMATIC1111_SCHEDULER
        else None
    )

    config.COMFYUI_BASE_URL = form_data.comfyui.COMFYUI_BASE_URL.strip("/")
    config.COMFYUI_API_KEY = form_data.comfyui.COMFYUI_API_KEY
    config.COMFYUI_WORKFLOW = form_data.comfyui.COMFYUI_WORKFLOW
    config.COMFYUI_WORKFLOW_NODES = form_data.comfyui.COMFYUI_WORKFLOW_NODES

    return _config_snapshot(config)


@router.get("/config/url/verify")
async def verify_url(request: Request, user=Depends(get_admin_user)):
    """Probe the configured image backend to verify connectivity."""
    config = request.app.state.config
    engine = _get_config_value(config.IMAGE_GENERATION_ENGINE)

    if engine == "automatic1111":
        try:
            _verify_automatic1111(config)
            return True
        except Exception:
            config.ENABLE_IMAGE_GENERATION = False
            raise HTTPException(status_code=400, detail=ERROR_MESSAGES.INVALID_URL)

    if engine == "comfyui":
        try:
            _verify_comfyui(config)
            return True
        except Exception:
            config.ENABLE_IMAGE_GENERATION = False
            raise HTTPException(status_code=400, detail=ERROR_MESSAGES.INVALID_URL)

    return True


# ---------------------------------------------------------------------------
# Endpoints — model / image config
# ---------------------------------------------------------------------------


@router.get("/image/config")
async def get_image_config(request: Request, user=Depends(get_admin_user)):
    """Return the current model, size, and steps settings."""
    return _image_config_snapshot(request.app.state.config)


@router.post("/image/config/update")
async def update_image_config(
    request: Request, form_data: ImageConfigForm, user=Depends(get_admin_user)
):
    """Update model, size, and steps; validate inputs before persisting."""
    set_image_model(request, form_data.MODEL)

    if not re.match(r"^\d+x\d+$", form_data.IMAGE_SIZE):
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.INCORRECT_FORMAT("  (e.g., 512x512)."),
        )
    if form_data.IMAGE_STEPS < 0:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.INCORRECT_FORMAT("  (e.g., 50)."),
        )

    config = request.app.state.config
    config.IMAGE_SIZE = form_data.IMAGE_SIZE
    config.IMAGE_STEPS = form_data.IMAGE_STEPS

    return _image_config_snapshot(config)


# ---------------------------------------------------------------------------
# Endpoints — model listing
# ---------------------------------------------------------------------------


@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    """List available image generation models for the active engine."""
    config = request.app.state.config
    engine = _get_config_value(config.IMAGE_GENERATION_ENGINE)

    try:
        if engine == "openai":
            return [
                {"id": "gpt-image-2", "name": "GPT Image 2"},
                {"id": "gpt-image-1.5", "name": "GPT Image 1.5"},
                {"id": "gpt-image-1", "name": "GPT Image 1"},
                {"id": "gpt-image-1-mini", "name": "GPT Image 1 Mini"},
            ]

        if engine == "gemini":
            return [
                {"id": "imagen-3-0-generate-002", "name": "imagen-3.0 generate-002"},
            ]

        if engine == "comfyui":
            return await _list_comfyui_models(config)

        # automatic1111 or empty (default)
        return await _list_automatic1111_models(request, config)

    except HTTPException:
        raise
    except Exception as exc:
        config.ENABLE_IMAGE_GENERATION = False
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(exc))


async def _list_comfyui_models(config) -> list[dict]:
    """Query ComfyUI for available checkpoint models."""
    base_url = _get_config_value(config.COMFYUI_BASE_URL)
    api_key = _get_config_value(config.COMFYUI_API_KEY)
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    r = await asyncio.to_thread(
        requests.get, url=f"{base_url}/object_info", headers=headers
    )
    info = r.json()

    workflow = json.loads(_get_config_value(config.COMFYUI_WORKFLOW))
    nodes = _get_config_value(config.COMFYUI_WORKFLOW_NODES)

    # Locate the model node
    model_node_id = None
    for node in nodes:
        if node["type"] == "model" and node.get("node_ids"):
            model_node_id = node["node_ids"][0]
            break

    if model_node_id:
        class_type = workflow[model_node_id]["class_type"]
        log.info("ComfyUI model node class_type: %s", class_type)
        required = info[class_type]["input"]["required"]
        model_key = next((k for k in required if "_name" in k), None)
        if model_key:
            return [{"id": m, "name": m} for m in required[model_key][0]]

    # Fallback to CheckpointLoaderSimple defaults
    return [
        {"id": m, "name": m}
        for m in info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
    ]


async def _list_automatic1111_models(request: Request, config) -> list[dict]:
    """Query AUTOMATIC1111 for available Stable Diffusion models."""
    base_url = _get_config_value(config.AUTOMATIC1111_BASE_URL)
    r = await asyncio.to_thread(
        requests.get,
        url=f"{base_url}/sdapi/v1/sd-models",
        headers={"authorization": get_automatic1111_api_auth(request)},
    )
    models = r.json()
    return [{"id": m["title"], "name": m["model_name"]} for m in models]


# ---------------------------------------------------------------------------
# Endpoints — image generation
# ---------------------------------------------------------------------------


@router.post("/generations")
async def image_generations(
    request: Request,
    form_data: GenerateImageForm,
    user=Depends(get_verified_user),
):
    """Generate one or more images using the configured engine."""
    config = request.app.state.config
    engine = _get_config_value(config.IMAGE_GENERATION_ENGINE) or ""

    r: requests.Response | None = None
    try:
        if engine == "openai":
            return await _generate_openai(request, form_data, user, config)
        if engine == "gemini":
            return await _generate_gemini(request, form_data, user, config)
        if engine == "comfyui":
            return await _generate_comfyui(request, form_data, user, config)
        # automatic1111 or empty (default)
        return await _generate_automatic1111(request, form_data, user, config)
    except HTTPException:
        raise
    except Exception as exc:
        error = _extract_error(exc, r)
        log.error("Image generation failed: %s", error)
        raise HTTPException(status_code=400, detail=ERROR_MESSAGES.DEFAULT(error))
