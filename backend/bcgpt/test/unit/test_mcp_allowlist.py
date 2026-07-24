"""Tests for the MCP outbound allow-host."""

from __future__ import annotations

from bcgpt.mcpbridge.allowlist import is_host_allowed


def test_empty_allowlist_denies():
    assert is_host_allowed("https://example.com/mcp", []) is False


def test_non_http_denied():
    assert is_host_allowed("ftp://example.com/x", ["example.com"]) is False


def test_exact_and_suffix_match():
    assert is_host_allowed("https://example.com/mcp", ["example.com"]) is True
    assert is_host_allowed("https://mcp.example.com/mcp", ["example.com"]) is True


def test_suffix_does_not_span_subdomain_boundary():
    # example.com must NOT match example.com.evil.com
    assert is_host_allowed("https://example.com.evil.com/mcp", ["example.com"]) is False


def test_loopback_builtin_allowed():
    assert (
        is_host_allowed("http://127.0.0.1:8080/mcp/builtin/time/", ["127.0.0.1"])
        is True
    )
    assert is_host_allowed("http://localhost:8080/mcp", ["localhost"]) is True


def test_disallowed_host_denied():
    assert is_host_allowed("https://evil.com/mcp", ["example.com"]) is False
