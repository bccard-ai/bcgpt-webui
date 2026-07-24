"""Tests for the skills router (DB-backed CRUD + flags + import).

Mounts only the skills router on a mini FastAPI app and overrides the auth
deps. Uses the shared ``skills_db`` fixture so the router's SkillsTable calls
hit an isolated engine.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bcgpt.agent.routers import skills as skills_router
from bcgpt.models import Skills
from bcgpt.utils.auth import get_admin_user, get_verified_user


class _U:
    def __init__(self, role="admin"):
        self.id = "admin-1"
        self.role = role


@pytest.fixture()
def client(skills_db):
    """Mini app with auth deps overridden. ``skills_db`` keeps get_db isolated."""
    app = FastAPI()
    app.include_router(skills_router.router, prefix="/api/v1/skills")
    app.dependency_overrides[get_admin_user] = lambda: _U("admin")
    app.dependency_overrides[get_verified_user] = lambda: _U("user")
    return TestClient(app)


def test_create_list_get_skill(client):
    r = client.post(
        "/api/v1/skills/",
        json={
            "id": "router-1",
            "name": "writer",
            "description": "d",
            "content": "c",
            "meta": {},
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "writer"

    lst = client.get("/api/v1/skills/").json()
    assert any(s["id"] == "router-1" for s in lst["skills"])

    one = client.get("/api/v1/skills/router-1").json()
    assert one["id"] == "router-1"


def test_set_flags_toggles_active_global(client):
    client.post(
        "/api/v1/skills/",
        json={
            "id": "router-2",
            "name": "n",
            "description": "d",
            "content": "c",
            "meta": {},
        },
    )
    r = client.patch(
        "/api/v1/skills/router-2/flags",
        json={"is_active": True, "is_global": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_active"] is True
    assert r.json()["is_global"] is True


def test_delete_builtin_is_rejected(client):
    client.post(
        "/api/v1/skills/",
        json={
            "id": "router-3",
            "name": "n",
            "description": "d",
            "content": "c",
            "meta": {},
        },
    )
    Skills.update_skill_by_id("router-3", {"is_builtin": True})
    r = client.delete("/api/v1/skills/router-3")
    assert r.status_code == 403
    # Row still exists (just disabled).
    assert Skills.get_skill_by_id("router-3") is not None


def test_import_valid_md(client):
    md = "---\nname: imported\ndescription: an imported skill\n---\n# Body\nDo the thing.\n"
    r = client.post("/api/v1/skills/import", json={"content": md, "format": "md"})
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "imported"
    assert "Body" in r.json()["content"]


def test_import_rejects_missing_description(client):
    md = "---\nname: nodesc\n---\nbody"
    r = client.post("/api/v1/skills/import", json={"content": md, "format": "md"})
    assert r.status_code == 422
