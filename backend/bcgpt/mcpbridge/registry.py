"""Build tools_dict descriptors for MCP tools (server-side executed)."""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.mcpbridge.client import DEFAULT_TIMEOUT, McpClient


def namespace_tool_name(server_id: str, tool_name: str) -> str:
    """Namespaced tool key so MCP tools never collide with DB Tools / read_skill / tool_servers."""
    safe = "".join(c if c.isalnum() else "_" for c in str(server_id))
    return f"mcp__{safe}__{tool_name}"


def make_mcp_tool_descriptor(server_cfg: dict, mcp_tool: Any) -> dict:
    """Return a ``tools_dict`` descriptor for one MCP tool (NO 'direct' key)."""
    server_id = server_cfg["id"]
    spec = {
        "name": namespace_tool_name(server_id, mcp_tool.name),
        "description": getattr(mcp_tool, "description", None)
        or f"MCP tool {mcp_tool.name}",
        "parameters": getattr(mcp_tool, "inputSchema", None)
        or {"type": "object", "properties": {}},
    }
    raw_name = mcp_tool.name

    async def _callable(*, timeout: float = DEFAULT_TIMEOUT, **params):
        # Per-call short-lived client (no shared session state in Phase 2).
        client = McpClient(server_cfg)
        try:
            await client.connect()
            return await client.call_tool(raw_name, params, timeout=timeout)
        except asyncio.TimeoutError:
            return f"[MCP tool '{raw_name}' timed out after {timeout}s]"
        except Exception as e:  # noqa: BLE001
            return f"[MCP tool '{raw_name}' error: {e}]"
        finally:
            try:
                await client.close()
            except Exception:
                pass

    return {"spec": spec, "callable": _callable, "toolkit_id": f"__mcp__:{server_id}"}
