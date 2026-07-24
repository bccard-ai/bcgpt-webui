"""Tests for the McpClient wrapper (mocks ClientSession — no network)."""

from __future__ import annotations

import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch

from bcgpt.mcpbridge.client import McpClient

CFG = {
    "id": "s1",
    "name": "n",
    "url": "https://mcp.example.invalid/mcp",
    "token": "tok",
}


def _run(coro):
    """Drive a coroutine on a throwaway event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _patched_transport(session):
    """Patch streamable_http_client + create_mcp_http_client so connect() yields ``session``."""
    tr = MagicMock()
    tr.__aenter__ = AsyncMock(return_value=(MagicMock(), MagicMock(), lambda: None))
    tr.__aexit__ = AsyncMock(return_value=False)
    http_client = MagicMock()
    http_client.__aenter__ = AsyncMock()
    http_client.__aexit__ = AsyncMock()
    return (
        patch("bcgpt.mcpbridge.client.streamable_http_client", return_value=tr),
        patch(
            "bcgpt.mcpbridge.client.create_mcp_http_client", return_value=http_client
        ),
        patch("bcgpt.mcpbridge.client.ClientSession", return_value=session),
    )


def test_list_tools_and_call():
    tool = MagicMock()
    tool.name = "now"
    page = MagicMock(tools=[tool], nextCursor=None)
    caps = MagicMock(tools=True)
    session = AsyncMock()
    session.__aenter__ = AsyncMock()
    session.__aexit__ = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(return_value=page)
    session.call_tool = AsyncMock(
        return_value=MagicMock(
            content=[MagicMock(type="text", text="2026")], isError=False
        )
    )
    session.get_server_capabilities = MagicMock(return_value=caps)
    p1, p2, p3 = _patched_transport(session)
    with p1, p2, p3:
        c = McpClient(CFG)
        _run(c.connect())
        tools = _run(c.list_tools())
        assert tools[0].name == "now"
        out = _run(c.call_tool("now", {}))
        assert "2026" in out
        _run(c.close())


def test_connect_rejects_server_without_tools():
    caps = MagicMock(tools=None)
    session = AsyncMock()
    session.__aenter__ = AsyncMock()
    session.__aexit__ = AsyncMock()
    session.initialize = AsyncMock()
    session.get_server_capabilities = MagicMock(return_value=caps)
    p1, p2, p3 = _patched_transport(session)
    with p1, p2, p3:
        c = McpClient(CFG)
        try:
            _run(c.connect())
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert "no tools" in str(e)


def test_source_passes_no_sampling_args():
    """Security gate: ClientSession must never be built with sampling kwargs. The check
    looks for an actual keyword-argument assignment (``=``), not a bare mention in the
    docstring."""
    from bcgpt.mcpbridge import client as cli

    src = inspect.getsource(cli)
    assert "sampling_callback=" not in src, "must not pass sampling_callback="
    assert "sampling_capabilities=" not in src, "must not pass sampling_capabilities="
