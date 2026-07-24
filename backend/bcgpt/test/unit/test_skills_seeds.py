"""Tests for builtin skill seeding (idempotent)."""

from __future__ import annotations

import pytest

from bcgpt.models import Skills
from bcgpt.utils.skill_seeds import BUILTIN_SKILL_IDS, seed_builtin_skills

pytestmark = pytest.mark.usefixtures("skills_db")


def test_seed_creates_all_builtins():
    inserted = seed_builtin_skills()
    assert inserted == len(BUILTIN_SKILL_IDS)
    names = {r.name for r in Skills.get_skills()}
    assert set(BUILTIN_SKILL_IDS) <= names
    for r in Skills.get_skills():
        assert r.is_builtin is True
        assert r.is_global is True
        assert r.is_active is True


def test_seed_is_idempotent():
    seed_builtin_skills()
    again = seed_builtin_skills()
    assert again == 0
