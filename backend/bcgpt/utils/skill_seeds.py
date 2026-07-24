"""Curated built-in SKILL.md seeds (prompt + reference content; no scripts).

``seed_builtin_skills`` is idempotent: it inserts each curated skill only if no
skill with that name exists yet, marking it ``is_builtin=True, is_global=True,
is_active=True``. Called from application startup.
"""

from __future__ import annotations

from bcgpt.models import SkillForm, SkillMeta, Skills

# name -> (description, markdown body)
_BUILTIN_BODIES: dict[str, tuple[str, str]] = {
    "technical-writing": (
        "Plan, draft, and revise clear technical documentation.",
        "# Technical Writing\nAsk clarifying questions about the audience and goal. "
        "Outline before drafting. Prefer short sentences, active voice, and concrete "
        "examples. Revise once for structure and once for clarity.\n",
    ),
    "code-review": (
        "Review code for correctness, security, and clarity.",
        "# Code Review\nRead the change twice. First: does it do what it claims, and "
        "are there bugs or security issues? Second: is it clear and consistent with "
        "surrounding code? Report findings most-severe first, with file:line anchors.\n",
    ),
    "document-creation": (
        "Produce well-structured markdown or document deliverables.",
        "# Document Creation\nAgree on format, length, and audience before writing. "
        "Use a short outline. Keep prose tight; use lists only when items are parallel "
        "and non-prose would be clearer.\n",
    ),
    "data-analysis-plan": (
        "Plan a data-analysis approach before touching data.",
        "# Data Analysis Plan\nState the question and the decision it supports. "
        "Identify the data needed, the comparison or metric, and confounders. Pick the "
        "simplest method that answers the question.\n",
    ),
    "research-workflow": (
        "Structure a multi-source research workflow with citations.",
        "# Research Workflow\nDecompose the question into sub-questions. Search "
        "breadth-first, triangulate across independent sources, prefer primary over "
        "secondary. Track every claim to a source.\n",
    ),
    "translation-ko-en": (
        "Translate between Korean and English with natural phrasing.",
        "# Korean ↔ English Translation\nPreserve meaning and tone, not word order. "
        "After a draft, read it aloud in the target language and revise anything that "
        "sounds translated. Flag ambiguities instead of guessing.\n",
    ),
}

BUILTIN_SKILL_IDS: list[str] = list(_BUILTIN_BODIES.keys())


def seed_builtin_skills() -> int:
    """Insert curated builtins (idempotent). Returns the number newly inserted."""
    existing = {s.name for s in Skills.get_skills()}
    inserted = 0
    for name, (desc, body) in _BUILTIN_BODIES.items():
        if name in existing:
            continue
        skill_id = f"builtin-{name}"
        form = SkillForm(
            id=skill_id,
            name=name,
            description=desc,
            content=body,
            meta=SkillMeta(description=desc, tags=["builtin"]),
        )
        created = Skills.insert_new_skill(user_id="system", form_data=form)
        if created is None:
            continue
        Skills.update_skill_by_id(
            skill_id,
            {"is_builtin": True, "is_global": True, "is_active": True},
        )
        inserted += 1
    return inserted
