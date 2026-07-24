"""Tests for the skill runtime helpers (catalog text + read_skill descriptor)."""

from __future__ import annotations

import asyncio

import pytest

from bcgpt.models import SkillForm, SkillMeta, SkillModel, Skills
from bcgpt.utils.skill_runtime import (
    build_skill_catalog,
    make_read_skill_descriptor,
)

pytestmark = pytest.mark.usefixtures("skills_db")


def _run(coro):
    """Drive a coroutine on a throwaway event loop.

    Using a fresh loop each call (rather than the global ``get_event_loop()``)
    keeps these tests immune to loop state left behind by earlier tests in the
    full unit suite (closed/running global loop).
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _U:
    id = "user-1"
    role = "user"
    settings = {}


def test_catalog_empty_when_no_skills():
    assert build_skill_catalog([]) == ""


def test_catalog_lists_names_and_description():
    s = SkillModel(
        id="x",
        user_id="u",
        name="writer",
        description="Writes docs",
        content="c",
        meta=SkillMeta(),
        is_active=True,
        is_global=True,
        updated_at=0,
        created_at=0,
    )
    text = build_skill_catalog([s])
    assert "writer" in text and "Writes docs" in text
    assert "read_skill" in text


def test_read_skill_descriptor_shape():
    desc = make_read_skill_descriptor(_U())
    assert desc["spec"]["name"] == "read_skill"
    assert callable(desc["callable"])
    assert desc["toolkit_id"] == "__skills__"


def test_read_skill_callable_returns_body():
    Skills.insert_new_skill(
        user_id="u",
        form_data=SkillForm(
            id="rs-1", name="rsname", description="d", content="BODY", meta=SkillMeta()
        ),
    )
    Skills.update_skill_by_id("rs-1", {"is_active": True, "is_global": True})
    desc = make_read_skill_descriptor(_U())
    out = _run(desc["callable"](skill_name="rsname"))
    assert "BODY" in out


def test_read_skill_callable_unknown_skill():
    desc = make_read_skill_descriptor(_U())
    out = _run(desc["callable"](skill_name="nope"))
    assert "not found" in out
