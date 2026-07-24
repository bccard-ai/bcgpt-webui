"""Tests for the MCP descriptor factory."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.mcpbridge.registry import make_mcp_tool_descriptor, namespace_tool_name


def test_namespacing():
    assert namespace_tool_name("s1", "now") == "mcp__s1__now"
    assert (
        namespace_tool_name("server.with/symbols", "t") == "mcp__server_with_symbols__t"
    )


def test_descriptor_shape_no_direct():
    tool = SimpleNamespace(name="now", description="d", inputSchema={"type": "object"})
    desc = make_mcp_tool_descriptor({"id": "s1", "url": "u", "token": ""}, tool)
    assert desc["spec"]["name"] == "mcp__s1__now"
    assert desc["spec"]["description"] == "d"
    assert desc["spec"]["parameters"] == {"type": "object"}
    assert callable(desc["callable"])
    assert desc["toolkit_id"] == "__mcp__:s1"
    # Server-side execution: must NOT carry the browser-roundtrip 'direct' key.
    assert "direct" not in desc


def test_descriptor_falls_back_when_schema_missing():
    tool = SimpleNamespace(name="t", description=None, inputSchema=None)
    desc = make_mcp_tool_descriptor({"id": "s1", "url": "u", "token": ""}, tool)
    assert desc["spec"]["parameters"] == {"type": "object", "properties": {}}
    assert "MCP tool t" in desc["spec"]["description"]
