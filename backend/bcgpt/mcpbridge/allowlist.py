"""Outbound allow-host for MCP server URLs (default-deny)."""

from __future__ import annotations

import ipaddress
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


def is_user_host_allowed(url: str, allowed_hosts: list[str]) -> bool:
    """Like :func:`is_host_allowed`, for URLs registered by a (non-admin) user.

    The loopback rule exists so admins can register built-in local servers; a
    user-supplied URL must never reach loopback, link-local or private IP
    literals even when the allowlist contains them.
    """
    if not is_host_allowed(url, allowed_hosts):
        return False
    host = (urlparse(url).hostname or "").lower()
    if host == "localhost" or host.endswith(".localhost"):
        return False
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_private
        or ip.is_unspecified
        or ip.is_reserved
        or ip.is_multicast
    )
