"""Parallel pattern: all agents answer concurrently; optional aggregation."""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent


async def execute_parallel(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    max_parallel = int(config.get("max_parallel", len(agents)) or len(agents))
    sem = asyncio.Semaphore(max(1, max_parallel))

    async def run(spec: AgentSpec) -> dict:
        async with sem:
            try:
                out = await ask_agent(request, user, spec, input_text)
            except Exception as e:  # noqa: BLE001
                out = f"[error: {e}]"
            return {"role": spec.role, "model_id": spec.model_id, "output": out}

    responses = await asyncio.gather(*[run(s) for s in agents])

    output = "\n\n".join(
        f"### {r['role']} ({r['model_id']})\n{r['output']}" for r in responses
    )

    # Optional aggregation by a designated aggregator model.
    aggregator = config.get("aggregator_model_id")
    if aggregator:
        joined = "\n\n".join(f"[{r['role']}]: {r['output']}" for r in responses)
        agg_prompt = (
            f"Task:\n{input_text}\n\n"
            f"Candidate answers from multiple agents:\n{joined}\n\n"
            "Synthesise the best, most complete single answer."
        )
        output = await ask_agent(
            request, user, AgentSpec(model_id=aggregator, role="aggregator"), agg_prompt
        )

    return {"pattern": "parallel", "output": output, "responses": responses}
