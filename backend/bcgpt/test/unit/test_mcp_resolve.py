"""Tests for resolve_effective_mcp_servers (admin catalog ∪ user-registered, allow-host gated)."""

from __future__ import annotations

import pytest

from bcgpt.utils.extensions import resolve_effective_mcp_servers


class _U:
    def __init__(self, uid="u1", settings=None):
        self.id = uid
        self.role = "user"
        self.settings = settings or {}


@pytest.fixture(autouse=True)
def _mcp_cfg(monkeypatch):
    # The PersistentConfig objects use a custom __getattribute__; patch .value via
    # object.__setattr__ to bypass it.
    import bcgpt.config as cfg

    object.__setattr__(cfg.ENABLE_MCP_SERVERS, "value", True)
    object.__setattr__(
        cfg.MCP_SERVERS,
        "value",
        [
            {
                "id": "a",
                "url": "https://mcp.a.com/mcp",
                "enabled": True,
                "allow_user_override": True,
            }
        ],
    )
    object.__setattr__(cfg.MCP_ALLOWED_HOSTS, "value", ["mcp.a.com"])
    yield
    object.__setattr__(cfg.ENABLE_MCP_SERVERS, "value", False)
    object.__setattr__(cfg.MCP_SERVERS, "value", [])
    object.__setattr__(cfg.MCP_ALLOWED_HOSTS, "value", [])


def test_admin_catalog_visible_when_enabled():
    rows = resolve_effective_mcp_servers(_U())
    assert [s["id"] for s in rows] == ["a"]


def test_disabled_when_flag_off(monkeypatch):
    import bcgpt.config as cfg

    object.__setattr__(cfg.ENABLE_MCP_SERVERS, "value", False)
    assert resolve_effective_mcp_servers(_U()) == []


def test_user_added_server_within_allowlist():
    rows = resolve_effective_mcp_servers(
        _U(
            "u1",
            {
                "ui": {
                    "mcpServers": [
                        {
                            "id": "uX",
                            "url": "https://mcp.a.com/mcp",
                            "token": "k",
                            "enabled": True,
                        }
                    ]
                }
            },
        )
    )
    assert "uX" in [s["id"] for s in rows]


def test_user_server_outside_allowlist_denied():
    rows = resolve_effective_mcp_servers(
        _U(
            "u1",
            {
                "ui": {
                    "mcpServers": [
                        {"id": "bad", "url": "https://evil.com/mcp", "enabled": True}
                    ]
                }
            },
        )
    )
    assert "bad" not in [s["id"] for s in rows]


def test_server_ids_restricts():
    rows = resolve_effective_mcp_servers(_U(), server_ids=["a"])
    assert [s["id"] for s in rows] == ["a"]
    rows2 = resolve_effective_mcp_servers(_U(), server_ids=["nonexistent"])
    assert rows2 == []
