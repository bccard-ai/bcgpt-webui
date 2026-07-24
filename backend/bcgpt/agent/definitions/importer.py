"""Import agent/skill definitions from YAML-frontmatter Markdown or JSON.

Frontmatter format (Open-MoAI ``.claude/agents/*.md`` style)::

    ---
    name: fullstack-developer
    description: End-to-end feature owner
    tools: Read, Write, Bash
    autonomy_level: operator
    ---

    # Markdown body → becomes system_prompt (agent) / prompt_template (skill)
"""

from __future__ import annotations

import json
import re
from typing import Tuple

from bcgpt.agent.definitions.agent_definition import AgentDefinition
from bcgpt.agent.definitions.skill_definition import SkillDefinition

_FRONTMATTER = re.compile(r"^\s*---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_frontmatter(text: str) -> Tuple[dict, str]:
    """Split YAML frontmatter from the markdown body. Returns (meta, body)."""
    match = _FRONTMATTER.match(text or "")
    if not match:
        return {}, (text or "").strip()
    raw_meta, body = match.group(1), match.group(2)
    try:
        import yaml

        meta = yaml.safe_load(raw_meta) or {}
    except ModuleNotFoundError as e:  # pragma: no cover
        raise RuntimeError("PyYAML is required to parse frontmatter") from e
    if not isinstance(meta, dict):
        meta = {}
    return meta, body.strip()


def import_agent(content, fmt: str = "md") -> AgentDefinition:
    if fmt == "json" or isinstance(content, dict):
        data = content if isinstance(content, dict) else json.loads(content)
        return AgentDefinition.from_dict(data)
    meta, body = parse_frontmatter(content)
    data = dict(meta)
    # Body is the system prompt unless explicitly provided in frontmatter.
    data.setdefault("system_prompt", body)
    # 'model' frontmatter key maps into model_config for convenience.
    if "model" in meta and "model_config" not in meta:
        data["model_config"] = {"model": meta["model"]}
    return AgentDefinition.from_dict(data)


def import_skill(content, fmt: str = "md") -> SkillDefinition:
    if fmt == "json" or isinstance(content, dict):
        data = content if isinstance(content, dict) else json.loads(content)
        return SkillDefinition.from_dict(data)
    meta, body = parse_frontmatter(content)
    data = dict(meta)
    data.setdefault("prompt_template", body)
    return SkillDefinition.from_dict(data)
