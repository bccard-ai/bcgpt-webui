"""Tests for the built-in MCP tool functions (call directly; no server)."""

from __future__ import annotations

from unittest.mock import patch

from bcgpt.mcpbridge.builtins import fetch as fetch_mod
from bcgpt.mcpbridge.builtins import time as time_mod
from bcgpt.mcpbridge.builtins.fetch import fetch
from bcgpt.mcpbridge.builtins.time import now


def test_time_now_returns_iso_string():
    out = now(tz_offset_minutes=540)
    assert isinstance(out, str) and "T" in out  # ISO-8601-ish


def test_time_server_constructs():
    srv = time_mod.create_server()
    assert srv.name == "time"


def test_fetch_rejects_disallowed_host():
    # Empty allow-list => deny.
    with patch.object(fetch_mod, "_effective_allowed_hosts", return_value=[]):
        out = fetch("https://evil.example.com/x")
    assert "denied" in out.lower() or "not in" in out.lower()


def test_fetch_allows_and_calls(monkeypatch):
    fake = type("R", (), {"text": "hello", "status_code": 200})()
    with (
        patch.object(
            fetch_mod, "_effective_allowed_hosts", return_value=["example.com"]
        ),
        patch.object(fetch_mod.httpx, "get", return_value=fake),
    ):
        out = fetch("https://example.com/x")
    assert out == "hello"


def test_fetch_server_constructs():
    srv = fetch_mod.create_server()
    assert srv.name == "fetch"
