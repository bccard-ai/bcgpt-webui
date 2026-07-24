"""SkillDefinition: a reusable, named capability (prompt template + tools)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from bcgpt.agent.definitions.agent_definition import _as_list


@dataclass
class SkillDefinition:
    name: str
    description: str = ""
    id: Optional[str] = None
    prompt_template: str = ""
    tools: list[str] = field(default_factory=list)
    required_capabilities: list[str] = field(default_factory=list)
    resources: dict = field(default_factory=dict)  # {relative_path: text_content}

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "prompt_template": self.prompt_template,
            "tools": list(self.tools),
            "required_capabilities": list(self.required_capabilities),
            "resources": dict(self.resources),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SkillDefinition":
        resources = d.get("resources")
        return cls(
            name=d.get("name") or d.get("id") or "skill",
            description=d.get("description", ""),
            id=d.get("id"),
            prompt_template=d.get("prompt_template", ""),
            tools=_as_list(d.get("tools")),
            required_capabilities=_as_list(d.get("required_capabilities")),
            resources=resources if isinstance(resources, dict) else {},
        )
