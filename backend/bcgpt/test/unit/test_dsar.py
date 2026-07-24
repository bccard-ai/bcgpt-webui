"""Security regression tests for the DSAR (data-subject-access-request) router.

The DSAR surface (open-moai compliance module) handles data-export / erasure
requests, so cross-user access is a PII-exfiltration risk. These tests lock the
IDOR protection on ``GET /{request_id}`` verified during the 2026-06-22 review:

  * A non-admin user may read only their OWN request; cross-user -> 403.
  * An admin may read any request.
  * ``COMPLIANCE_ENABLED`` off -> 403 (gate).
  * Unknown request id -> 404.

The router's model lookup is monkeypatched so no DB is required.

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_dsar.py -q
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bcgpt.compliance.models.dsar import AIDSARRequestModel, AIDSARRequests
from bcgpt.compliance.routers import dsar as dsar_router


def _fake_request(*, enabled: bool = True):
    config = SimpleNamespace(COMPLIANCE_ENABLED=enabled)
    return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(config=config)))


def _fake_user(*, id: str, role: str = "user"):
    return SimpleNamespace(id=id, role=role)


def _fake_dsar_model(*, user_id: str):
    return AIDSARRequestModel(
        id="req-1",
        request_type="export",
        user_id=user_id,
        status="pending",
        requested_at=0,
        created_at=0,
    )


def _call(request_id, request, user):
    """Invoke the async router fn synchronously (its body has no awaits)."""
    return asyncio.run(dsar_router.get_dsar_request(request_id, request, user))


# ---------------------------------------------------------------------------
# IDOR: cross-user access control on GET /{request_id}
# ---------------------------------------------------------------------------


def test_owner_can_read_own_request(monkeypatch):
    monkeypatch.setattr(
        AIDSARRequests, "get_by_id", lambda id_: _fake_dsar_model(user_id="owner-1")
    )
    result = _call("req-1", _fake_request(), _fake_user(id="owner-1"))
    assert result["user_id"] == "owner-1"


def test_non_owner_non_admin_gets_403(monkeypatch):
    monkeypatch.setattr(
        AIDSARRequests, "get_by_id", lambda id_: _fake_dsar_model(user_id="owner-1")
    )
    with pytest.raises(HTTPException) as exc:
        _call("req-1", _fake_request(), _fake_user(id="attacker"))
    assert exc.value.status_code == 403


def test_admin_can_read_any_request(monkeypatch):
    monkeypatch.setattr(
        AIDSARRequests, "get_by_id", lambda id_: _fake_dsar_model(user_id="owner-1")
    )
    result = _call("req-1", _fake_request(), _fake_user(id="admin-1", role="admin"))
    assert result["user_id"] == "owner-1"


def test_compliance_disabled_returns_403(monkeypatch):
    monkeypatch.setattr(
        AIDSARRequests, "get_by_id", lambda id_: _fake_dsar_model(user_id="owner-1")
    )
    with pytest.raises(HTTPException) as exc:
        _call("req-1", _fake_request(enabled=False), _fake_user(id="owner-1"))
    assert exc.value.status_code == 403


def test_missing_request_returns_404(monkeypatch):
    monkeypatch.setattr(AIDSARRequests, "get_by_id", lambda id_: None)
    with pytest.raises(HTTPException) as exc:
        _call("nope", _fake_request(), _fake_user(id="owner-1"))
    assert exc.value.status_code == 404
