"""Sequential pattern: A → B → C, each agent refines the previous output."""

from __future__ import annotations

from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent


async def execute_sequential(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    steps: list[dict] = []
    current = input_text
    for i, spec in enumerate(agents):
        if i == 0:
            prompt = current
        else:
            prompt = (
                f"Original task:\n{input_text}\n\n"
                f"Previous agent's output:\n{current}\n\n"
                f"As the '{spec.role}', improve, extend, or correct it."
            )
        out = await ask_agent(request, user, spec, prompt)
        steps.append({"role": spec.role, "model_id": spec.model_id, "output": out})
        current = out

    return {
        "pattern": "sequential",
        "output": current,
        "steps": steps,
    }
