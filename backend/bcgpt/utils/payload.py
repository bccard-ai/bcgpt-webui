"""LLM request payload construction and format conversion.

Provides helpers to apply model-level parameters and system prompts to chat
request payloads, as well as converters between OpenAI and Ollama wire
formats.

Public exports (re-exported from ``bcgpt.utils.__init__``):
    apply_model_params_to_body, apply_model_params_to_body_ollama,
    apply_model_params_to_body_openai, apply_model_system_prompt_to_body,
    convert_messages_openai_to_ollama, convert_payload_openai_to_ollama
"""

from __future__ import annotations

import html as html_module
import json
from typing import Callable, Optional

from bcgpt.utils import prompt_template, prompt_variables_template
from bcgpt.utils.misc import add_or_update_system_message


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_user_input(value: Optional[str]) -> Optional[str]:
    """HTML-escape a user-supplied string, returning ``None`` for ``None``."""
    if value is None:
        return None
    return html_module.escape(str(value))


def _decode_stop_sequences(sequences: list[str]) -> list[str]:
    """Decode unicode-escaped stop sequences for API compatibility."""
    return [bytes(s, "utf-8").decode("unicode_escape") for s in sequences]


# ---------------------------------------------------------------------------
# OpenAI parameter mappings
# ---------------------------------------------------------------------------

_OPENAI_PARAM_MAPPINGS: dict[str, Callable] = {
    "temperature": float,
    "top_p": float,
    "max_tokens": int,
    "frequency_penalty": float,
    "reasoning_effort": str,
    "verbosity": str,
    "seed": lambda x: x,
    "stop": _decode_stop_sequences,
    "logit_bias": lambda x: x,
    "response_format": dict,
}

_OLLAMA_PARAM_MAPPINGS: dict[str, Callable] = {
    "temperature": float,
    "top_p": float,
    "seed": lambda x: x,
    "mirostat": int,
    "mirostat_eta": float,
    "mirostat_tau": float,
    "num_ctx": int,
    "num_batch": int,
    "num_keep": int,
    "num_predict": int,
    "repeat_last_n": int,
    "top_k": int,
    "min_p": float,
    "typical_p": float,
    "repeat_penalty": float,
    "presence_penalty": float,
    "frequency_penalty": float,
    "penalize_newline": bool,
    "stop": _decode_stop_sequences,
    "numa": bool,
    "num_gpu": int,
    "main_gpu": int,
    "low_vram": bool,
    "vocab_only": bool,
    "use_mmap": bool,
    "use_mlock": bool,
    "num_thread": int,
}

# OpenAI → Ollama parameter name remapping
_OPENAI_TO_OLLAMA_NAMES: dict[str, str] = {
    "max_tokens": "num_predict",
}


# ---------------------------------------------------------------------------
# System prompt application
# ---------------------------------------------------------------------------

def apply_model_system_prompt_to_body(
    params: dict,
    form_data: dict,
    metadata: Optional[dict] = None,
    user=None,
) -> dict:
    """Inject the model's system prompt into the message list.

    If *metadata* contains ``variables``, they are interpolated first
    (WebUI-style usage).  If a *user* object is supplied, its name and
    location are template-substituted (legacy API usage).

    .. note:: *form_data* is mutated in-place and returned.
    """
    system = params.get("system")
    if not system:
        return form_data

    # WebUI metadata variables
    if metadata:
        variables = metadata.get("variables", {})
        if variables:
            system = prompt_variables_template(system, variables)

    # Legacy API user template params
    if user:
        template_params = {
            "user_name": _sanitize_user_input(user.name),
            "user_location": _sanitize_user_input(
                user.info.get("location") if user.info else None,
            ),
        }
    else:
        template_params = {}

    system = prompt_template(system, **template_params)

    form_data["messages"] = add_or_update_system_message(
        system, form_data.get("messages", []),
    )
    return form_data


# ---------------------------------------------------------------------------
# Generic & provider-specific param application
# ---------------------------------------------------------------------------

def apply_model_params_to_body(
    params: dict,
    form_data: dict,
    mappings: dict[str, Callable],
) -> dict:
    """Apply model parameters to *form_data* using *mappings* for type coercion.

    Each entry in *mappings* maps a parameter name to a callable that casts
    the raw value to the expected type.  Parameters absent from *params* are
    skipped.

    .. note:: *form_data* is mutated in-place and returned.
    """
    if not params:
        return form_data

    for key, cast_func in mappings.items():
        if (value := params.get(key)) is not None:
            form_data[key] = cast_func(value)

    return form_data


def apply_model_params_to_body_openai(params: dict, form_data: dict) -> dict:
    """Apply model parameters using the OpenAI parameter schema.

    .. note:: *form_data* is mutated in-place and returned.
    """
    return apply_model_params_to_body(params, form_data, _OPENAI_PARAM_MAPPINGS)


def apply_model_params_to_body_ollama(params: dict, form_data: dict) -> dict:
    """Apply model parameters using the Ollama parameter schema.

    Remaps OpenAI-style parameter names (e.g. ``max_tokens`` →
    ``num_predict``) and hoists ``keep_alive`` / ``format`` out of the
    ``options`` dict when present.

    .. note:: Both *params* and *form_data* are mutated in-place.
    """
    # Remap parameter names
    for openai_name, ollama_name in _OPENAI_TO_OLLAMA_NAMES.items():
        if (param := params.get(openai_name)) is not None:
            params[ollama_name] = params[openai_name]
            del params[openai_name]

    # Hoist keep_alive and format out of options
    options = form_data.get("options", {})
    if "keep_alive" in options:
        form_data["keep_alive"] = options["keep_alive"]
        del options["keep_alive"]
    if "format" in options:
        form_data["format"] = options["format"]
        del options["format"]

    return apply_model_params_to_body(params, form_data, _OLLAMA_PARAM_MAPPINGS)


# ---------------------------------------------------------------------------
# OpenAI → Ollama message conversion
# ---------------------------------------------------------------------------

def convert_messages_openai_to_ollama(messages: list[dict]) -> list[dict]:
    """Convert an OpenAI-style message list to Ollama-compatible format.

    Handles plain-text content, multi-part content (text + images), and
    tool-call messages.  Base64 data-URL images are stripped of their prefix
    so that Ollama receives only the raw base64 payload.
    """
    ollama_messages: list[dict] = []

    for message in messages:
        new_message: dict = {"role": message["role"]}
        content = message.get("content", [])
        tool_calls = message.get("tool_calls")
        tool_call_id = message.get("tool_call_id")

        if isinstance(content, str) and not tool_calls:
            new_message["content"] = content
            if tool_call_id:
                new_message["tool_call_id"] = tool_call_id

        elif tool_calls:
            ollama_tool_calls = []
            for tool_call in tool_calls:
                ollama_tool_calls.append({
                    "index": tool_call.get("index", 0),
                    "id": tool_call.get("id"),
                    "function": {
                        "name": tool_call.get("function", {}).get("name", ""),
                        "arguments": json.loads(
                            tool_call.get("function", {}).get("arguments", {}),
                        ),
                    },
                })
            new_message["tool_calls"] = ollama_tool_calls
            new_message["content"] = ""

        else:
            # Multi-part content: text segments + image URLs
            text_parts: list[str] = []
            images: list[str] = []

            for item in content:
                if item.get("type") == "text":
                    text_parts.append(item.get("text", ""))
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        if img_url.startswith("data:"):
                            img_url = img_url.split(",")[-1]
                        images.append(img_url)

            if text_parts:
                new_message["content"] = "".join(text_parts).strip()
            if images:
                new_message["images"] = images

        ollama_messages.append(new_message)

    return ollama_messages


# ---------------------------------------------------------------------------
# Full payload conversion
# ---------------------------------------------------------------------------

def convert_payload_openai_to_ollama(openai_payload: dict) -> dict:
    """Convert an OpenAI-format chat completion payload to Ollama format.

    Remaps ``max_tokens`` → ``num_predict`` and ``system`` from inside
    ``options`` to a top-level key.  Extracts ``keep_alive`` when present.
    Converts ``response_format`` JSON-schema to Ollama's ``format`` field.
    """
    ollama_payload: dict = {
        "model": openai_payload.get("model"),
        "messages": convert_messages_openai_to_ollama(
            openai_payload.get("messages", []),
        ),
        "stream": openai_payload.get("stream", False),
    }

    # Carry over optional top-level fields
    if "tools" in openai_payload:
        ollama_payload["tools"] = openai_payload["tools"]
    if "format" in openai_payload:
        ollama_payload["format"] = openai_payload["format"]
    if "metadata" in openai_payload:
        ollama_payload["metadata"] = openai_payload["metadata"]

    # Process options block
    if openai_payload.get("options"):
        ollama_options = dict(openai_payload["options"])

        if "max_tokens" in ollama_options:
            ollama_options["num_predict"] = ollama_options.pop("max_tokens")

        if "system" in ollama_options:
            ollama_payload["system"] = ollama_options.pop("system")

        if "keep_alive" in ollama_options:
            ollama_payload["keep_alive"] = ollama_options.pop("keep_alive")

        ollama_payload["options"] = ollama_options

    # Remap top-level stop → options.stop
    if "stop" in openai_payload:
        ollama_options = ollama_payload.get("options", {})
        ollama_options["stop"] = openai_payload["stop"]
        ollama_payload["options"] = ollama_options

    # Convert response_format JSON schema to Ollama format
    if "response_format" in openai_payload:
        response_format = openai_payload["response_format"]
        format_type = response_format.get("type")
        schema = response_format.get(format_type) if format_type else None
        if schema and isinstance(schema, dict):
            format_schema = schema.get("schema")
            if format_schema:
                ollama_payload["format"] = format_schema

    return ollama_payload
