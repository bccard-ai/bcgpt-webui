"""Streamable-HTTP MCP client wrapper.

Security: sampling stays at the SDK default-refuse — we deliberately do NOT pass
``sampling_callback`` or ``sampling_capabilities`` to ``ClientSession``. A
spec-compliant server therefore cannot ask the BCGPT host to spend LLM tokens.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared._httpx_utils import create_mcp_http_client

from bcgpt.mcpbridge.serialize import stringify_call_result

DEFAULT_TIMEOUT = 30.0


class McpClient:
    """Short-lived Streamable-HTTP MCP client (connect → list/call → close)."""

    def __init__(self, server_cfg: dict):
        self.cfg = server_cfg
        self._session: ClientSession | None = None
        self._http_client = None
        self._tr = None

    async def connect(self) -> None:
        headers = {"Accept": "application/json, text/event-stream"}
        token = self.cfg.get("token")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        http_client = create_mcp_http_client(
            headers=headers, timeout=httpx.Timeout(30.0, read=300.0)
        )
        self._http_client = http_client
        await self._http_client.__aenter__()
        self._tr = streamable_http_client(
            self.cfg["url"], http_client=http_client, terminate_on_close=True
        )
        read_stream, write_stream, _get_id = await self._tr.__aenter__()
        # SECURITY GATE: no sampling_callback / no sampling_capabilities passed.
        self._session = ClientSession(read_stream, write_stream)
        await self._session.__aenter__()
        await self._session.initialize()
        caps = self._session.get_server_capabilities()
        if not (caps and getattr(caps, "tools", None)):
            raise RuntimeError("MCP server advertises no tools capability")

    async def list_tools(self) -> list[Any]:
        assert self._session is not None
        tools: list[Any] = []
        cursor = None
        while True:
            page = await self._session.list_tools(cursor=cursor)
            tools.extend(page.tools)
            cursor = getattr(page, "nextCursor", None)
            if not cursor:
                break
        return tools

    async def call_tool(
        self, name: str, arguments: dict | None, *, timeout: float = DEFAULT_TIMEOUT
    ) -> str:
        assert self._session is not None
        result = await asyncio.wait_for(
            self._session.call_tool(name, arguments or {}), timeout=timeout
        )
        return stringify_call_result(result)

    async def close(self) -> None:
        for cm in (self._session, self._tr, self._http_client):
            if cm is None:
                continue
            try:
                await cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._session = None
        self._tr = None
        self._http_client = None

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc):
        await self.close()
