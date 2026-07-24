"""Skill progressive-disclosure runtime helpers.

``build_skill_catalog`` renders the always-on Layer-1 catalog (one line per
active skill, injected into the system prompt). ``make_read_skill_descriptor``
builds the synthetic ``read_skill`` tool descriptor that the model calls to
load a skill's full body or a bundled reference file on demand (Layer 2).

Both are consumed by ``process_chat_payload`` in ``bcgpt.utils.middleware``.
Kept in this separate module so they can be unit-tested without importing the
full chat middleware stack.
"""

from __future__ import annotations

from typing import Any

READ_SKILL_SPEC = {
    "name": "read_skill",
    "description": (
        "Open a skill by name to read its full instructions, or pass file_path "
        "to read a bundled reference file. Use this when you decide to apply a "
        "skill listed in <available-skills>."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "skill_name": {"type": "string", "description": "The skill name."},
            "file_path": {
                "type": "string",
                "description": "Optional bundled reference file path.",
            },
        },
        "required": ["skill_name"],
    },
}


def build_skill_catalog(skills: list) -> str:
    """Render the always-on Layer-1 catalog text. Empty string when no skills."""
    if not skills:
        return ""
    lines = [
        "<available-skills>",
        "The following skills are available. Call `read_skill(skill_name)` "
        "to open one and read its full instructions or bundled files.",
    ]
    for s in skills:
        lines.append(f"- {s.name} — {s.description or ''}".rstrip())
    lines.append("</available-skills>")
    return "\n".join(lines)


def make_read_skill_descriptor(user: Any) -> dict:
    """Build the synthetic read_skill tool descriptor for ``tools_dict``."""
    # Local import keeps this module importable without the extensions chain.
    from bcgpt.utils.extensions import resolve_effective_skills

    async def _read_skill_callable(
        skill_name: str, file_path: str | None = None
    ) -> str:
        match = next(
            (s for s in resolve_effective_skills(user) if s.name == skill_name),
            None,
        )
        if match is None:
            return f"Skill '{skill_name}' not found or not enabled."
        if file_path:
            resources = (match.meta.resources or {}) if match.meta else {}
            if file_path not in resources:
                return f"File '{file_path}' not found in skill '{skill_name}'."
            return resources[file_path]
        return match.content or ""

    return {
        "spec": READ_SKILL_SPEC,
        "callable": _read_skill_callable,
        "toolkit_id": "__skills__",
    }
