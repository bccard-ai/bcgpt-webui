"""
Google Gemini provider – native REST API (generateContent / streamGenerateContent).

Gemini uses a different request/response schema from OpenAI:
  - Messages use "parts" instead of "content"
  - System instruction is a top-level field
  - Streaming returns concatenated JSON objects (not SSE)

We translate between OpenAI format ↔ Gemini format at the boundary.
"""

import logging
import re
from typing import Any, Optional

import orjson

from fastapi import HTTPException, Request
from starlette.responses import StreamingResponse

from bcgpt.models import UserModel
from bcgpt.providers.base import BaseLLMProvider
from bcgpt.utils.http_client import get_client_session

log = logging.getLogger(__name__)

_GEMINI_MODEL_MAP = {
    "gemini-2.5-pro": "gemini-2.5-pro",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.0-flash": "gemini-2.0-flash",
    "gemini-2.0-flash-lite": "gemini-2.0-flash-lite",
}

_RE_THINKING = re.compile(r"<think\b[^>]*>(.*?)</think\s*>", re.DOTALL)


def _openai_messages_to_gemini(messages: list[dict]) -> dict:
    """Convert OpenAI messages → Gemini generateContent request body."""
    system_instruction = None
    contents = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            parts = _content_to_parts(content, msg)
            system_instruction = {"parts": parts}
            continue

        if role == "assistant":
            gemini_role = "model"
        else:
            gemini_role = "user"

        parts = _content_to_parts(content, msg)
        if parts:
            contents.append({"role": gemini_role, "parts": parts})

    if not contents:
        contents.append({"role": "user", "parts": [{"text": ""}]})

    body: dict[str, Any] = {"contents": contents}
    if system_instruction:
        body["systemInstruction"] = system_instruction

    return body


def _content_to_parts(content: Any, msg: dict) -> list[dict]:
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, list):
        parts = []
        for item in content:
            if item.get("type") == "text":
                parts.append({"text": item.get("text", "")})
            elif item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    mime_end = url.index(";")
                    mime_type = url[5:mime_end]
                    b64_data = url[url.index(",") + 1 :]
                    parts.append(
                        {"inline_data": {"mime_type": mime_type, "data": b64_data}}
                    )
                else:
                    parts.append({"text": url})
        return parts
    return []


def _gemini_response_to_openai(
    gemini_resp: dict, model: str, stream: bool = False
) -> dict:
    """Convert Gemini response → OpenAI-compatible response."""
    candidates = gemini_resp.get("candidates", [])
    if not candidates:
        return _empty_openai_response(model)

    candidate = candidates[0]
    content_obj = candidate.get("content", {})
    parts = content_obj.get("parts", [])

    reasoning_text = ""
    text_parts = []
    for part in parts:
        if "text" in part:
            text_parts.append(part["text"])
        if "thought" in part:
            reasoning_text += part.get("thought", "") + "\n"

    full_text = "".join(text_parts)

    if reasoning_text.strip():
        reasoning_text = reasoning_text.strip()
        full_text = f'<think type="thinking">\n{reasoning_text}\n</think\n{full_text}'

    finish_reason = "stop"
    finish_data = candidate.get("finishReason", "")
    if finish_data == "MAX_TOKENS":
        finish_reason = "length"
    elif finish_data == "SAFETY":
        finish_reason = "content_filter"

    usage = gemini_resp.get("usageMetadata", {})

    openai_resp = {
        "id": f"chatcmpl-{gemini_resp.get('responseId', 'gemini')}",
        "object": "chat.completion" if not stream else "chat.completion.chunk",
        "created": gemini_resp.get("createTime", 0),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message" if not stream else "delta": {
                    "role": "assistant",
                    "content": full_text,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("promptTokenCount", 0),
            "completion_tokens": usage.get("candidatesTokenCount", 0),
            "total_tokens": usage.get("totalTokenCount", 0),
        },
    }
    return openai_resp


def _empty_openai_response(model: str) -> dict:
    return {
        "id": "chatcmpl-gemini-empty",
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": ""},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class GeminiProvider(BaseLLMProvider):
    provider_name = "gemini"

    def _get_api_key(self, request: Request) -> str:
        keys = getattr(self.config, "GEMINI_API_KEYS", [])
        if isinstance(keys, list) and keys:
            return keys[0]
        key = getattr(self.config, "GEMINI_API_KEY", "")
        return key

    def _get_base_url(self, request: Request) -> str:
        url = getattr(self.config, "GEMINI_API_BASE_URL", "")
        if not url:
            url = "https://generativelanguage.googleapis.com/v1beta"
        return url.rstrip("/")

    async def chat_completions(
        self,
        request: Request,
        form_data: dict,
        user: UserModel,
        *,
        bypass_filter: bool = False,
    ) -> Any:
        api_key = self._get_api_key(request)
        if not api_key:
            raise HTTPException(status_code=500, detail="Gemini API key not configured")

        base_url = self._get_base_url(request)
        model_id = form_data.get("model", "gemini-2.0-flash")
        api_model = _GEMINI_MODEL_MAP.get(model_id, model_id)

        stream = form_data.get("stream", False)
        messages = form_data.get("messages", [])

        gemini_body = _openai_messages_to_gemini(messages)

        params = form_data.get("params", {})
        if params.get("temperature") is not None:
            gemini_body.setdefault("generationConfig", {})["temperature"] = params[
                "temperature"
            ]
        if params.get("max_tokens") is not None:
            gemini_body.setdefault("generationConfig", {})["maxOutputTokens"] = params[
                "max_tokens"
            ]
        if params.get("top_p") is not None:
            gemini_body.setdefault("generationConfig", {})["topP"] = params["top_p"]

        endpoint = "streamGenerateContent?alt=sse" if stream else "generateContent"
        url = f"{base_url}/models/{api_model}:{endpoint}"

        session = await get_client_session()
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key,
        }

        if stream:
            r = await session.post(url, json=gemini_body, headers=headers)
            if r.status != 200:
                err = await r.text()
                raise HTTPException(status_code=r.status, detail=f"Gemini: {err}")

            async def _stream_generator():
                async for line in r.content:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("data: "):
                        json_str = decoded[6:]
                        if json_str == "[DONE]":
                            yield "data: [DONE]\n\n"
                            continue
                        try:
                            chunk = orjson.loads(json_str)
                            openai_chunk = _gemini_response_to_openai(
                                chunk, model_id, stream=True
                            )
                            yield f"data: {orjson.dumps(openai_chunk).decode()}\n\n"
                        except Exception:
                            continue
                r.close()

            return StreamingResponse(
                _stream_generator(),
                status_code=200,
                headers={"Content-Type": "text/event-stream"},
            )
        else:
            async with session.post(url, json=gemini_body, headers=headers) as r:
                if r.status != 200:
                    err = await r.text()
                    raise HTTPException(status_code=r.status, detail=f"Gemini: {err}")
                resp = await r.json()
                return _gemini_response_to_openai(resp, model_id)

    async def get_models(
        self, request: Request, user: Optional[UserModel] = None
    ) -> list[dict]:
        api_key = self._get_api_key(request)
        if not api_key:
            return []

        base_url = self._get_base_url(request)
        url = f"{base_url}/models?key={api_key}"

        try:
            session = await get_client_session()
            async with session.get(url) as r:
                if r.status != 200:
                    return []
                data = await r.json()
                models = []
                for model in data.get("models", []):
                    name = model.get("name", "").replace("models/", "")
                    if "generateContent" in model.get("supportedGenerationMethods", []):
                        models.append(
                            {
                                "id": name,
                                "name": model.get("displayName", name),
                                "owned_by": "gemini",
                                "gemini": {"id": name},
                            }
                        )
                return models
        except Exception as e:
            log.error(f"Gemini model listing failed: {e}")
            return []

    async def verify_connection(self, request: Request, user: UserModel) -> dict:
        api_key = self._get_api_key(request)
        if not api_key:
            raise HTTPException(status_code=400, detail="Gemini API key not set")

        base_url = self._get_base_url(request)
        url = f"{base_url}/models?key={api_key}"

        try:
            session = await get_client_session()
            async with session.get(url) as r:
                if r.status != 200:
                    err = await r.text()
                    raise HTTPException(status_code=r.status, detail=f"Gemini: {err}")
                return {"status": True, "data": await r.json()}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gemini: {str(e)}")
