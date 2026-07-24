"""AgentDefinition: a portable description of an agent.

Maps cleanly onto a BCGPT ``Model`` record (autonomy_level + capabilities live
in ``meta``; system_prompt/params in ``params``) and to/from the Open-MoAI
``.claude/agents/*.md`` YAML-frontmatter format.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bcgpt.agent.types import AgentAutonomyLevel


@dataclass
class AgentDefinition:
    name: str
    description: str = ""
    id: Optional[str] = None
    autonomy_level: str = AgentAutonomyLevel.ASSISTANT.value
    system_prompt: str = ""
    tools: list[str] = field(default_factory=list)
    # Knowledge references are persisted in ``model.meta.knowledge`` as a list of
    # dicts (``{"id", "type": "collection", "source": ...}``); legacy entries may
    # be bare collection-name strings. Preserve items as-is, not stringified.
    knowledge: list = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    workflow: Optional[list] = None  # serialised DAG (list of node dicts)
    model_config_: dict = field(default_factory=dict)  # temperature, max_tokens...

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "autonomy_level": self.autonomy_level,
            "system_prompt": self.system_prompt,
            "tools": list(self.tools),
            "knowledge": list(self.knowledge),
            "capabilities": list(self.capabilities),
            "workflow": self.workflow,
            "model_config": dict(self.model_config_),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "AgentDefinition":
        return cls(
            name=d.get("name") or d.get("id") or "agent",
            description=d.get("description", ""),
            id=d.get("id"),
            autonomy_level=AgentAutonomyLevel.from_value(d.get("autonomy_level")).value,
            system_prompt=d.get("system_prompt", ""),
            tools=_as_list(d.get("tools")),
            knowledge=_as_knowledge_list(d.get("knowledge")),
            capabilities=_as_list(d.get("capabilities")),
            workflow=d.get("workflow"),
            model_config_=d.get("model_config") or {},
        )


def _as_list(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [v.strip() for v in value.split(",") if v.strip()]
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _as_knowledge_list(value) -> list:
    """Preserve knowledge references (dict or str) without stringifying.

    Unlike ``_as_list``, this keeps dict items intact so the persisted
    ``meta.knowledge`` shape (list of dicts) round-trips through import/export.
    A bare string is treated as a single reference (knowledge is not CSV).
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple)):
        return [v for v in value if v]
    return []
