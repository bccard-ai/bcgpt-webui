"""Security tests for the RAG web-fetch SSRF defenses (``retrieval/web/utils.py``).

The cloud-metadata / internal-network SSRF surface (OWASP-style): an authenticated
user asks the server to fetch a URL, which must never resolve to a private/loopback/
link-local address. These tests lock the IP-blocklist (``_is_blocked_ip``) and the
``validate_url`` scheme/format gate so a future change cannot silently re-open the
hole. (DNS-rebinding / TOCTOU -- resolving a safe IP then connecting to a different
one -- remains a noted limitation that needs connection-time IP pinning and is out
of scope here.)

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
