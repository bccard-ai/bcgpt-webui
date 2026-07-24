"""General-purpose utility functions for BCGPT WebUI.

Covers message-list manipulation, OpenAI-compatible response templates,
hashing, email validation, filename sanitisation, duration parsing,
Ollama modelfile parsing, and logit-bias conversion.

All public names are re-exported through ``bcgpt.utils.__init__``.
"""

from __future__ import annotations

import collections.abc
import hashlib
import json
import logging
import re
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bcgpt.env import SRC_LOG_LEVELS

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# ---------------------------------------------------------------------------
# Pre-compiled patterns
# ---------------------------------------------------------------------------

_RE_EMAIL = re.compile(r"[^@]+@[^@]+\.[^@]+")
_RE_SANITIZE_SPECIAL = re.compile(r"[^\w\s]")
_RE_SANITIZE_SPACES = re.compile(r"\s+")
_RE_DURATION = re.compile(r"(-?\d+(?:\.\d+)?)(ms|s|m|h|d|w)")


# ---------------------------------------------------------------------------
# Dict helpers
# ---------------------------------------------------------------------------


def deep_update(d: dict, u: dict) -> dict:
    """Recursively merge *u* into *d* (in-place) and return *d*.

    Nested mappings are merged recursively; all other values are replaced.

    Args:
        d: Target dict (mutated in-place).
        u: Source dict whose entries are merged into *d*.

    Returns:
        The same *d* dict with all updates applied.
    """
    for key, value in u.items():
        if isinstance(value, collections.abc.Mapping):
            d[key] = deep_update(d.get(key, {}), value)
        else:
            d[key] = value
    return d


# ---------------------------------------------------------------------------
# Message-list helpers
# ---------------------------------------------------------------------------


def get_message_list(messages: dict, message_id: str) -> Optional[List[dict]]:
    """Reconstruct an ordered message chain from *messages* ending at *message_id*.

    Follows ``parentId`` links from the target back to the root.

    Args:
        messages: Dict mapping message IDs to message dicts.
        message_id: ID of the last message in the desired chain.

    Returns:
        Ordered list of messages (root first), or ``None`` when
        *message_id* is absent from *messages*.
    """
    current = messages.get(message_id)
    if not current:
        return None

    chain: List[dict] = []
    while current:
        chain.insert(0, current)
        parent_id = current.get("parentId")
        current = messages.get(parent_id) if parent_id else None
    return chain


def get_messages_content(messages: List[dict]) -> str:
    """Join all message contents into a single string (``ROLE: content``)."""
    return "\n".join(
        f"{msg['role'].upper()}: {get_content_from_message(msg)}" for msg in messages
    )


def get_content_from_message(message: dict) -> Optional[str]:
    """Extract the text content from a message that may use structured content.

    Supports both plain-string ``content`` and the OpenAI-style list-of-parts
    format (returns the first part of type ``"text"``).

    Args:
        message: A message dict with a ``"content"`` key.

    Returns:
        Extracted text string, or ``None`` when no text part is found.
    """
    content = message["content"]
    if isinstance(content, list):
        for part in content:
            if part.get("type") == "text":
                return part["text"]
        return None
    return content


# ---------------------------------------------------------------------------
# Last-message lookups
# ---------------------------------------------------------------------------


def get_last_user_message_item(messages: List[dict]) -> Optional[dict]:
    """Return the last message dict with ``role == "user"``, or ``None``."""
    return next((m for m in reversed(messages) if m["role"] == "user"), None)


def get_last_user_message(messages: List[dict]) -> Optional[str]:
    """Return the text content of the last user message, or ``None``."""
    item = get_last_user_message_item(messages)
    return get_content_from_message(item) if item else None


def get_last_assistant_message_item(messages: List[dict]) -> Optional[dict]:
    """Return the last message dict with ``role == "assistant"``, or ``None``."""
    return next((m for m in reversed(messages) if m["role"] == "assistant"), None)


def get_last_assistant_message(messages: List[dict]) -> Optional[str]:
    """Return the text content of the last assistant message, or ``None``."""
    for msg in reversed(messages):
        if msg["role"] == "assistant":
            return get_content_from_message(msg)
    return None


# ---------------------------------------------------------------------------
# System-message helpers
# ---------------------------------------------------------------------------


def get_system_message(messages: List[dict]) -> Optional[dict]:
    """Return the first system message, or ``None``."""
    return next((m for m in messages if m["role"] == "system"), None)


def remove_system_message(messages: List[dict]) -> List[dict]:
    """Return a copy of *messages* with all system messages removed."""
    return [m for m in messages if m["role"] != "system"]


def pop_system_message(messages: List[dict]) -> Tuple[Optional[dict], List[dict]]:
    """Split *messages* into ``(system_message, remaining)``.

    Returns ``(None, messages)`` when no system message is present.
    """
    return get_system_message(messages), remove_system_message(messages)


# ---------------------------------------------------------------------------
# Message mutation helpers
# ---------------------------------------------------------------------------


def prepend_to_first_user_message_content(
    content: str,
    messages: List[dict],
) -> List[dict]:
    """Prepend *content* to the first user message's text (in-place).

    Handles both plain-string and structured (list-of-parts) content formats.

    Args:
        content: Text to prepend.
        messages: Message list (mutated in-place).

    Returns:
        The same *messages* list.
    """
    for msg in messages:
        if msg["role"] == "user":
            if isinstance(msg["content"], list):
                for part in msg["content"]:
                    if part.get("type") == "text":
                        part["text"] = f"{content}\n{part['text']}"
            else:
                msg["content"] = f"{content}\n{msg['content']}"
            break
    return messages


def add_or_update_system_message(content: str, messages: List[dict]) -> List[dict]:
    """Prepend *content* to the first system message, or insert one at index 0.

    Args:
        content: Text to prepend to or create the system message.
        messages: Message list (mutated in-place).

    Returns:
        The same *messages* list.
    """
    if messages and messages[0].get("role") == "system":
        messages[0]["content"] = f"{content}\n{messages[0]['content']}"
    else:
        messages.insert(0, {"role": "system", "content": content})
    return messages


def add_or_update_user_message(content: str, messages: List[dict]) -> List[dict]:
    """Append *content* to the last user message, or add a new one at the end.

    Args:
        content: Text to append or create.
        messages: Message list (mutated in-place).

    Returns:
        The same *messages* list.
    """
    if messages and messages[-1].get("role") == "user":
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        messages.append({"role": "user", "content": content})
    return messages


def append_or_update_assistant_message(
    content: str,
    messages: List[dict],
) -> List[dict]:
    """Append *content* to the last assistant message, or add a new one at the end.

    Args:
        content: Text to append or create.
        messages: Message list (mutated in-place).

    Returns:
        The same *messages* list.
    """
    if messages and messages[-1].get("role") == "assistant":
        messages[-1]["content"] = f"{messages[-1]['content']}\n{content}"
    else:
        messages.append({"role": "assistant", "content": content})
    return messages


# ---------------------------------------------------------------------------
# OpenAI-compatible response templates
# ---------------------------------------------------------------------------


def openai_chat_message_template(model: str) -> dict:
    """Return a minimal OpenAI chat message skeleton (no object type set).

    Args:
        model: Model name embedded in the response ``model`` field.

    Returns:
        Dict with ``id``, ``created``, ``model``, and ``choices`` keys.
    """
    return {
        "id": f"{model}-{uuid.uuid4()}",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "logprobs": None, "finish_reason": None}],
    }


def openai_chat_chunk_message_template(
    model: str,
    content: Optional[str] = None,
    tool_calls: Optional[List[dict]] = None,
    usage: Optional[dict] = None,
) -> dict:
    """Build a ``chat.completion.chunk`` response dict.

    Sets ``finish_reason`` to ``"stop"`` when neither *content* nor
    *tool_calls* is provided (final chunk).

    Args:
        model: Model name.
        content: Delta content for this chunk.
        tool_calls: Tool call deltas (if any).
        usage: Token usage metadata (included on the final chunk).

    Returns:
        Complete chunk dict ready for SSE serialisation.
    """
    template = openai_chat_message_template(model)
    template["object"] = "chat.completion.chunk"
    template["choices"][0]["index"] = 0
    template["choices"][0]["delta"] = {}

    if content:
        template["choices"][0]["delta"]["content"] = content
    if tool_calls:
        template["choices"][0]["delta"]["tool_calls"] = tool_calls
    if not content and not tool_calls:
        template["choices"][0]["finish_reason"] = "stop"
    if usage:
        template["usage"] = usage
    return template


def openai_chat_completion_message_template(
    model: str,
    message: Optional[str] = None,
    tool_calls: Optional[List[dict]] = None,
    usage: Optional[dict] = None,
) -> dict:
    """Build a ``chat.completion`` response dict.

    Args:
        model: Model name.
        message: Assistant message text.
        tool_calls: Tool calls included in the response.
        usage: Token usage metadata.

    Returns:
        Complete completion dict.
    """
    template = openai_chat_message_template(model)
    template["object"] = "chat.completion"
    if message is not None:
        template["choices"][0]["message"] = {
            "content": message,
            "role": "assistant",
            **({"tool_calls": tool_calls} if tool_calls else {}),
        }
    template["choices"][0]["finish_reason"] = "stop"
    if usage:
        template["usage"] = usage
    return template


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


def get_gravatar_url(email: str) -> str:
    """Return the Gravatar avatar URL for *email* (SHA-256, default ``mp``).

    Args:
        email: Email address to hash.

    Returns:
        Fully-qualified Gravatar URL.
    """
    address = str(email).strip().lower()
    hex_digest = hashlib.sha256(address.encode()).hexdigest()
    return f"https://www.gravatar.com/avatar/{hex_digest}?d=mp"


def calculate_sha256(file_path: str, chunk_size: int) -> str:
    """Compute the SHA-256 hex digest of a file, reading in *chunk_size* blocks.

    Args:
        file_path: Path to the file.
        chunk_size: Number of bytes to read per iteration.

    Returns:
        Hex-encoded SHA-256 digest string.
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as fh:
        while chunk := fh.read(chunk_size):
            sha256.update(chunk)
    return sha256.hexdigest()


def calculate_sha256_string(string: str) -> str:
    """Compute the SHA-256 hex digest of a UTF-8 string.

    Args:
        string: Input text.

    Returns:
        Hex-encoded SHA-256 digest.
    """
    return hashlib.sha256(string.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation / sanitisation
# ---------------------------------------------------------------------------


def validate_email_format(email: str) -> bool:
    """Return ``True`` when *email* has a valid format.

    ``@localhost`` addresses are always accepted.

    Args:
        email: Email address to validate.

    Returns:
        ``True`` if the format is acceptable.
    """
    if email.endswith("@localhost"):
        return True
    return bool(_RE_EMAIL.match(email))


def sanitize_filename(file_name: str) -> str:
    """Lower-case, strip special characters, and collapse whitespace into hyphens.

    Args:
        file_name: Raw file name.

    Returns:
        Sanitised, URL-safe file name.
    """
    lower = file_name.lower()
    no_special = _RE_SANITIZE_SPECIAL.sub("", lower)
    return _RE_SANITIZE_SPACES.sub("-", no_special)


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def extract_folders_after_data_docs(path: str) -> List[str]:
    """Return folder segments after ``data/docs/`` in *path* as accumulated tags.

    Example::

        "data/docs/projectA/chapter1/file.pdf"
        → ["projectA", "projectA/chapter1"]

    Args:
        path: File path string to parse.

    Returns:
        List of accumulated folder paths.
    """
    parts = Path(path).parts
    try:
        idx_data = parts.index("data") + 1
        idx_docs = parts.index("docs", idx_data) + 1
    except ValueError:
        return []

    folders = parts[idx_docs:-1]
    return ["/".join(folders[: i + 1]) for i in range(len(folders))]


# ---------------------------------------------------------------------------
# Duration parsing
# ---------------------------------------------------------------------------

_DURATION_UNITS = {
    "ms": lambda v: timedelta(milliseconds=v),
    "s": lambda v: timedelta(seconds=v),
    "m": lambda v: timedelta(minutes=v),
    "h": lambda v: timedelta(hours=v),
    "d": lambda v: timedelta(days=v),
    "w": lambda v: timedelta(weeks=v),
}


def parse_duration(duration: str) -> Optional[timedelta]:
    """Parse a duration string (e.g. ``"1h30m"``, ``"2d"``) into a ``timedelta``.

    Returns ``None`` for ``"-1"`` and ``"0"``.  Raises ``ValueError`` when
    the string contains no recognised units.

    Args:
        duration: Human-readable duration string.

    Returns:
        Corresponding ``timedelta``, or ``None`` for sentinel values.

    Raises:
        ValueError: When no valid duration units are found.
    """
    if duration in ("-1", "0"):
        return None

    matches = _RE_DURATION.findall(duration)
    if not matches:
        raise ValueError("Invalid duration string")

    total = timedelta()
    for number_str, unit in matches:
        total += _DURATION_UNITS[unit](float(number_str))
    return total


# ---------------------------------------------------------------------------
# Ollama modelfile parser
# ---------------------------------------------------------------------------

_OLLAMA_PARAM_TYPES: Dict[str, type] = {
    "mirostat": int,
    "mirostat_eta": float,
    "mirostat_tau": float,
    "num_ctx": int,
    "repeat_last_n": int,
    "repeat_penalty": float,
    "temperature": float,
    "seed": int,
    "tfs_z": float,
    "num_predict": int,
    "top_k": int,
    "top_p": float,
    "num_keep": int,
    "typical_p": float,
    "presence_penalty": float,
    "frequency_penalty": float,
    "penalize_newline": bool,
    "numa": bool,
    "num_batch": int,
    "num_gpu": int,
    "main_gpu": int,
    "low_vram": bool,
    "f16_kv": bool,
    "vocab_only": bool,
    "use_mmap": bool,
    "use_mlock": bool,
    "num_thread": int,
}


def parse_ollama_modelfile(model_text: str) -> dict:
    """Parse an Ollama Modelfile string into a structured dict.

    Extracts the base model, template, stop sequences, typed parameters,
    adapter path, system prompt, and message list.

    Args:
        model_text: Raw Modelfile content.

    Returns:
        ``{"base_model_id": str | None, "params": dict}``
    """
    data: dict = {"base_model_id": None, "params": {}}

    # Base model
    match = re.search(r"^FROM\s+(\w+)", model_text, re.MULTILINE | re.IGNORECASE)
    if match:
        data["base_model_id"] = match.group(1)

    # Template
    match = re.search(r'TEMPLATE\s+"""(.+?)"""', model_text, re.DOTALL | re.IGNORECASE)
    if match:
        data["params"]["template"] = match.group(1).strip()

    # Stop sequences
    stops = re.findall(r'PARAMETER stop "(.*?)"', model_text, re.IGNORECASE)
    if stops:
        data["params"]["stop"] = stops

    # Typed parameters
    for param, param_type in _OLLAMA_PARAM_TYPES.items():
        match = re.search(rf"PARAMETER {param} (.+)", model_text, re.IGNORECASE)
        if not match:
            continue
        raw = match.group(1)
        try:
            if param_type is int:
                value: Any = int(raw)
            elif param_type is float:
                value = float(raw)
            elif param_type is bool:
                value = raw.lower() == "true"
            else:
                value = raw
        except Exception as exc:
            log.exception("Failed to parse parameter %s: %s", param, exc)
            continue
        data["params"][param] = value

    # Adapter
    match = re.search(r"ADAPTER (.+)", model_text, re.IGNORECASE)
    if match:
        data["params"]["adapter"] = match.group(1)

    # System prompt (triple-quoted or single-line)
    match = re.search(r'SYSTEM\s+"""(.+?)"""', model_text, re.DOTALL | re.IGNORECASE)
    if match:
        data["params"]["system"] = match.group(1).strip()
    else:
        match = re.search(r"SYSTEM\s+([^\n]+)", model_text, re.IGNORECASE)
        if match:
            data["params"]["system"] = match.group(1).strip()

    # Messages
    messages = [
        {"role": role, "content": content}
        for role, content in re.findall(r"MESSAGE (\w+) (.+)", model_text, re.IGNORECASE)
    ]
    if messages:
        data["params"]["messages"] = messages

    return data


# ---------------------------------------------------------------------------
# Logit-bias conversion
# ---------------------------------------------------------------------------


def convert_logit_bias_input_to_json(user_input: str) -> str:
    """Convert a comma-separated ``token:bias`` string into a JSON object.

    Bias values are clamped to ``[-100, 100]``.

    Args:
        user_input: Comma-separated pairs, e.g. ``"123:-50,456:100"``.

    Returns:
        JSON string mapping tokens to clamped bias integers.
    """
    result: Dict[str, int] = {}
    for pair in user_input.split(","):
        token, bias_str = pair.split(":")
        token = token.strip()
        bias = max(-100, min(100, int(bias_str.strip())))
        result[token] = bias
    return json.dumps(result)
