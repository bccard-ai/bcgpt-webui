"""Security regression tests for the SCIM 2.0 provisioning router.

The SCIM surface (open-moai adoption 3.4) auto-provisions user accounts from
an identity provider, so it is a sensitive auth boundary. These tests lock the
properties verified during the 2026-06-22 review:

  * SCIM endpoints are unreachable when ``SCIM_ENABLED`` is off (404).
  * Requests with no / wrong / empty bearer token are rejected (401), and a
    missing configured token fails closed (401, never open).
  * The bearer-prefix match is case-insensitive.
  * Payload parsing normalizes email and never reads a ``role`` from the IdP
    payload (role is server-controlled -> no privilege escalation via SCIM).

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_scim.py -q
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bcgpt.routers.scim import (
    _iso,
    _require_scim,
    _scim_extract_user,
    _user_to_scim,
)


def _fake_request(*, enabled: bool = False, token: str = "", authorization: str = ""):
    config = SimpleNamespace(SCIM_ENABLED=enabled, SCIM_TOKEN=token)
    headers = {"authorization": authorization} if authorization else {}
    return SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(config=config)),
        headers=headers,
    )


# ---------------------------------------------------------------------------
# _require_scim — the security gate
# ---------------------------------------------------------------------------


def test_scim_disabled_returns_404():
    with pytest.raises(HTTPException) as exc:
        _require_scim(_fake_request(enabled=False))
    assert exc.value.status_code == 404


def test_scim_no_token_configured_returns_401():
    # SCIM enabled but no token set -> fail-closed (never open).
    with pytest.raises(HTTPException) as exc:
        _require_scim(_fake_request(enabled=True, token=""))
    assert exc.value.status_code == 401


def test_scim_missing_authorization_header_returns_401():
    with pytest.raises(HTTPException) as exc:
        _require_scim(_fake_request(enabled=True, token="s3cr3t"))
    assert exc.value.status_code == 401


def test_scim_wrong_token_returns_401():
    with pytest.raises(HTTPException) as exc:
        _require_scim(
            _fake_request(enabled=True, token="s3cr3t", authorization="Bearer wrong")
        )
    assert exc.value.status_code == 401


def test_scim_correct_token_passes():
    # No exception raised on a valid token.
    _require_scim(
        _fake_request(enabled=True, token="s3cr3t", authorization="Bearer s3cr3t")
    )


def test_scim_token_prefix_case_insensitive():
    _require_scim(
        _fake_request(enabled=True, token="s3cr3t", authorization="bearer s3cr3t")
    )


def test_scim_empty_bearer_token_returns_401():
    with pytest.raises(HTTPException) as exc:
        _require_scim(
            _fake_request(enabled=True, token="s3cr3t", authorization="Bearer ")
        )
    assert exc.value.status_code == 401


# ---------------------------------------------------------------------------
# _scim_extract_user — payload parsing + normalization
# ---------------------------------------------------------------------------


def test_extract_user_basic_normalizes_email():
    email, name, active = _scim_extract_user(
        {"userName": "Alice@Example.com", "displayName": "Alice", "active": False}
    )
    assert email == "alice@example.com"  # lowercased
    assert name == "Alice"
    assert active is False


def test_extract_user_active_defaults_true():
    _, _, active = _scim_extract_user({"userName": "bob@example.com"})
    assert active is True


def test_extract_user_email_from_emails_array():
    email, _, _ = _scim_extract_user(
        {"emails": [{"value": "carol@example.com", "primary": True}]}
    )
    assert email == "carol@example.com"


def test_extract_user_prefers_primary_email():
    email, _, _ = _scim_extract_user(
        {
            "emails": [
                {"value": "secondary@example.com"},
                {"value": "primary@example.com", "primary": True},
            ]
        }
    )
    assert email == "primary@example.com"


def test_extract_user_name_fallback_chain():
    # displayName wins.
    _, name, _ = _scim_extract_user(
        {"userName": "x@y.com", "displayName": "Display", "name": {"formatted": "Fmt"}}
    )
    assert name == "Display"
    # name.formatted next.
    _, name, _ = _scim_extract_user(
        {"userName": "x@y.com", "name": {"formatted": "Fmt", "givenName": "G"}}
    )
    assert name == "Fmt"
    # given + family next.
    _, name, _ = _scim_extract_user(
        {"userName": "x@y.com", "name": {"givenName": "Given", "familyName": "Family"}}
    )
    assert name == "Given Family"
    # email last.
    email, name, _ = _scim_extract_user({"userName": "solo@example.com"})
    assert name == "solo@example.com"


def test_extract_user_ignores_role_in_payload():
    """Security: a SCIM payload cannot inject a role. ``_scim_extract_user``
    returns only (email, name, active); the router assigns role server-side
    ("user"/"pending"), so an IdP-supplied ``role`` key is silently ignored."""
    result = _scim_extract_user(
        {"userName": "pwn@example.com", "role": "admin", "active": True}
    )
    assert len(result) == 3  # (email, name, active) — no role channel
    assert result[2] is True  # active comes from the `active` key, not role


def test_extract_user_empty_payload():
    email, name, _ = _scim_extract_user({})
    assert email == ""
    assert name == ""


# ---------------------------------------------------------------------------
# _user_to_scim — resource mapping (active == role != "pending")
# ---------------------------------------------------------------------------


def _fake_user(role: str):
    return SimpleNamespace(
        id="u1",
        email="u1@example.com",
        name="U1",
        role=role,
        created_at=0,
        updated_at=0,
    )


def test_user_to_scim_active_user_is_active():
    assert _user_to_scim(_fake_user("user"))["active"] is True


def test_user_to_scim_pending_is_inactive():
    assert _user_to_scim(_fake_user("pending"))["active"] is False


def test_user_to_scim_shape():
    out = _user_to_scim(_fake_user("user"))
    assert out["userName"] == "u1@example.com"
    assert out["emails"] == [{"value": "u1@example.com", "primary": True}]
    assert out["id"] == "u1"


# ---------------------------------------------------------------------------
# _iso — timestamp formatting
# ---------------------------------------------------------------------------


def test_iso_epoch_zero():
    assert _iso(0) == "1970-01-01T00:00:00Z"


def test_iso_none():
    assert _iso(None) == "1970-01-01T00:00:00Z"


def test_iso_invalid_falls_back():
    assert _iso("not-a-number") == "1970-01-01T00:00:00Z"
