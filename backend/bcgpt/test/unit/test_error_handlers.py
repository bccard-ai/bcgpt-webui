"""Tests for structured exception handlers registered on the FastAPI app.

Verifies the Phase 0 fix from Round 13 of the ULW loop: the handlers in
utils/error_handlers.py were defined but never registered (dead code).
These tests prove they are now active and emit request_id in responses.

ADR: docs/ERROR_HANDLING_RESILIENCE_GOVERNANCE_PLAN_2026-06-23.md §3.3
"""

import uuid

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from bcgpt.utils.error_handlers import (
    generic_exception_handler,
    http_exception_handler,
    validation_exception_handler,
)


def _validate_request_id(value) -> None:
    """A request_id must be a valid UUID4 string."""
    parsed = uuid.UUID(str(value))
    assert parsed.version == 4


def test_handler_functions_exist():
    assert callable(generic_exception_handler)
    assert callable(validation_exception_handler)
    assert callable(http_exception_handler)


def test_app_has_exception_handlers_registered():
    """The production app must register all three handlers."""
    from bcgpt.main import app

    # FastAPI stores exception handlers in app.exception_handlers dict
    # keyed by exception class.  StarletteHTTPException covers HTTPException.
    handlers = app.exception_handlers
    assert Exception in handlers
    assert RequestValidationError in handlers
    assert StarletteHTTPException in handlers


def test_unhandled_exception_returns_500_with_request_id():
    app = FastAPI()

    @app.get("/_test/boom")
    async def _boom():
        raise RuntimeError("synthetic crash")

    app.add_exception_handler(Exception, generic_exception_handler)

    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/_test/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert "request_id" in body
    _validate_request_id(body["request_id"])


def test_http_exception_returns_status_with_request_id():
    app = FastAPI()

    @app.get("/_test/forbidden")
    async def _forbidden():
        raise HTTPException(status_code=403, detail="not allowed")

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    client = TestClient(app)
    resp = client.get("/_test/forbidden")
    assert resp.status_code == 403
    body = resp.json()
    assert body["detail"] == "not allowed"
    assert "request_id" in body
    _validate_request_id(body["request_id"])


def test_http_exception_preserves_custom_status_codes():
    """Handler must echo whatever status_code the route raised."""
    app = FastAPI()

    @app.get("/_test/conflict")
    async def _conflict():
        raise HTTPException(status_code=409, detail="conflict data")

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    client = TestClient(app)
    resp = client.get("/_test/conflict")
    assert resp.status_code == 409
    body = resp.json()
    assert body["detail"] == "conflict data"
    assert "request_id" in body


def test_request_ids_are_unique():
    """Each request must get a distinct request_id."""
    app = FastAPI()

    @app.get("/_test/err")
    async def _err():
        raise HTTPException(status_code=400, detail="bad")

    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    client = TestClient(app)
    ids = set()
    for _ in range(5):
        resp = client.get("/_test/err")
        ids.add(resp.json()["request_id"])
    assert len(ids) == 5
