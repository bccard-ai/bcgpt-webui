"""Built-in MCP server: ``fetch`` (allow-host-gated HTTP fetch)."""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from bcgpt.mcpbridge.allowlist import is_host_allowed

BUILTIN_NAME = "fetch"

_MAX_CHARS = 8192


def _effective_allowed_hosts() -> list[str]:
    """Read the admin allow-host defensively (the config constant may not exist on
    fresh installs before Task 7's config block runs). Monkeypatchable in tests."""
    try:
        from bcgpt import config as cfg

        hosts = getattr(getattr(cfg, "MCP_ALLOWED_HOSTS", None), "value", None)
        return list(hosts or [])
    except Exception:
        return []


def fetch(url: str) -> str:
    """Fetch a URL's text, subject to the admin MCP_ALLOWED_HOSTS allow-list."""
    if not is_host_allowed(url, _effective_allowed_hosts()):
        return "[fetch denied: host not in MCP_ALLOWED_HOSTS]"
    try:
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
        return resp.text[:_MAX_CHARS]
    except Exception as e:  # noqa: BLE001
        return f"[fetch error: {e}]"


def create_server() -> FastMCP:
    mcp = FastMCP(
        name=BUILTIN_NAME,
        streamable_http_path="/",
        stateless_http=True,
        json_response=True,
    )
    mcp.tool()(fetch)
    return mcp
