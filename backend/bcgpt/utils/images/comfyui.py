"""ComfyUI image-generation integration.

Provides helpers for submitting workflows to a ComfyUI instance over HTTP
and WebSocket, collecting generated image URLs, and mapping high-level
generation parameters onto workflow node inputs.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

import websocket  # websocket-client
from bcgpt.env import SRC_LOG_LEVELS
from pydantic import BaseModel

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["COMFYUI"])

_DEFAULT_HEADERS: Dict[str, str] = {"User-Agent": "Mozilla/5.0"}


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------


def queue_prompt(
    prompt: dict,
    client_id: str,
    base_url: str,
    api_key: str,
) -> dict:
    """Submit a workflow *prompt* to ComfyUI and return the queued response.

    Args:
        prompt: Serialisable workflow dict.
        client_id: WebSocket client identifier echoed back by ComfyUI.
        base_url: ComfyUI HTTP root (e.g. ``"http://localhost:8188"``).
        api_key: Bearer token for authentication.

    Returns:
        Parsed JSON response (contains at least ``prompt_id``).

    Raises:
        Exception: Propagated on network or HTTP errors.
    """
    log.info("queue_prompt")
    data = json.dumps({"prompt": prompt, "client_id": client_id}).encode("utf-8")
    log.debug("queue_prompt data: %s", data)
    try:
        req = urllib.request.Request(
            f"{base_url}/prompt",
            data=data,
            headers={**_DEFAULT_HEADERS, "Authorization": f"Bearer {api_key}"},
        )
        response = urllib.request.urlopen(req).read()
        return json.loads(response)
    except Exception as exc:
        log.exception("Error while queuing prompt: %s", exc)
        raise


def get_image(
    filename: str,
    subfolder: str,
    folder_type: str,
    base_url: str,
    api_key: str,
) -> bytes:
    """Download raw image bytes from ComfyUI's ``/view`` endpoint.

    Args:
        filename: Image file name on the server.
        subfolder: Sub-folder within the output directory.
        folder_type: ComfyUI folder type (``"output"``, ``"temp"`` …).
        base_url: ComfyUI HTTP root.
        api_key: Bearer token.

    Returns:
        Raw image bytes.
    """
    log.info("get_image")
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    req = urllib.request.Request(
        f"{base_url}/view?{params}",
        headers={**_DEFAULT_HEADERS, "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req) as resp:
        return resp.read()


def get_image_url(
    filename: str,
    subfolder: str,
    folder_type: str,
    base_url: str,
) -> str:
    """Construct the URL for an image served by ComfyUI's ``/view`` endpoint.

    Args:
        filename: Image file name.
        subfolder: Sub-folder within the output directory.
        folder_type: ComfyUI folder type.
        base_url: ComfyUI HTTP root.

    Returns:
        Fully-qualified URL string.
    """
    log.info("get_image_url")
    params = urllib.parse.urlencode(
        {"filename": filename, "subfolder": subfolder, "type": folder_type}
    )
    return f"{base_url}/view?{params}"


def get_history(
    prompt_id: str,
    base_url: str,
    api_key: str,
) -> dict:
    """Fetch execution history for *prompt_id* from ComfyUI.

    Args:
        prompt_id: The prompt identifier returned by :func:`queue_prompt`.
        base_url: ComfyUI HTTP root.
        api_key: Bearer token.

    Returns:
        Parsed JSON history dict keyed by prompt ID.
    """
    log.info("get_history")
    req = urllib.request.Request(
        f"{base_url}/history/{prompt_id}",
        headers={**_DEFAULT_HEADERS, "Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# WebSocket image collection
# ---------------------------------------------------------------------------


def get_images(
    ws: websocket.WebSocket,
    prompt: dict,
    client_id: str,
    base_url: str,
    api_key: str,
) -> Dict[str, List[Dict[str, str]]]:
    """Block until a workflow finishes and collect output image URLs.

    Listens on the WebSocket *ws* for execution-completion messages
    matching *prompt_id*, then reads the history to discover generated
    images.

    Args:
        ws: Connected WebSocket to ComfyUI.
        prompt: Serialisable workflow dict.
        client_id: WebSocket client identifier.
        base_url: ComfyUI HTTP root.
        api_key: Bearer token.

    Returns:
        ``{"data": [{"url": "..."}, ...]}`` with one entry per image.
    """
    prompt_id = queue_prompt(prompt, client_id, base_url, api_key)["prompt_id"]
    output_images: List[Dict[str, str]] = []

    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message["type"] == "executing":
                data = message["data"]
                if data["node"] is None and data["prompt_id"] == prompt_id:
                    break
        else:
            continue  # binary preview frames

    history = get_history(prompt_id, base_url, api_key)[prompt_id]
    for node_id in history.get("outputs", {}):
        node_output = history["outputs"][node_id]
        if "images" in node_output:
            for image in node_output["images"]:
                url = get_image_url(
                    image["filename"], image["subfolder"], image["type"], base_url
                )
                output_images.append({"url": url})

    return {"data": output_images}


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class ComfyUINodeInput(BaseModel):
    """Describes a single workflow node input to be overridden at runtime."""

    type: Optional[str] = None
    node_ids: list[str] = []
    key: Optional[str] = "text"
    value: Optional[str] = None


class ComfyUIWorkflow(BaseModel):
    """Wraps the raw workflow JSON together with node-input overrides."""

    workflow: str
    nodes: list[ComfyUINodeInput]


class ComfyUIGenerateImageForm(BaseModel):
    """High-level image generation request mapped onto a ComfyUI workflow."""

    workflow: ComfyUIWorkflow

    prompt: str
    negative_prompt: Optional[str] = None
    width: int
    height: int
    n: int = 1

    steps: Optional[int] = None
    seed: Optional[int] = None


# ---------------------------------------------------------------------------
# High-level generation entry point
# ---------------------------------------------------------------------------


async def comfyui_generate_image(
    model: str,
    payload: ComfyUIGenerateImageForm,
    client_id: str,
    base_url: str,
    api_key: str,
) -> Optional[Dict[str, List[Dict[str, str]]]]:
    """Generate images via ComfyUI using the supplied *payload*.

    Parses the workflow JSON, applies node-level parameter overrides
    (model name, prompt, dimensions, steps, seed, etc.), submits the
    workflow over a WebSocket, and returns collected image URLs.

    Args:
        model: Model identifier injected into designated workflow nodes.
        payload: Generation parameters and workflow definition.
        client_id: WebSocket client identifier.
        base_url: ComfyUI HTTP root.
        api_key: Bearer token.

    Returns:
        Image result dict (see :func:`get_images`) on success, or
        ``None`` on failure.
    """
    ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
    workflow = json.loads(payload.workflow.workflow)

    # Apply node-level overrides
    for node in payload.workflow.nodes:
        if node.type:
            _apply_typed_override(workflow, node, model, payload)
        else:
            for node_id in node.node_ids:
                workflow[node_id]["inputs"][node.key] = node.value

    # Connect WebSocket
    try:
        ws = websocket.WebSocket()
        ws.connect(
            f"{ws_url}/ws?clientId={client_id}",
            header={"Authorization": f"Bearer {api_key}"},
        )
        log.info("WebSocket connection established")
    except Exception as exc:
        log.exception("Failed to connect to WebSocket server: %s", exc)
        return None

    # Execute workflow and collect images
    try:
        log.info("Sending workflow to WebSocket server")
        log.debug("Workflow: %s", workflow)
        images = await asyncio.to_thread(
            get_images, ws, workflow, client_id, base_url, api_key
        )
    except Exception as exc:
        log.exception("Error while receiving images: %s", exc)
        images = None

    ws.close()
    return images


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_typed_override(
    workflow: dict,
    node: ComfyUINodeInput,
    model: str,
    payload: ComfyUIGenerateImageForm,
) -> None:
    """Mutate *workflow* by applying a single typed node override."""
    key = node.key

    mapping: Dict[str, Any] = {
        "model": model,
        "prompt": payload.prompt,
        "negative_prompt": payload.negative_prompt,
        "width": payload.width,
        "height": payload.height,
        "n": payload.n,
        "steps": payload.steps,
        "seed": (
            payload.seed
            if payload.seed is not None
            else random.randint(0, 1_125_899_906_842_624)
        ),
    }

    value = mapping.get(node.type)  # type: ignore[arg-type]
    if value is not None:
        for node_id in node.node_ids:
            workflow[node_id]["inputs"][key] = value
