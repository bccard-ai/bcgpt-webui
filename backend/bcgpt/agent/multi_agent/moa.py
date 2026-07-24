"""Mixture of Agents: proposer agents draft, an aggregator synthesises.

Mirrors the existing ``/tasks/moa/completions`` idea but generalised to N
proposers + one aggregator, as an option within the unified multi-agent API.

v2: Council-style structured synthesis (SC-MoA / Council Mode inspired).
The aggregator produces a 4-section output — consensus, disagreement,
unique findings, analysis — reducing hallucination by forcing explicit
attribution of claims to proposer sources.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent

_COUNCIL_AGGREGATOR_PROMPT = (
    "You are a Council Synthesizer. You have received responses from several "
    "models to the same task. Produce a single, high-quality synthesis that "
    "strictly follows this 4-section structure.\n\n"
    "## Task\n{task}\n\n"
    "## Model Responses\n{responses}\n\n"
    "## Your Output Format (JSON)\n"
    "Respond with ONLY a JSON object:\n"
    "{{\n"
    '  "consensus": "Points ALL models agree on, with attribution.",\n'
    '  "disagreement": "Points where models diverge, stating each view.",\n'
    '  "unique_findings": "Valuable insights unique to individual models.",\n'
    '  "analysis": "Your reasoned judgment reconciling conflicts, citing evidence.",\n'
    '  "final_answer": "The single best answer synthesizing all of the above."\n'
    "}}\n\n"
    "Rules:\n"
    "- Every factual claim must be attributed to at least one model.\n"
    "- If models disagree on a point, do NOT pick a winner silently — state the disagreement.\n"
    "- The final_answer must be internally consistent with the analysis.\n"
    "- Do not introduce information not present in any model response."
)


async def execute_moa(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    # Last agent is the aggregator if a dedicated one isn't configured;
    # otherwise all agents propose and the configured aggregator synthesises.
    aggregator_id = config.get("aggregator_model_id")
    if aggregator_id:
        proposers = agents
    else:
        proposers = agents[:-1] if len(agents) > 1 else agents
        aggregator_id = agents[-1].model_id

    proposals = await asyncio.gather(
        *[ask_agent(request, user, s, input_text) for s in proposers]
    )
    labelled = [
        {"role": s.role, "model_id": s.model_id, "output": o}
        for s, o in zip(proposers, proposals)
    ]

    responses_block = "\n\n".join(
        f"{i+1}. [{p['model_id']} ({p['role']})]: {p['output']}"
        for i, p in enumerate(labelled)
    )

    synthesis = await ask_agent(
        request,
        user,
        AgentSpec(model_id=aggregator_id, role="aggregator"),
        _COUNCIL_AGGREGATOR_PROMPT.format(task=input_text, responses=responses_block),
    )

    return {
        "pattern": "moa",
        "output": synthesis,
        "proposals": labelled,
        "aggregator_model_id": aggregator_id,
    }
