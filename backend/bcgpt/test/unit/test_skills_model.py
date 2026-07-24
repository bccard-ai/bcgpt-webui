"""Unit tests for the Skill model and SkillsTable CRUD.

Uses the shared ``skills_db`` fixture (isolated SQLite + ``skill`` table,
monkeypatched ``get_db``) so these tests run hermetically inside the full
unit suite as well as in isolation.
"""

from __future__ import annotations

import pytest

from bcgpt.models import SkillForm, SkillMeta, Skills

pytestmark = pytest.mark.usefixtures("skills_db")


def _form(
    id_: str = "skill-1",
    name: str = "technical-writing",
    description: str = "Writes clear docs",
) -> SkillForm:
    return SkillForm(
        id=id_,
        name=name,
        description=description,
        content="# Body\nWrite docs.",
        meta=SkillMeta(description=description),
    )


def test_insert_and_get_skill_round_trip():
    created = Skills.insert_new_skill(user_id="user-1", form_data=_form())
    assert created is not None
    assert created.id == "skill-1"
    assert created.name == "technical-writing"
    assert created.is_active is False
    assert created.is_global is False
    assert created.is_builtin is False

    fetched = Skills.get_skill_by_id("skill-1")
    assert fetched is not None
    assert fetched.content == "# Body\nWrite docs."


def test_get_skills_active_only_filters_inactive():
    Skills.insert_new_skill(user_id="u", form_data=_form())
    Skills.update_skill_by_id("skill-1", {"is_active": True})
    active = Skills.get_skills(active_only=True)
    assert any(s.id == "skill-1" for s in active)


def test_get_active_global_skills_filters_correctly():
    Skills.insert_new_skill(user_id="u", form_data=_form())
    Skills.update_skill_by_id("skill-1", {"is_active": True, "is_global": True})
    globs = Skills.get_active_global_skills()
    assert len(globs) == 1 and globs[0].id == "skill-1"


def test_get_skills_for_user_returns_only_own_non_global():
    Skills.insert_new_skill(user_id="user-1", form_data=_form("a", "a", "a"))
    Skills.insert_new_skill(user_id="user-2", form_data=_form("b", "b", "b"))
    Skills.update_skill_by_id("b", {"is_global": True})
    mine = Skills.get_skills_for_user("user-1")
    assert [s.id for s in mine] == ["a"]


def test_delete_skill_by_id():
    Skills.insert_new_skill(user_id="u", form_data=_form())
    assert Skills.delete_skill_by_id("skill-1") is True
    assert Skills.get_skill_by_id("skill-1") is None


def test_update_skill_by_id_changes_fields():
    Skills.insert_new_skill(user_id="u", form_data=_form())
    updated = Skills.update_skill_by_id(
        "skill-1", {"description": "updated", "is_global": True}
    )
    assert updated is not None
    assert updated.description == "updated"
    assert updated.is_global is True
