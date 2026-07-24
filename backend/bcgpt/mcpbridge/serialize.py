"""Stringify an MCP CallToolResult for tools_dict callable consumption."""

from __future__ import annotations

MAX_CHARS = 8192


def stringify_call_result(result) -> str:
    """Flatten a ``CallToolResult``'s content blocks into a single string.

    Honours ``isError`` (server-side tool failure is surfaced, not raised) and
    truncates over-long output to protect the chat context window.
    """
    parts: list[str] = []
    for block in getattr(result, "content", []) or []:
        t = getattr(block, "type", None)
        if t == "text":
            parts.append(getattr(block, "text", ""))
        elif t == "image":
            parts.append(
                f"[image/{getattr(block, 'mimeType', '?')}: {getattr(block, 'data', '')}]"
            )
        elif t == "audio":
            parts.append(f"[audio/{getattr(block, 'mimeType', '?')}]")
        elif t == "resource":
            parts.append(f"[resource {getattr(block, 'uri', '')}]")
        # unknown block types are skipped
    text = "\n".join(p for p in parts if p)
    if getattr(result, "isError", False):
        text = f"[MCP tool error] {text}"
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n…[truncated]"
    return text
