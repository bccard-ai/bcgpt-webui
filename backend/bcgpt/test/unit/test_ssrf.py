"""Security tests for the RAG web-fetch SSRF defenses (``retrieval/web/utils.py``).

The cloud-metadata / internal-network SSRF surface (OWASP-style): an authenticated
user asks the server to fetch a URL, which must never resolve to a private/loopback/
link-local address. These tests lock the IP-blocklist (``_is_blocked_ip``) and the
``validate_url`` scheme/format gate so a future change cannot silently re-open the
hole, plus the connection-time ``SSRFSafeResolver`` that closes the DNS-rebinding /
TOCTOU gap (a host that resolved to a safe IP during validation but to a blocked
one when the client connects).

Network-free: ``_is_blocked_ip`` is pure ``ipaddress``; the ``validate_url`` cases
exercise only the pre-DNS ValueError paths (bad scheme / malformed / no host), so no
real hostname resolution occurs.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_ssrf.py -q
"""

from __future__ import annotations

import pytest

from bcgpt.retrieval.web.utils import _is_blocked_ip, validate_url

# ---------------------------------------------------------------------------
# _is_blocked_ip -- the core SSRF IP blocklist (pure)
# ---------------------------------------------------------------------------


def test_loopback_blocked():
    assert _is_blocked_ip("127.0.0.1") is True
    assert _is_blocked_ip("::1") is True


def test_cloud_metadata_endpoint_blocked():
    # 169.254.169.254 (AWS/Azure/GCP IMDS) is link-local -> blocked.
    assert _is_blocked_ip("169.254.169.254") is True
    assert _is_blocked_ip("169.254.170.2") is True  # ECS task metadata


def test_link_local_ipv6_blocked():
    assert _is_blocked_ip("fe80::1") is True


def test_private_ipv4_blocked_by_default():
    for ip in ("10.0.0.1", "192.168.1.1", "172.16.0.1", "172.31.255.255"):
        assert _is_blocked_ip(ip) is True, ip


def test_private_ipv6_ula_blocked_by_default():
    # Unique-local (fc00::/7), incl. the EC2 IMDSv6 fd00:ec2::254.
    assert _is_blocked_ip("fc00::1") is True
    assert _is_blocked_ip("fd00:ec2::254") is True


def test_private_allowed_when_explicit_opt_in():
    # allow_private=True permits RFC-1918 / ULA (the local-web-fetch opt-in).
    assert _is_blocked_ip("10.0.0.1", allow_private=True) is False
    assert _is_blocked_ip("192.168.1.1", allow_private=True) is False
    assert _is_blocked_ip("fd00:ec2::254", allow_private=True) is False


def test_loopback_and_metadata_blocked_even_with_allow_private():
    # Even the local-fetch opt-in must never reach loopback / metadata.
    assert _is_blocked_ip("127.0.0.1", allow_private=True) is True
    assert _is_blocked_ip("169.254.169.254", allow_private=True) is True


def test_public_addresses_allowed():
    assert _is_blocked_ip("8.8.8.8") is False
    assert _is_blocked_ip("1.1.1.1") is False
    assert _is_blocked_ip("2606:4700:4700::1111") is False


def test_multicast_reserved_unspecified_blocked():
    assert _is_blocked_ip("224.0.0.1") is True  # multicast
    assert _is_blocked_ip("240.0.0.1") is True  # reserved
    assert _is_blocked_ip("0.0.0.0") is True  # unspecified


def test_invalid_ip_string_blocked():
    # A non-IP string is treated as blocked (fail-closed), not a crash.
    assert _is_blocked_ip("not-an-ip") is True
    assert _is_blocked_ip("") is True
    assert _is_blocked_ip("999.999.999.999") is True


# ---------------------------------------------------------------------------
# validate_url -- scheme/format gate (pre-DNS ValueError paths only)
# ---------------------------------------------------------------------------


def test_validate_url_rejects_non_http_scheme():
    with pytest.raises(ValueError):
        validate_url("ftp://example.com")
    with pytest.raises(ValueError):
        validate_url("file:///etc/passwd")


def test_validate_url_rejects_malformed():
    with pytest.raises(ValueError):
        validate_url("not a url at all")
    with pytest.raises(ValueError):
        validate_url("ht!tp://broken")


def test_validate_url_rejects_missing_host():
    with pytest.raises(ValueError):
        validate_url("http://")


def test_validate_url_unsupported_type_returns_false():
    # Non-str, non-sequence -> False (not a crash).
    assert validate_url(123) is False
    assert validate_url(None) is False


# ---------------------------------------------------------------------------
# SSRFSafeResolver -- connection-time filtering (DNS rebinding)
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

from bcgpt.retrieval.web import utils as web_utils  # noqa: E402


class _FakeInner:
    def __init__(self, ips):
        self._ips = ips

    async def resolve(self, host, port=0, family=0):
        return [{"hostname": host, "host": ip, "port": port} for ip in self._ips]

    async def close(self):
        pass


def _resolve(ips, host="rebind.example", **kw):
    resolver = web_utils.SSRFSafeResolver(allow_private=False, **kw)
    resolver._inner = _FakeInner(ips)
    return asyncio.run(resolver.resolve(host, 80))


def test_resolver_rejects_when_all_addresses_blocked():
    with pytest.raises(OSError):
        _resolve(["169.254.169.254"])


def test_resolver_drops_blocked_addresses():
    infos = _resolve(["10.0.0.7", "93.184.216.34"])
    assert [i["host"] for i in infos] == ["93.184.216.34"]


def test_resolver_exempts_proxy_host():
    infos = _resolve(
        ["10.0.0.7"], host="proxy.corp", exempt_hosts=frozenset({"proxy.corp"})
    )
    assert [i["host"] for i in infos] == ["10.0.0.7"]


def test_sync_scrape_uses_safe_fetch(monkeypatch):
    loader = web_utils.SafeWebBaseLoader(web_paths=["https://example.com/"])
    calls = []

    async def fake_fetch(url, *a, **k):
        calls.append(url)
        return "<html><title>t</title><body>hello</body></html>"

    monkeypatch.setattr(loader, "_fetch", fake_fetch)
    monkeypatch.setattr(
        loader.session, "get", lambda *a, **k: pytest.fail("requests path used")
    )
    soup = loader._scrape("https://example.com/")
    assert calls == ["https://example.com/"]
    assert "hello" in soup.get_text()
