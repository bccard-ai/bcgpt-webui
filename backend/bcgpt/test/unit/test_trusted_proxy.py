"""Trusted-header sign-in must only honour headers from allowlisted proxies.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_trusted_proxy.py -q
"""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.routers import auths


def _request(host):
    return SimpleNamespace(client=SimpleNamespace(host=host) if host else None)


def test_no_allowlist_trusts_nobody(monkeypatch):
    monkeypatch.setattr(auths, "BCGPT_AUTH_TRUSTED_PROXY_IPS", [])
    assert auths._is_trusted_proxy(_request("10.0.0.5")) is False
    assert auths._is_trusted_proxy(_request("127.0.0.1")) is False


def test_allowlisted_ip_and_cidr(monkeypatch):
    monkeypatch.setattr(
        auths, "BCGPT_AUTH_TRUSTED_PROXY_IPS", ["10.0.0.5", "172.18.0.0/16"]
    )
    assert auths._is_trusted_proxy(_request("10.0.0.5")) is True
    assert auths._is_trusted_proxy(_request("172.18.3.4")) is True
    assert auths._is_trusted_proxy(_request("10.0.0.6")) is False
    assert auths._is_trusted_proxy(_request(None)) is False
