"""Pipeline management router with filter middleware.

Provides CRUD endpoints for managing remote pipelines (list, upload, add,
delete) as well as valve inspection and updates.  Also exposes helper
functions used by the chat middleware to run inlet/outlet filter chains
before and after model calls.
"""

from __future__ import annotations

import logging
import os
import shutil
from typing import Any, Optional

import aiohttp
import requests
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel

from bcgpt.config import CACHE_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.routers.openai import _fetch_all_provider_models as get_all_models_responses
from bcgpt.utils import get_admin_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class AddPipelineForm(BaseModel):
    """Payload for registering a pipeline by URL."""

    url: str
    urlIdx: int


class DeletePipelineForm(BaseModel):
    """Payload for removing a registered pipeline."""

    id: str
    urlIdx: int


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_url_and_key(request: Request, url_idx: int) -> tuple[str, str]:
    """Resolve the API base URL and key for the given *url_idx*.

    Returns:
        A ``(base_url, api_key)`` tuple pulled from the app config.
    """
    base_url = request.app.state.config.OPENAI_API_BASE_URLS[url_idx]
    api_key = request.app.state.config.OPENAI_API_KEYS[url_idx]
    return base_url, api_key


def _extract_detail(response: requests.Response | None) -> str:
    """Try to read a ``detail`` field from a failed *response*.

    Returns the extracted detail string, or a generic fallback message.
    """
    if response is None:
        return "Pipeline not found"
    try:
        body = response.json()
        if "detail" in body:
            return body["detail"]
    except Exception:
        pass
    return "Pipeline not found"


def _extract_status(response: requests.Response | None) -> int:
    """Return the HTTP status from *response*, defaulting to 404."""
    return response.status_code if response is not None else status.HTTP_404_NOT_FOUND


def _forward_request(
    method: str,
    url: str,
    api_key: str,
    *,
    json_data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
) -> requests.Response:
    """Execute a synchronous HTTP request to a pipeline backend.

    Args:
        method: HTTP method (``get``, ``post``, ``delete``).
        url: Fully-qualified URL.
        api_key: Bearer token.
        json_data: Optional JSON body.
        files: Optional multipart files dict.

    Returns:
        The raw :class:`requests.Response`.
    """
    headers = {"Authorization": f"Bearer {api_key}"}
    fn = getattr(requests, method)
    return fn(url, headers=headers, json=json_data, files=files)


def _proxy_pipeline_call(
    response: requests.Response | None,
    exc: Exception,
) -> None:
    """Raise a user-facing HTTPException from a failed pipeline proxy call.

    Extracts the upstream status code and detail message when available.
    """
    log.error("Pipeline proxy call failed: %s", exc)
    raise HTTPException(
        status_code=_extract_status(response),
        detail=_extract_detail(response),
    )


def _user_dict(user) -> dict[str, Any]:
    """Convert a user object to the dict shape expected by pipeline filters."""
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "role": user.role,
    }


# ---------------------------------------------------------------------------
# Filter middleware helpers (used by chat utils)
# ---------------------------------------------------------------------------


def get_sorted_filters(model_id: str, models: dict[str, Any]) -> list[dict[str, Any]]:
    """Return pipeline filters applicable to *model_id*, sorted by priority.

    A filter matches when its ``pipeline.type`` is ``"filter"`` and its
    ``pipeline.pipelines`` list is either ``["*"]`` (match-all) or contains
    *model_id*.
    """
    candidates = [
        model
        for model in models.values()
        if "pipeline" in model
        and model["pipeline"].get("type") == "filter"
        and (
            model["pipeline"]["pipelines"] == ["*"]
            or model_id in model["pipeline"]["pipelines"]
        )
    ]
    return sorted(candidates, key=lambda m: m["pipeline"]["priority"])


async def process_pipeline_inlet_filter(
    request: Request,
    payload: dict[str, Any],
    user,
    models: dict[str, Any],
) -> dict[str, Any]:
    """Run the inlet filter chain, mutating *payload* in place.

    Filters are executed in priority order; the owning model's own pipeline
    (if any) is appended last.
    """
    user_info = _user_dict(user)
    model_id = payload["model"]
    filters = get_sorted_filters(model_id, models)

    model = models[model_id]
    if "pipeline" in model:
        filters.append(model)

    async with aiohttp.ClientSession() as session:
        for filt in filters:
            url_idx = filt.get("urlIdx")
            if url_idx is None:
                continue

            base_url = request.app.state.config.OPENAI_API_BASE_URLS[url_idx]
            api_key = request.app.state.config.OPENAI_API_KEYS[url_idx]
            if not api_key:
                continue

            try:
                async with session.post(
                    f"{base_url}/{filt['id']}/filter/inlet",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"user": user_info, "body": payload},
                ) as resp:
                    payload = await resp.json()
                    resp.raise_for_status()
            except aiohttp.ClientResponseError:
                try:
                    body = (
                        await resp.json()
                        if resp.content_type == "application/json"
                        else {}
                    )
                    if "detail" in body:
                        raise Exception(resp.status, body["detail"])
                except Exception:
                    pass
            except Exception as exc:
                log.exception("Inlet filter connection error: %s", exc)

    return payload


async def process_pipeline_outlet_filter(
    request: Request,
    payload: dict[str, Any],
    user,
    models: dict[str, Any],
) -> dict[str, Any]:
    """Run the outlet filter chain, mutating *payload* in place.

    Filters are executed in reverse priority order; the owning model's own
    pipeline (if any) is prepended first.
    """
    user_info = _user_dict(user)
    model_id = payload["model"]
    filters = get_sorted_filters(model_id, models)

    model = models[model_id]
    if "pipeline" in model:
        filters = [model] + filters

    async with aiohttp.ClientSession() as session:
        for filt in filters:
            url_idx = filt.get("urlIdx")
            if url_idx is None:
                continue

            base_url = request.app.state.config.OPENAI_API_BASE_URLS[url_idx]
            api_key = request.app.state.config.OPENAI_API_KEYS[url_idx]
            if not api_key:
                continue

            try:
                async with session.post(
                    f"{base_url}/{filt['id']}/filter/outlet",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"user": user_info, "body": payload},
                ) as resp:
                    payload = await resp.json()
                    resp.raise_for_status()
            except aiohttp.ClientResponseError:
                try:
                    body = (
                        await resp.json()
                        if "application/json" in resp.content_type
                        else {}
                    )
                    if "detail" in body:
                        raise Exception(resp.status, body)
                except Exception:
                    pass
            except Exception as exc:
                log.exception("Outlet filter connection error: %s", exc)

    return payload


# ---------------------------------------------------------------------------
# Pipeline list endpoint
# ---------------------------------------------------------------------------


@router.get("/list")
async def get_pipelines_list(request: Request, user=Depends(get_admin_user)):
    """Return URLs and indices of backends that expose a ``/pipelines`` endpoint."""
    responses = await get_all_models_responses(request, user)
    log.debug("get_pipelines_list: received %d responses", len(responses))

    url_indices = [
        idx
        for idx, resp in enumerate(responses)
        if resp is not None and "pipelines" in resp
    ]

    return {
        "data": [
            {
                "url": request.app.state.config.OPENAI_API_BASE_URLS[idx],
                "idx": idx,
            }
            for idx in url_indices
        ]
    }


# ---------------------------------------------------------------------------
# Pipeline upload endpoint
# ---------------------------------------------------------------------------


@router.post("/upload")
async def upload_pipeline(
    request: Request,
    urlIdx: int = Form(...),
    file: UploadFile = File(...),
    user=Depends(get_admin_user),
):
    """Upload a Python pipeline file to a remote backend.

    The file is saved to a temporary cache directory, forwarded to the
    target pipeline service, and then cleaned up regardless of outcome.
    """
    log.info("upload_pipeline: urlIdx=%d, filename=%s", urlIdx, file.filename)

    if not (file.filename and file.filename.endswith(".py")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Python (.py) files are allowed.",
        )

    upload_dir = os.path.join(CACHE_DIR, "pipelines")
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, os.path.basename(file.filename))

    r: requests.Response | None = None
    try:
        with open(file_path, "wb") as dest:
            shutil.copyfileobj(file.file, dest)

        base_url, api_key = _get_url_and_key(request, urlIdx)

        with open(file_path, "rb") as f:
            r = _forward_request(
                "post",
                f"{base_url}/pipelines/upload",
                api_key,
                files={"file": f},
            )

        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)


# ---------------------------------------------------------------------------
# Pipeline CRUD endpoints
# ---------------------------------------------------------------------------


@router.post("/add")
async def add_pipeline(
    request: Request,
    form_data: AddPipelineForm,
    user=Depends(get_admin_user),
):
    """Register a new pipeline by URL on the specified backend."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, form_data.urlIdx)
        r = _forward_request(
            "post",
            f"{base_url}/pipelines/add",
            api_key,
            json_data={"url": form_data.url},
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)


@router.delete("/delete")
async def delete_pipeline(
    request: Request,
    form_data: DeletePipelineForm,
    user=Depends(get_admin_user),
):
    """Remove a registered pipeline by ID from the specified backend."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, form_data.urlIdx)
        r = _forward_request(
            "delete",
            f"{base_url}/pipelines/delete",
            api_key,
            json_data={"id": form_data.id},
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)


@router.get("/")
async def get_pipelines(
    request: Request,
    urlIdx: Optional[int] = None,
    user=Depends(get_admin_user),
):
    """List all pipelines on the specified backend."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, urlIdx)
        r = _forward_request("get", f"{base_url}/pipelines", api_key)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)


# ---------------------------------------------------------------------------
# Valve endpoints
# ---------------------------------------------------------------------------


@router.get("/{pipeline_id}/valves")
async def get_pipeline_valves(
    request: Request,
    urlIdx: Optional[int],
    pipeline_id: str,
    user=Depends(get_admin_user),
):
    """Retrieve the current valve values for a pipeline."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, urlIdx)
        r = _forward_request("get", f"{base_url}/{pipeline_id}/valves", api_key)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)


@router.get("/{pipeline_id}/valves/spec")
async def get_pipeline_valves_spec(
    request: Request,
    urlIdx: Optional[int],
    pipeline_id: str,
    user=Depends(get_admin_user),
):
    """Retrieve the valve specification (schema) for a pipeline."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, urlIdx)
        r = _forward_request("get", f"{base_url}/{pipeline_id}/valves/spec", api_key)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)


@router.post("/{pipeline_id}/valves/update")
async def update_pipeline_valves(
    request: Request,
    urlIdx: Optional[int],
    pipeline_id: str,
    form_data: dict,
    user=Depends(get_admin_user),
):
    """Update valve configuration values for a pipeline."""
    r: requests.Response | None = None
    try:
        base_url, api_key = _get_url_and_key(request, urlIdx)
        r = _forward_request(
            "post",
            f"{base_url}/{pipeline_id}/valves/update",
            api_key,
            json_data=form_data,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        _proxy_pipeline_call(r, exc)
