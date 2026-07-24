"""MCP operations router: effective server list, tool discovery, CRUD, test.

``McpClient`` is imported lazily so the router (and therefore the whole backend)
loads even if the optional ``mcp`` SDK is not installed. Endpoints that need the
SDK return HTTP 503 when it is unavailable; catalog CRUD still works without it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt import config as cfg
from bcgpt.mcpbridge.allowlist import is_host_allowed
from bcgpt.utils.auth import get_admin_user, get_verified_user
from bcgpt.utils.extensions import resolve_effective_mcp_servers

router = APIRouter()


def _get_mcp_client():
    """Lazily import McpClient. Raises HTTPException(503) if the mcp SDK is missing."""
    try:
        from bcgpt.mcpbridge.client import McpClient

        return McpClient
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail="MCP SDK is not installed (`pip install mcp`); server-side tool "
            "discovery/calls are unavailable.",
        ) from e


@router.get("/servers")
async def list_servers(request: Request, user=Depends(get_verified_user)):
    return {"servers": resolve_effective_mcp_servers(user)}


@router.get("/servers/{server_id}/tools")
async def list_server_tools(
    server_id: str, request: Request, user=Depends(get_verified_user)
):
    servers = resolve_effective_mcp_servers(user)
    match = next((s for s in servers if s["id"] == server_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    McpClient = _get_mcp_client()
    try:
        client = McpClient(match)
        await client.connect()
        tools = await client.list_tools()
        await client.close()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"MCP discovery failed: {e}")
    return {
        "tools": [
            {
                "name": t.name,
                "description": getattr(t, "description", ""),
                "inputSchema": getattr(t, "inputSchema", {}),
            }
            for t in tools
        ]
    }


@router.post("/servers/{server_id}/test")
async def test_server(server_id: str, request: Request, user=Depends(get_admin_user)):
    servers = resolve_effective_mcp_servers(user)
    match = next((s for s in servers if s["id"] == server_id), None)
    if match is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    McpClient = _get_mcp_client()
    try:
        client = McpClient(match)
        await client.connect()
        await client.list_tools()
        await client.close()
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    return {"ok": True}


class ServerForm(BaseModel):
    id: str
    name: str
    url: str
    token: str | None = None
    enabled: bool = True
    allow_user_override: bool = True


@router.post("/servers")
async def create_server_endpoint(
    form: ServerForm, request: Request, user=Depends(get_admin_user)
):
    allowed = list(getattr(cfg.MCP_ALLOWED_HOSTS, "value", []) or [])
    if not is_host_allowed(form.url, allowed):
        raise HTTPException(status_code=400, detail="URL host not in MCP_ALLOWED_HOSTS")
    servers = list(getattr(cfg.MCP_SERVERS, "value", []) or [])
    if any(s.get("id") == form.id for s in servers):
        raise HTTPException(status_code=409, detail="MCP server id already exists")
    servers.append(form.model_dump())
    cfg.MCP_SERVERS = servers
    return {"servers": servers}


@router.delete("/servers/{server_id}")
async def delete_server_endpoint(
    server_id: str, request: Request, user=Depends(get_admin_user)
):
    servers = [
        s
        for s in (list(getattr(cfg.MCP_SERVERS, "value", []) or []))
        if s.get("id") != server_id
    ]
    cfg.MCP_SERVERS = servers
    return {"servers": servers}
