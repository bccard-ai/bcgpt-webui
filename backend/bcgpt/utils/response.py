"""Ollama-to-OpenAI response format converters.

Transforms Ollama completion and streaming responses into the
OpenAI-compatible format used throughout BCGPT WebUI.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional
from uuid import uuid4

import orjson

from bcgpt.utils.misc import (
    openai_chat_chunk_message_template,
    openai_chat_completion_message_template,
)


# ---------------------------------------------------------------------------
# Tool-call conversion
# ---------------------------------------------------------------------------


def convert_ollama_tool_call_to_openai(tool_calls: list) -> List[Dict[str, Any]]:
    """Convert Ollama tool calls to the OpenAI function-calling format.

    Args:
        tool_calls: List of Ollama tool-call dicts.

    Returns:
        List of OpenAI-compatible tool-call dicts with ``id``, ``type``,
        and ``function`` keys.
    """
    openai_tool_calls: List[Dict[str, Any]] = []
    for tool_call in tool_calls:
        openai_tool_calls.append(
            {
                "index": tool_call.get("index", 0),
                "id": tool_call.get("id", f"call_{uuid4()}"),
                "type": "function",
                "function": {
                    "name": tool_call.get("function", {}).get("name", ""),
                    "arguments": orjson.dumps(
                        tool_call.get("function", {}).get("arguments", {})
                    ).decode(),
                },
            }
        )
    return openai_tool_calls


# ---------------------------------------------------------------------------
# Usage conversion
# ---------------------------------------------------------------------------


def convert_ollama_usage_to_openai(data: Dict[str, Any]) -> Dict[str, Any]:
    """Map Ollama timing/usage metrics to the OpenAI usage format.

    Includes throughput calculations (tokens/second), raw durations,
    and an approximate human-readable total.

    Args:
        data: Raw Ollama response dict containing ``eval_count``,
            ``eval_duration``, ``prompt_eval_count``, etc.

    Returns:
        Dict with both OpenAI-standard keys (``prompt_tokens``,
        ``completion_tokens``, ``total_tokens``) and Ollama-specific
        diagnostic fields.
    """
    eval_count = data.get("eval_count", 0)
    eval_duration = data.get("eval_duration", 0)
    prompt_eval_count = data.get("prompt_eval_count", 0)
    prompt_eval_duration = data.get("prompt_eval_duration", 0)
    total_duration = data.get("total_duration", 0) or 0

    def _throughput(count: int, duration_ns: int) -> str | float:
        if duration_ns <= 0:
            return "N/A"
        return round((count / (duration_ns / 10_000_000)) * 100, 2)

    def _fmt_duration(ns: int) -> str:
        s = ns // 1_000_000_000
        return f"{s // 3600}h{(s % 3600) // 60}m{s % 60}s"

    return {
        "response_token/s": _throughput(eval_count, eval_duration),
        "prompt_token/s": _throughput(prompt_eval_count, prompt_eval_duration),
        "total_duration": data.get("total_duration", 0),
        "load_duration": data.get("load_duration", 0),
        "prompt_eval_count": prompt_eval_count,
        "prompt_tokens": int(prompt_eval_count),
        "prompt_eval_duration": data.get("prompt_eval_duration", 0),
        "eval_count": eval_count,
        "completion_tokens": int(eval_count),
        "eval_duration": data.get("eval_duration", 0),
        "approximate_total": _fmt_duration(total_duration),
        "total_tokens": int(prompt_eval_count + eval_count),
        "completion_tokens_details": {
            "reasoning_tokens": 0,
            "accepted_prediction_tokens": 0,
            "rejected_prediction_tokens": 0,
        },
    }


# ---------------------------------------------------------------------------
# Non-streaming conversion
# ---------------------------------------------------------------------------


def convert_response_ollama_to_openai(ollama_response: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a complete Ollama response to the OpenAI format.

    Args:
        ollama_response: Raw Ollama completion dict.

    Returns:
        OpenAI-compatible ``chat.completion`` response dict.
    """
    model = ollama_response.get("model", "ollama")
    message_content = ollama_response.get("message", {}).get("content", "")
    tool_calls = ollama_response.get("message", {}).get("tool_calls")

    openai_tool_calls = (
        convert_ollama_tool_call_to_openai(tool_calls) if tool_calls else None
    )
    usage = convert_ollama_usage_to_openai(ollama_response)

    return openai_chat_completion_message_template(
        model, message_content, openai_tool_calls, usage
    )


# ---------------------------------------------------------------------------
# Streaming conversion
# ---------------------------------------------------------------------------


async def convert_streaming_response_ollama_to_openai(
    ollama_streaming_response: Any,
) -> AsyncIterator[str]:
    """Convert a streaming Ollama response into OpenAI SSE chunks.

    Content chunks are buffered (up to 3 items) before emission to reduce
    overhead.  Tool calls, ``done`` markers, and empty-content frames
    trigger an immediate flush.

    Args:
        ollama_streaming_response: Async iterable yielding Ollama streaming
            data objects with a ``body_iterator`` attribute.

    Yields:
        SSE-formatted strings (``"data: {json}\\n\\n"``) and a final
        ``"data: [DONE]\\n\\n"`` sentinel.
    """
    buffer: List[str] = []
    BUFFER_SIZE = 3

    async for raw in ollama_streaming_response.body_iterator:
        data = orjson.loads(raw)

        model = data.get("model", "ollama")
        message_content = data.get("message", {}).get("content")
        tool_calls = data.get("message", {}).get("tool_calls")
        done = data.get("done", False)

        openai_tool_calls = (
            convert_ollama_tool_call_to_openai(tool_calls) if tool_calls else None
        )
        usage = convert_ollama_usage_to_openai(data) if done else None

        should_flush = tool_calls or done or message_content is None

        # Buffer plain content for batching
        if not should_flush and message_content is not None and not openai_tool_calls:
            buffer.append(message_content)
            if len(buffer) >= BUFFER_SIZE:
                combined = "".join(buffer)
                buffer.clear()
                chunk = openai_chat_chunk_message_template(model, combined)
                yield f"data: {orjson.dumps(chunk).decode()}\n\n"
            continue

        # Flush buffered content before special frames
        if buffer:
            combined = "".join(buffer)
            buffer.clear()
            chunk = openai_chat_chunk_message_template(model, combined)
            yield f"data: {orjson.dumps(chunk).decode()}\n\n"

        chunk = openai_chat_chunk_message_template(
            model, message_content, openai_tool_calls, usage
        )
        yield f"data: {orjson.dumps(chunk).decode()}\n\n"

    # Final buffer flush
    if buffer:
        combined = "".join(buffer)
        buffer.clear()
        chunk = openai_chat_chunk_message_template(model, combined)
        yield f"data: {orjson.dumps(chunk).decode()}\n\n"

    yield "data: [DONE]\n\n"
