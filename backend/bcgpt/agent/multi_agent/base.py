"""Shared helpers for multi-agent executors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from bcgpt.agent.llm import extract_content, llm_complete


@dataclass
class AgentSpec:
    model_id: str
    role: str = "agent"
    system_prompt: Optional[str] = None
    params: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> "AgentSpec":
        return cls(
            model_id=d["model_id"],
            role=d.get("role", "agent"),
            system_prompt=d.get("system_prompt"),
            params=d.get("params") or {},
        )


def parse_agents(agents: list[dict]) -> list[AgentSpec]:
    specs = [AgentSpec.from_dict(a) for a in (agents or []) if a.get("model_id")]
    if not specs:
        raise ValueError("multi-agent execution requires at least one agent")
    return specs


async def ask_agent(
    request: Any,
    user: Any,
    spec: AgentSpec,
    user_content: str,
    *,
    extra_system: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> str:
    """Single-turn ask to one agent; returns its text content."""
    messages: list[dict] = []
    system_bits = [s for s in (spec.system_prompt, extra_system) if s]
    if system_bits:
        messages.append({"role": "system", "content": "\n\n".join(system_bits)})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_content})

    resp = await llm_complete(
        request, user, spec.model_id, messages, params=spec.params
    )
    return extract_content(resp)
