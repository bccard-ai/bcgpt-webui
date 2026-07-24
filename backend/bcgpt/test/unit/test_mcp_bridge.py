"""Test the MCP tools_dict registration shape (no network — descriptor unit)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.mcpbridge.registry import make_mcp_tool_descriptor


def test_mcp_descriptor_registers_under_namespaced_key():
    tool = SimpleNamespace(name="now", description="d", inputSchema={"type": "object"})
    desc = make_mcp_tool_descriptor({"id": "s1", "url": "u", "token": ""}, tool)
    tools_dict: dict = {}
    tools_dict.setdefault(desc["spec"]["name"], desc)
    assert "mcp__s1__now" in tools_dict
    assert tools_dict["mcp__s1__now"]["toolkit_id"] == "__mcp__:s1"
    # Server-side execution: no browser-roundtrip 'direct' key.
    assert "direct" not in tools_dict["mcp__s1__now"]


def test_namespaced_keys_avoid_collision():
    """Two servers exposing a tool of the same name must not collide."""
    tool = SimpleNamespace(name="now", description="d", inputSchema={"type": "object"})
    d1 = make_mcp_tool_descriptor({"id": "s1", "url": "u", "token": ""}, tool)
    d2 = make_mcp_tool_descriptor({"id": "s2", "url": "u", "token": ""}, tool)
    tools_dict: dict = {}
    tools_dict.setdefault(d1["spec"]["name"], d1)
    tools_dict.setdefault(d2["spec"]["name"], d2)
    assert len(tools_dict) == 2
