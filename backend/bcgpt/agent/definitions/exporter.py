"""Export agent/skill definitions to YAML-frontmatter Markdown or JSON."""

from __future__ import annotations

import json

from bcgpt.agent.definitions.agent_definition import AgentDefinition
from bcgpt.agent.definitions.skill_definition import SkillDefinition


def _dump_frontmatter(meta: dict, body: str) -> str:
    import yaml

    fm = yaml.safe_dump(meta, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{fm}\n---\n\n{body}\n"


def export_agent(defn: AgentDefinition, fmt: str = "md") -> str:
    if fmt == "json":
        return json.dumps(defn.to_dict(), ensure_ascii=False, indent=2)
    meta = {
        "name": defn.name,
        "description": defn.description,
        "autonomy_level": defn.autonomy_level,
        "tools": defn.tools,
        "knowledge": defn.knowledge,
        "capabilities": defn.capabilities,
    }
    if defn.model_config_:
        meta["model_config"] = defn.model_config_
    if defn.workflow:
        meta["workflow"] = defn.workflow
    meta = {k: v for k, v in meta.items() if v not in (None, [], {})}
    return _dump_frontmatter(meta, defn.system_prompt or "")


def export_skill(defn: SkillDefinition, fmt: str = "md") -> str:
    if fmt == "json":
        return json.dumps(defn.to_dict(), ensure_ascii=False, indent=2)
    meta = {
        "name": defn.name,
        "description": defn.description,
        "tools": defn.tools,
        "required_capabilities": defn.required_capabilities,
    }
    meta = {k: v for k, v in meta.items() if v not in (None, [], {})}
    return _dump_frontmatter(meta, defn.prompt_template or "")
