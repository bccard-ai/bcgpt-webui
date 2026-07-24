"""Regression tests for safe session revocation across browser tabs."""

from types import SimpleNamespace

from starlette.requests import Request

from bcgpt.routers import auths as auths_router


def _request_with_token(token: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/auths/signout",
            "headers": [(b"cookie", f"token={token}".encode())],
        }
    )


def test_signout_does_not_revoke_a_newer_session_from_a_stale_token(monkeypatch):
    # Kept as a list so the assertion verifies that the revocation method was
    # never reached, rather than merely checking monkeypatch's return value.
    calls: list[str] = []
    monkeypatch.setattr(
        auths_router, "decode_token", lambda _token: {"id": "u1", "tv": 3}
    )
    monkeypatch.setattr(
        auths_router.Auths,
        "get_auth_by_user_id",
        lambda _user_id: SimpleNamespace(token_version=4),
    )
    monkeypatch.setattr(
        auths_router.Auths,
        "increment_token_version",
        lambda user_id: calls.append(user_id) or True,
    )

    auths_router._invalidate_session_token(_request_with_token("stale-token"))

    assert calls == []


def test_signout_revokes_the_current_session_token(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(
        auths_router, "decode_token", lambda _token: {"id": "u1", "tv": 4}
    )
    monkeypatch.setattr(
        auths_router.Auths,
        "get_auth_by_user_id",
        lambda _user_id: SimpleNamespace(token_version=4),
    )
    monkeypatch.setattr(
        auths_router.Auths,
        "increment_token_version",
        lambda user_id: calls.append(user_id) or True,
    )

    auths_router._invalidate_session_token(_request_with_token("current-token"))

    assert calls == ["u1"]
