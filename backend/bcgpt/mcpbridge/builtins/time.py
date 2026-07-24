"""Built-in MCP server: ``time`` (current time, tz-offset aware)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP

BUILTIN_NAME = "time"


def now(tz_offset_minutes: int = 0) -> str:
    """Return the current time offset by ``tz_offset_minutes`` (ISO-8601)."""
    tz = timezone(timedelta(minutes=int(tz_offset_minutes)))
    return datetime.now(tz).isoformat()


def create_server() -> FastMCP:
    mcp = FastMCP(
        name=BUILTIN_NAME,
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
    )
    mcp.tool()(now)
    return mcp
