"""
Anthropic Claude provider – native Messages API.

Claude uses a different request/response schema from OpenAI:
  - System prompt is a top-level parameter, not a message
  - Streaming uses SSE with specific event types (message_start, content_block_start, etc.)
  - API key goes in x-api-key header, version in anthropic-version header

We translate between OpenAI format ↔ Claude format at the boundary.
"""

import logging
from typing import Any, Optional

import orjson

from fastapi import HTTPException, Request
from starlette.responses import StreamingResponse

from bcgpt.models import UserModel
from bcgpt.providers.base import BaseLLMProvider
from bcgpt.utils.http_client import get_client_session

log = logging.getLogger(__name__)

_ANTHROPIC_VERSION = "2023-06-01"


def _openai_messages_to_claude(messages: list[dict]) -> tuple[str, list[dict]]:
    """Convert OpenAI messages → Claude Messages API format.

    Returns (system_prompt, claude_messages).
    """
    system_parts = []
    claude_messages = []

    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            system_parts.append(_content_to_text(content, msg))
            continue

        if role == "assistant":
            claude_role = "assistant"
        elif role == "tool":
            claude_role = "user"
        else:
            claude_role = "user"

        claude_content = _content_to_claude_content(content, msg)
        if claude_content:
            claude_messages.append({"role": claude_role, "content": claude_content})

    if not claude_messages:
        claude_messages.append({"role": "user", "content": " "})

    merged_system = "\n\n".join(system_parts) if system_parts else ""
    return merged_system, claude_messages


def _content_to_text(content: Any, msg: dict) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for item in content:
            if item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "\n".join(texts)
    return ""


def _content_to_claude_content(content: Any, msg: dict) -> list[dict]:
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    if isinstance(content, list):
        blocks = []
        for item in content:
            if item.get("type") == "text":
                blocks.append({"type": "text", "text": item.get("text", "")})
            elif item.get("type") == "image_url":
                url = item.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    mime_end = url.index(";")
                    mime_type = url[5:mime_end]
                    b64_data = url[url.index(",") + 1 :]
                    blocks.append(
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": b64_data,
                            },
                        }
                    )
                else:
                    blocks.append({"type": "text", "text": url})
        return blocks
    return [{"type": "text", "text": ""}]


def _claude_response_to_openai(claude_resp: dict, model: str) -> dict:
    """Convert Claude Messages response → OpenAI-compatible response."""
    content_blocks = claude_resp.get("content", [])
    text_parts = []
    thinking_parts = []

    for block in content_blocks:
        if block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif block.get("type") == "thinking":
            thinking_parts.append(block.get("thinking", ""))

    full_text = "".join(text_parts)
    if thinking_parts:
        thinking = "\n".join(thinking_parts)
        full_text = f'<think type="thinking">\n{thinking}\n</think\n{full_text}'

    stop_reason = claude_resp.get("stop_reason", "end_turn")
    finish_reason_map = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    finish_reason = finish_reason_map.get(stop_reason, "stop")

    usage = claude_resp.get("usage", {})
    return {
        "id": claude_resp.get("id", "chatcmpl-claude"),
        "object": "chat.completion",
        "created": 0,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": full_text,
                },
                "finish_reason": finish_reason,
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("input_tokens", 0),
            "completion_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("input_tokens", 0)
            + usage.get("output_tokens", 0),
        },
    }


def _claude_stream_chunk_to_openai(
    event_type: str, data: dict, model: str
) -> list[dict]:
    """Convert a single Claude SSE event → list of OpenAI SSE chunks."""
    chunks = []

    if event_type == "message_start":
        chunks.append(
            {
                "id": data.get("message", {}).get("id", "chatcmpl-claude"),
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": ""},
                        "finish_reason": None,
                    }
                ],
            }
        )
    elif event_type == "content_block_start":
        block = data.get("content_block", {})
        if block.get("type") == "thinking":
            chunks.append(
                {
                    "id": "chatcmpl-claude",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": '<think type="thinking">\n'},
                            "finish_reason": None,
                        }
                    ],
                }
            )
        elif block.get("type") == "text":
            text = block.get("text", "")
            if text:
                chunks.append(
                    {
                        "id": "chatcmpl-claude",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
    elif event_type == "content_block_delta":
        delta = data.get("delta", {})
        if delta.get("type") == "thinking_delta":
            text = delta.get("thinking", "")
            if text:
                chunks.append(
                    {
                        "id": "chatcmpl-claude",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
        elif delta.get("type") == "text_delta":
            text = delta.get("text", "")
            if text:
                chunks.append(
                    {
                        "id": "chatcmpl-claude",
                        "object": "chat.completion.chunk",
                        "created": 0,
                        "model": model,
                        "choices": [
                            {
                                "index": 0,
                                "delta": {"content": text},
                                "finish_reason": None,
                            }
                        ],
                    }
                )
    elif event_type == "content_block_stop":
        block = data.get("content_block", {})
        if block.get("type") == "thinking":
            chunks.append(
                {
                    "id": "chatcmpl-claude",
                    "object": "chat.completion.chunk",
                    "created": 0,
                    "model": model,
                    "choices": [
                        {
                            "index": 0,
                            "delta": {"content": "\n</think\n"},
                            "finish_reason": None,
                        }
                    ],
                }
            )
    elif event_type == "message_delta":
        stop_reason = data.get("delta", {}).get("stop_reason", "end_turn")
        finish_reason_map = {
            "end_turn": "stop",
            "max_tokens": "length",
            "stop_sequence": "stop",
            "tool_use": "tool_calls",
        }
        chunks.append(
            {
                "id": "chatcmpl-claude",
                "object": "chat.completion.chunk",
                "created": 0,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {},
                        "finish_reason": finish_reason_map.get(stop_reason, "stop"),
                    }
                ],
            }
        )

    return chunks


class ClaudeProvider(BaseLLMProvider):
    provider_name = "claude"

    def _get_api_key(self, request: Request) -> str:
        keys = getattr(self.config, "CLAUDE_API_KEYS", [])
        if isinstance(keys, list) and keys:
            return keys[0]
        key = getattr(self.config, "CLAUDE_API_KEY", "")
        return key

    def _get_base_url(self, request: Request) -> str:
        url = getattr(self.config, "CLAUDE_API_BASE_URL", "")
        if not url:
            url = "https://api.anthropic.com"
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
            raise HTTPException(status_code=500, detail="Claude API key not configured")

        base_url = self._get_base_url(request)
        model_id = form_data.get("model", "claude-sonnet-4-20250514")

        stream = form_data.get("stream", False)
        messages = form_data.get("messages", [])

        system_prompt, claude_messages = _openai_messages_to_claude(messages)

        body: dict[str, Any] = {
            "model": model_id,
            "messages": claude_messages,
            "max_tokens": 8192,
            "stream": stream,
        }

        if system_prompt:
            body["system"] = system_prompt

        params = form_data.get("params", {})
        if params.get("temperature") is not None:
            body["temperature"] = params["temperature"]
        if params.get("max_tokens") is not None:
            body["max_tokens"] = params["max_tokens"]
        if params.get("top_p") is not None:
            body["top_p"] = params["top_p"]
        if params.get("stop"):
            body["stop_sequences"] = (
                params["stop"] if isinstance(params["stop"], list) else [params["stop"]]
            )

        url = f"{base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }

        session = await get_client_session()

        if stream:
            r = await session.post(url, json=body, headers=headers)
            if r.status != 200:
                err = await r.text()
                raise HTTPException(status_code=r.status, detail=f"Claude: {err}")

            async def _stream_generator():
                current_event = None
                async for line in r.content:
                    decoded = line.decode("utf-8").strip()
                    if decoded.startswith("event: "):
                        current_event = decoded[7:]
                        continue
                    if decoded.startswith("data: "):
                        json_str = decoded[6:]
                        if current_event == "ping":
                            continue
                        try:
                            data = orjson.loads(json_str)
                            chunks = _claude_stream_chunk_to_openai(
                                current_event or "", data, model_id
                            )
                            for chunk in chunks:
                                yield f"data: {orjson.dumps(chunk).decode()}\n\n"
                        except Exception:
                            continue
                yield "data: [DONE]\n\n"
                r.close()

            return StreamingResponse(
                _stream_generator(),
                status_code=200,
                headers={"Content-Type": "text/event-stream"},
            )
        else:
            async with session.post(url, json=body, headers=headers) as r:
                if r.status != 200:
                    err = await r.text()
                    raise HTTPException(status_code=r.status, detail=f"Claude: {err}")
                resp = await r.json()
                return _claude_response_to_openai(resp, model_id)

    async def get_models(
        self, request: Request, user: Optional[UserModel] = None
    ) -> list[dict]:
        api_key = self._get_api_key(request)
        if not api_key:
            return []

        known_models = [
            ("claude-sonnet-4-20250514", "Claude Sonnet 4"),
            ("claude-opus-4-20250514", "Claude Opus 4"),
            ("claude-3-7-sonnet-20250219", "Claude 3.7 Sonnet"),
            ("claude-3-5-haiku-20241022", "Claude 3.5 Haiku"),
        ]
        return [
            {"id": mid, "name": name, "owned_by": "claude", "claude": {"id": mid}}
            for mid, name in known_models
        ]

    async def verify_connection(self, request: Request, user: UserModel) -> dict:
        api_key = self._get_api_key(request)
        if not api_key:
            raise HTTPException(status_code=400, detail="Claude API key not set")

        base_url = self._get_base_url(request)
        url = f"{base_url}/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": _ANTHROPIC_VERSION,
        }
        body = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1,
            "messages": [{"role": "user", "content": "hi"}],
        }

        try:
            session = await get_client_session()
            async with session.post(url, json=body, headers=headers) as r:
                if r.status != 200:
                    err = await r.text()
                    raise HTTPException(status_code=r.status, detail=f"Claude: {err}")
                return {"status": True}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Claude: {str(e)}")
