"""The global security-header middleware must not clobber per-route headers.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_security_headers.py -q
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.testclient import TestClient

from bcgpt.utils.security_headers import SecurityHeadersMiddleware

_SANDBOX_CSP = "default-src 'none'; sandbox"


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/preview")
    def preview():
        return HTMLResponse(
            "<p>x</p>", headers={"Content-Security-Policy": _SANDBOX_CSP}
        )

    @app.get("/plain")
    def plain():
        return PlainTextResponse("ok")

    return TestClient(app)


def test_route_csp_is_preserved():
    resp = _client().get("/preview")
    assert resp.headers["content-security-policy"] == _SANDBOX_CSP
    assert resp.headers["x-content-type-options"] == "nosniff"


def test_defaults_applied_when_route_sets_nothing():
    resp = _client().get("/plain")
    assert "default-src 'self'" in resp.headers["content-security-policy"]
    assert resp.headers["x-frame-options"] == "SAMEORIGIN"
