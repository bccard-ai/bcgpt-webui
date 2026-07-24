"""Regression tests for chats router HTTP status codes.

Bug reproduced here: after login, clicking the chat list issued a request to
a ``/chats/{id}``-shaped path whose id did not resolve to a chat (e.g. the
legacy ``GET /chats/tags`` call, where "tags" is captured by the catch-all
``GET /{id}`` route). The handler raised **HTTP 401**, which the frontend's
global ``installUnauthorizedInterceptor`` treats as an authentication failure
and force-logs-out the user ("로그인이 풀려버린다").

HTTP 401 must be reserved for *authentication* failures (missing/invalid/
expired token), which are produced by the ``get_verified_user`` dependency.
Resource-not-found is 404; ownership/permission denial is 403. None of these
should be 401, otherwise the interceptor nukes a valid session.
"""

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bcgpt.routers import chats as chats_router
from bcgpt.utils import get_verified_user


def _client(monkeypatch, *, chat=None, user=None):
    app = FastAPI()
    app.include_router(chats_router.router, prefix="/api/v1/chats")

    fake_user = user or SimpleNamespace(id="u1", role="user")

    async def _fake_user():
        return fake_user

    app.dependency_overrides[get_verified_user] = _fake_user

    monkeypatch.setattr(
        chats_router,
        "Chats",
        SimpleNamespace(
            get_chat_by_id_and_user_id=lambda cid, uid: chat,
            get_chat_by_id=lambda cid: chat,
        ),
    )
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.parametrize(
    "path",
    ["/api/v1/chats/tags", "/api/v1/chats/does-not-exist-12345"],
)
def test_get_unknown_chat_id_is_404_never_401(monkeypatch, path):
    """A GET that does not resolve to a chat must be 404, never 401.

    A 401 here trips the frontend interceptor and logs the user out, which is
    the bug under test.
    """
    client = _client(monkeypatch, chat=None)
    resp = client.get(path)
    assert (
        resp.status_code != 401
    ), "resource-not-found returned 401, which force-logs-out the user"
    assert resp.status_code == 404
