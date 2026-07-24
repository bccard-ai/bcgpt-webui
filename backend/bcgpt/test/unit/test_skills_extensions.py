"""Tests for resolve_effective_skills (admin catalog ∪ user-enabled)."""

from __future__ import annotations

import pytest

from bcgpt.models import SkillForm, SkillMeta, Skills
from bcgpt.utils.extensions import resolve_effective_skills

pytestmark = pytest.mark.usefixtures("skills_db")


class _U:
    def __init__(self, uid, settings=None):
        self.id = uid
        self.role = "user"
        self.settings = settings or {}


def _seed(id_, **flags):
    Skills.insert_new_skill(
        user_id="admin-1",
        form_data=SkillForm(
            id=id_, name=id_, description=id_, content="c", meta=SkillMeta()
        ),
    )
    if flags:
        Skills.update_skill_by_id(id_, flags)


def test_global_active_skills_included():
    _seed("g1", is_active=True, is_global=True)
    rows = resolve_effective_skills(_U("user-1"))
    assert [r.id for r in rows] == ["g1"]


def test_global_inactive_excluded_even_if_user_lists_it():
    _seed("g2", is_active=False, is_global=True)
    rows = resolve_effective_skills(
        _U("user-1", {"ui": {"skills": {"enabled": ["g2"]}}})
    )
    assert rows == []


def test_user_owned_active_included():
    _seed("u1", is_active=True)
    Skills.update_skill_by_id("u1", {"user_id": "user-1", "is_global": False})
    rows = resolve_effective_skills(_U("user-1"))
    assert "u1" in [r.id for r in rows]


def test_skill_ids_restricts_to_intersection():
    _seed("r1", is_active=True, is_global=True)
    _seed("r2", is_active=True, is_global=True)
    rows = resolve_effective_skills(_U("user-1"), skill_ids=["r1"])
    assert [r.id for r in rows] == ["r1"]
