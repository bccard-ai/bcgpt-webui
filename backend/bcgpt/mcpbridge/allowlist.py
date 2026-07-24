"""Outbound allow-host for MCP server URLs (default-deny)."""

from __future__ import annotations

from urllib.parse import urlparse


def is_host_allowed(url: str, allowed_hosts: list[str]) -> bool:
    """True iff ``url`` is http(s) and its host matches an allow-host rule.

    Rules are host suffixes (``example.com`` matches ``mcp.example.com`` but not
    ``example.com.evil.com``). ``127.0.0.1`` / ``localhost`` are matched literally
    so loopback built-in servers can be registered. Empty allowlist => deny all.
    """
    if not isinstance(url, str) or not allowed_hosts:
        return False
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    for rule in allowed_hosts:
        r = str(rule).lower().lstrip(".")
        if not r:
            continue
        if host == r or host.endswith("." + r):
            return True
        if r in ("127.0.0.1", "localhost") and host in ("127.0.0.1", "localhost"):
            return True
    return False
