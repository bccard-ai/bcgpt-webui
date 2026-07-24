"""Audio router — TTS speech synthesis, STT transcription, and config management.

Provides endpoints for text-to-speech (OpenAI, ElevenLabs, Azure),
speech-to-text (OpenAI, Deepgram), voice/model listing, and audio
configuration management.  All audio artifacts are cached on disk.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import uuid
from functools import lru_cache
from pathlib import Path

import aiofiles
import aiohttp
import requests as _requests  # renamed to clarify sync usage
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel

from bcgpt.config import CACHE_DIR
from bcgpt.constants import ERROR_MESSAGES
from bcgpt.env import (
    AIOHTTP_CLIENT_TIMEOUT,
    ENABLE_FORWARD_USER_INFO_HEADERS,
    SRC_LOG_LEVELS,
)
from bcgpt.utils import get_admin_user, get_verified_user

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["AUDIO"])

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_FILE_SIZE_MB: int = 25
MAX_FILE_SIZE: int = MAX_FILE_SIZE_MB * 1024 * 1024

SUPPORTED_AUDIO_TYPES: tuple[str, ...] = (
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/x-m4a",
)

OPENAI_VOICES: dict[str, str] = {
    "alloy": "alloy",
    "echo": "echo",
    "fable": "fable",
    "onyx": "onyx",
    "nova": "nova",
    "shimmer": "shimmer",
}

SPEECH_CACHE_DIR: Path = CACHE_DIR / "audio" / "speech"
SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)

TRANSCRIPTIONS_DIR: Path = CACHE_DIR / "audio" / "transcriptions"
TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class TTSConfigForm(BaseModel):
    """Form payload for TTS engine configuration."""

    OPENAI_API_BASE_URL: str
    OPENAI_API_KEY: str
    API_KEY: str
    ENGINE: str
    MODEL: str
    VOICE: str
    SPLIT_ON: str
    AZURE_SPEECH_REGION: str
    AZURE_SPEECH_OUTPUT_FORMAT: str


class STTConfigForm(BaseModel):
    """Form payload for STT engine configuration."""

    OPENAI_API_BASE_URL: str
    OPENAI_API_KEY: str
    ENGINE: str
    MODEL: str
    DEEPGRAM_API_KEY: str


class AudioConfigUpdateForm(BaseModel):
    """Combined TTS + STT configuration update."""

    tts: TTSConfigForm
    stt: STTConfigForm


# ---------------------------------------------------------------------------
# Config serialization helpers
# ---------------------------------------------------------------------------


def _serialize_tts_config(cfg) -> dict:
    """Return a JSON-safe dict of the current TTS config attributes."""
    return {
        "OPENAI_API_BASE_URL": cfg.TTS_OPENAI_API_BASE_URL,
        "OPENAI_API_KEY": cfg.TTS_OPENAI_API_KEY,
        "API_KEY": cfg.TTS_API_KEY,
        "ENGINE": cfg.TTS_ENGINE,
        "MODEL": cfg.TTS_MODEL,
        "VOICE": cfg.TTS_VOICE,
        "SPLIT_ON": cfg.TTS_SPLIT_ON,
        "AZURE_SPEECH_REGION": cfg.TTS_AZURE_SPEECH_REGION,
        "AZURE_SPEECH_OUTPUT_FORMAT": cfg.TTS_AZURE_SPEECH_OUTPUT_FORMAT,
    }


def _serialize_stt_config(cfg) -> dict:
    """Return a JSON-safe dict of the current STT config attributes."""
    return {
        "OPENAI_API_BASE_URL": cfg.STT_OPENAI_API_BASE_URL,
        "OPENAI_API_KEY": cfg.STT_OPENAI_API_KEY,
        "ENGINE": cfg.STT_ENGINE,
        "MODEL": cfg.STT_MODEL,
        "DEEPGRAM_API_KEY": cfg.DEEPGRAM_API_KEY,
    }


def _serialize_audio_config(cfg) -> dict:
    """Return the combined TTS + STT config dict."""
    return {
        "tts": _serialize_tts_config(cfg),
        "stt": _serialize_stt_config(cfg),
    }


# ---------------------------------------------------------------------------
# External API error parsing
# ---------------------------------------------------------------------------


def _parse_api_error(response, fallback_error: Exception) -> str | None:
    """Try to extract a human-readable error from an external API response.

    Returns *None* when no structured error is available.
    """
    try:
        body = response.json()
        if "error" in body:
            return f"External: {body['error'].get('message', '')}"
    except Exception:
        return f"External: {fallback_error}"
    return None


# ---------------------------------------------------------------------------
# User-info headers helper
# ---------------------------------------------------------------------------


def _user_info_headers(user) -> dict[str, str]:
    """Return forwarded user-identity headers when the feature is enabled."""
    if not ENABLE_FORWARD_USER_INFO_HEADERS:
        return {}
    return {
        "X-BCGPT-User-Name": user.name,
        "X-BCGPT-User-Id": user.id,
        "X-BCGPT-User-Email": user.email,
        "X-BCGPT-User-Role": user.role,
    }


# ---------------------------------------------------------------------------
# Speech cache helpers
# ---------------------------------------------------------------------------


def _speech_cache_key(body: bytes, engine: str, model: str) -> str:
    """Compute a deterministic cache key for a TTS request."""
    raw = body + engine.encode("utf-8") + model.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


async def _write_cache(file_path: Path, body_path: Path, audio: bytes, payload: dict) -> None:
    """Persist audio data and the original request payload to disk."""
    async with aiofiles.open(file_path, "wb") as f:
        await f.write(audio)
    async with aiofiles.open(body_path, "w") as f:
        await f.write(json.dumps(payload))


def _raise_from_response(response, exc: Exception) -> None:
    """Raise an HTTPException derived from an external API failure."""
    detail = _parse_api_error(response, exc) or "BCGPT: Server Connection Error"
    raise HTTPException(
        status_code=getattr(response, "status", 500),
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Config endpoints
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_audio_config(request: Request, user=Depends(get_admin_user)):
    """Return the current TTS and STT configuration."""
    return _serialize_audio_config(request.app.state.config)


@router.post("/config/update")
async def update_audio_config(
    request: Request,
    form_data: AudioConfigUpdateForm,
    user=Depends(get_admin_user),
):
    """Persist updated TTS and STT settings and return the new config."""
    cfg = request.app.state.config
    tts = form_data.tts
    stt = form_data.stt

    cfg.TTS_OPENAI_API_BASE_URL = tts.OPENAI_API_BASE_URL
    cfg.TTS_OPENAI_API_KEY = tts.OPENAI_API_KEY
    cfg.TTS_API_KEY = tts.API_KEY
    cfg.TTS_ENGINE = tts.ENGINE
    cfg.TTS_MODEL = tts.MODEL
    cfg.TTS_VOICE = tts.VOICE
    cfg.TTS_SPLIT_ON = tts.SPLIT_ON
    cfg.TTS_AZURE_SPEECH_REGION = tts.AZURE_SPEECH_REGION
    cfg.TTS_AZURE_SPEECH_OUTPUT_FORMAT = tts.AZURE_SPEECH_OUTPUT_FORMAT

    cfg.STT_OPENAI_API_BASE_URL = stt.OPENAI_API_BASE_URL
    cfg.STT_OPENAI_API_KEY = stt.OPENAI_API_KEY
    cfg.STT_ENGINE = stt.ENGINE
    cfg.STT_MODEL = stt.MODEL
    cfg.DEEPGRAM_API_KEY = stt.DEEPGRAM_API_KEY

    return _serialize_audio_config(cfg)


# ---------------------------------------------------------------------------
# TTS — speech synthesis
# ---------------------------------------------------------------------------


async def _speech_openai(request: Request, payload: dict, file_path: Path, body_path: Path, user) -> FileResponse:
    """Synthesize speech via the OpenAI-compatible TTS API."""
    cfg = request.app.state.config
    payload["model"] = cfg.TTS_MODEL

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {cfg.TTS_OPENAI_API_KEY}",
        **_user_info_headers(user),
    }
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(
                f"{cfg.TTS_OPENAI_API_BASE_URL}/audio/speech",
                json=payload,
                headers=headers,
            ) as r:
                r.raise_for_status()
                audio = await r.read()
                await _write_cache(file_path, body_path, audio, payload)
        return FileResponse(file_path)
    except Exception as exc:
        log.exception("OpenAI TTS error: %s", exc)
        _raise_from_response(r, exc)


async def _speech_elevenlabs(request: Request, payload: dict, file_path: Path, body_path: Path) -> FileResponse:
    """Synthesize speech via the ElevenLabs TTS API."""
    cfg = request.app.state.config
    voice_id = payload.get("voice", "")

    if voice_id not in get_available_voices(request):
        raise HTTPException(status_code=400, detail="Invalid voice id")

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": cfg.TTS_API_KEY,
    }
    body = {
        "text": payload["input"],
        "model_id": cfg.TTS_MODEL,
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.5},
    }
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(
                f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                json=body,
                headers=headers,
            ) as r:
                r.raise_for_status()
                audio = await r.read()
                await _write_cache(file_path, body_path, audio, payload)
        return FileResponse(file_path)
    except Exception as exc:
        log.exception("ElevenLabs TTS error: %s", exc)
        _raise_from_response(r, exc)


async def _speech_azure(request: Request, payload: dict, file_path: Path, body_path: Path) -> FileResponse:
    """Synthesize speech via the Azure Cognitive Services TTS API."""
    cfg = request.app.state.config

    region = cfg.TTS_AZURE_SPEECH_REGION
    voice_name = cfg.TTS_VOICE
    locale = "-".join(voice_name.split("-")[:1])
    output_format = cfg.TTS_AZURE_SPEECH_OUTPUT_FORMAT

    ssml = (
        f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{locale}">'
        f'<voice name="{voice_name}">{payload["input"]}</voice>'
        f"</speak>"
    )
    headers = {
        "Ocp-Apim-Subscription-Key": cfg.TTS_API_KEY,
        "Content-Type": "application/ssml+xml",
        "X-Microsoft-OutputFormat": output_format,
    }
    timeout = aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT)
    try:
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(
                f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1",
                headers=headers,
                data=ssml,
            ) as r:
                r.raise_for_status()
                audio = await r.read()
                await _write_cache(file_path, body_path, audio, payload)
        return FileResponse(file_path)
    except Exception as exc:
        log.exception("Azure TTS error: %s", exc)
        _raise_from_response(r, exc)


@router.post("/speech")
async def speech(request: Request, user=Depends(get_verified_user)):
    """Synthesize audio from text using the configured TTS engine.

    Results are cached on disk keyed by request body + engine + model.
    """
    body = await request.body()
    cfg = request.app.state.config

    cache_name = _speech_cache_key(body, cfg.TTS_ENGINE, cfg.TTS_MODEL)
    file_path = SPEECH_CACHE_DIR / f"{cache_name}.mp3"
    body_path = SPEECH_CACHE_DIR / f"{cache_name}.json"

    if file_path.is_file():
        return FileResponse(file_path)

    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception as exc:
        log.exception("Invalid JSON payload: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    engine = cfg.TTS_ENGINE
    if engine == "openai":
        return await _speech_openai(request, payload, file_path, body_path, user)
    if engine == "elevenlabs":
        return await _speech_elevenlabs(request, payload, file_path, body_path)
    if engine == "azure":
        return await _speech_azure(request, payload, file_path, body_path)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="No TTS engine configured. Please configure a TTS engine (openai, elevenlabs, or azure) in Admin Settings.",
    )


# ---------------------------------------------------------------------------
# STT — transcription
# ---------------------------------------------------------------------------


def _save_transcript(file_dir: str, file_id: str, data: dict) -> None:
    """Persist a transcription result to a JSON sidecar file."""
    path = os.path.join(file_dir, f"{file_id}.json")
    with open(path, "w") as f:
        json.dump(data, f)


def _transcribe_openai(request: Request, file_path: str, filename: str, file_dir: str, file_id: str) -> dict:
    """Transcribe audio via the OpenAI-compatible STT API."""
    cfg = request.app.state.config
    r = None
    try:
        r = _requests.post(
            f"{cfg.STT_OPENAI_API_BASE_URL}/audio/transcriptions",
            headers={"Authorization": f"Bearer {cfg.STT_OPENAI_API_KEY}"},
            files={"file": (filename, open(file_path, "rb"))},
            data={"model": cfg.STT_MODEL},
        )
        r.raise_for_status()
        data = r.json()
        _save_transcript(file_dir, file_id, data)
        return data
    except Exception as exc:
        log.exception("OpenAI STT error: %s", exc)
        detail = None
        if r is not None:
            detail = _parse_api_error(r, exc)
        raise Exception(detail or "BCGPT: Server Connection Error")


def _transcribe_deepgram(request: Request, file_path: str, file_id: str, file_dir: str) -> dict:
    """Transcribe audio via the Deepgram STT API."""
    cfg = request.app.state.config

    mime, _ = mimetypes.guess_type(file_path)
    if not mime:
        mime = "audio/wav"

    with open(file_path, "rb") as f:
        file_data = f.read()

    headers = {
        "Authorization": f"Token {cfg.DEEPGRAM_API_KEY}",
        "Content-Type": mime,
    }
    params = {}
    if cfg.STT_MODEL:
        params["model"] = cfg.STT_MODEL

    r = None
    try:
        r = _requests.post(
            "https://api.deepgram.com/v1/listen",
            headers=headers,
            params=params,
            data=file_data,
        )
        r.raise_for_status()
        response_data = r.json()

        try:
            transcript = response_data["results"]["channels"][0]["alternatives"][0].get("transcript", "")
        except (KeyError, IndexError) as exc:
            log.error("Malformed Deepgram response: %s", exc)
            raise Exception("Failed to parse Deepgram response - unexpected response format")

        data = {"text": transcript.strip()}
        _save_transcript(file_dir, file_id, data)
        return data
    except Exception as exc:
        log.exception("Deepgram STT error: %s", exc)
        detail = None
        if r is not None:
            detail = _parse_api_error(r, exc)
        raise Exception(detail or "BCGPT: Server Connection Error")


def transcribe(request: Request, file_path: str) -> dict:
    """Dispatch transcription to the configured STT engine.

    Returns a dict with at least a ``text`` key.
    """
    log.info("transcribe: %s", file_path)
    filename = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    file_id = filename.split(".")[0]

    engine = request.app.state.config.STT_ENGINE
    if engine == "openai":
        return _transcribe_openai(request, file_path, filename, file_dir, file_id)
    if engine == "deepgram":
        return _transcribe_deepgram(request, file_path, file_id, file_dir)

    raise Exception(f"Unsupported STT engine: {engine}")


@router.post("/transcriptions")
def transcription(
    request: Request,
    file: UploadFile = File(...),
    user=Depends(get_verified_user),
):
    """Accept an audio upload and return a transcription."""
    log.info("file.content_type: %s", file.content_type)

    if not file.content_type.startswith(SUPPORTED_AUDIO_TYPES):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_SUPPORTED,
        )

    try:
        ext = os.path.splitext(os.path.basename(file.filename or ""))[1].lstrip(".") or "bin"
        file_id = uuid.uuid4()
        filename = f"{file_id}.{ext}"
        contents = file.file.read()

        file_path = str(TRANSCRIPTIONS_DIR / filename)

        with open(file_path, "wb") as f:
            f.write(contents)

        data = transcribe(request, file_path)
        return {**data, "filename": filename}

    except HTTPException:
        raise
    except Exception as exc:
        log.exception("Transcription error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(exc),
        )


# ---------------------------------------------------------------------------
# Voice listing
# ---------------------------------------------------------------------------


@lru_cache
def get_elevenlabs_voices(api_key: str) -> dict[str, str]:
    """Fetch available voices from ElevenLabs.

    Results are cached per API key.  Requires ``AUDIO_TTS_ENGINE=elevenlabs``
    and a valid ``AUDIO_TTS_API_KEY``.
    """
    try:
        response = _requests.get(
            "https://api.elevenlabs.io/v1/voices",
            headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        )
        response.raise_for_status()
        voices_data = response.json()
        return {v["voice_id"]: v["name"] for v in voices_data.get("voices", [])}
    except _requests.RequestException as exc:
        log.error("Error fetching ElevenLabs voices: %s", exc)
        raise RuntimeError(f"Error fetching voices: {exc}") from exc


def _voices_openai(cfg) -> dict[str, str]:
    """Fetch voices from a custom OpenAI-compatible endpoint or return defaults."""
    if cfg.TTS_OPENAI_API_BASE_URL.startswith("https://api.openai.com"):
        return dict(OPENAI_VOICES)

    try:
        response = _requests.get(f"{cfg.TTS_OPENAI_API_BASE_URL}/audio/voices")
        response.raise_for_status()
        data = response.json()
        return {v["id"]: v["name"] for v in data.get("voices", [])}
    except Exception as exc:
        log.error("Error fetching voices from custom endpoint: %s", exc)
        return dict(OPENAI_VOICES)


def _voices_azure(cfg) -> dict[str, str]:
    """Fetch voices from Azure Cognitive Services."""
    region = cfg.TTS_AZURE_SPEECH_REGION
    url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/voices/list"
    headers = {"Ocp-Apim-Subscription-Key": cfg.TTS_API_KEY}

    try:
        response = _requests.get(url, headers=headers)
        response.raise_for_status()
        voices = response.json()
        return {
            v["ShortName"]: f"{v['DisplayName']} ({v['ShortName']})"
            for v in voices
        }
    except _requests.RequestException as exc:
        log.error("Error fetching Azure voices: %s", exc)
        return {}


def get_available_voices(request: Request) -> dict[str, str]:
    """Return ``{voice_id: voice_name}`` for the configured TTS engine."""
    cfg = request.app.state.config
    engine = cfg.TTS_ENGINE

    if engine == "openai":
        return _voices_openai(cfg)
    if engine == "elevenlabs":
        try:
            return get_elevenlabs_voices(cfg.TTS_API_KEY)
        except Exception:
            return {}
    if engine == "azure":
        return _voices_azure(cfg)
    return {}


@router.get("/voices")
async def get_voices(request: Request, user=Depends(get_verified_user)):
    """List available TTS voices for the current engine."""
    return {
        "voices": [
            {"id": k, "name": v} for k, v in get_available_voices(request).items()
        ]
    }


# ---------------------------------------------------------------------------
# Model listing
# ---------------------------------------------------------------------------


def _models_openai(cfg) -> list[dict]:
    """Fetch TTS models from a custom OpenAI-compatible endpoint or return defaults."""
    defaults = [{"id": "tts-1"}, {"id": "tts-1-hd"}]
    if cfg.TTS_OPENAI_API_BASE_URL.startswith("https://api.openai.com"):
        return defaults

    try:
        response = _requests.get(f"{cfg.TTS_OPENAI_API_BASE_URL}/audio/models")
        response.raise_for_status()
        data = response.json()
        return data.get("models", defaults)
    except Exception as exc:
        log.error("Error fetching models from custom endpoint: %s", exc)
        return defaults


def _models_elevenlabs(cfg) -> list[dict]:
    """Fetch TTS models from ElevenLabs."""
    try:
        response = _requests.get(
            "https://api.elevenlabs.io/v1/models",
            headers={"xi-api-key": cfg.TTS_API_KEY, "Content-Type": "application/json"},
            timeout=5,
        )
        response.raise_for_status()
        models = response.json()
        return [{"name": m["name"], "id": m["model_id"]} for m in models]
    except _requests.RequestException as exc:
        log.error("Error fetching ElevenLabs models: %s", exc)
        return []


def get_available_models(request: Request) -> list[dict]:
    """Return available TTS models for the configured engine."""
    cfg = request.app.state.config
    engine = cfg.TTS_ENGINE

    if engine == "openai":
        return _models_openai(cfg)
    if engine == "elevenlabs":
        return _models_elevenlabs(cfg)
    return []


@router.get("/models")
async def get_models(request: Request, user=Depends(get_verified_user)):
    """List available TTS models for the current engine."""
    return {"models": get_available_models(request)}
