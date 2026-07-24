"""Voting pattern: agents answer, a judge extracts the best reasoning trace
and synthesizes a superior answer (SC-MoA inspired trace-level synthesis).

Instead of simple majority tally, the judge performs element-level extraction
across all agent outputs, identifying the strongest reasoning elements from
each and composing them into a single trace-synthesized answer.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent
from bcgpt.agent.quality.base import judge_json

_TRACE_SYNTHESIS_SYSTEM = (
    "You are a Trace Synthesis Judge. You have received answers from multiple "
    "agents to the same task. Your job is NOT majority voting. Instead:\n"
    "1. Decompose each answer into its reasoning steps and factual claims.\n"
    "2. Identify the strongest elements across ALL answers (even minority ones).\n"
    "3. Synthesize a superior answer that combines the best reasoning trace.\n\n"
    "Output ONLY JSON:\n"
    "{\n"
    '  "elements": [{"source": "agent_role", "element": "str", "quality": "high|medium|low"}],\n'
    '  "best_trace": "The combined best reasoning chain.",\n'
    '  "synthesized_answer": "The final answer synthesizing best elements.",\n'
    '  "confidence": 0.0-1.0\n'
    "}\n\n"
    "Rules:\n"
    "- A minority answer may contain the best reasoning for a sub-problem.\n"
    "- Extract elements even from answers you ultimately disagree with.\n"
    "- The synthesized_answer must be strictly better than any individual answer.\n"
    "- confidence reflects how well the elements compose into a coherent answer."
)


async def execute_voting(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    answers = await asyncio.gather(
        *[ask_agent(request, user, s, input_text) for s in agents]
    )
    ballots = [
        {"role": s.role, "model_id": s.model_id, "output": o}
        for s, o in zip(agents, answers)
    ]

    judge_id = config.get("judge_model_id") or agents[0].model_id
    verdict = await judge_json(
        request,
        user,
        judge_id,
        _TRACE_SYNTHESIS_SYSTEM,
        "Task:\n"
        + input_text
        + "\n\nAnswers:\n"
        + "\n".join(f"[{b['role']}]: {b['output']}" for b in ballots),
    )

    synthesized = ""
    elements: list[dict] = []
    best_trace = ""
    confidence = 0.0

    if isinstance(verdict, dict):
        elems = verdict.get("elements")
        if isinstance(elems, list):
            elements = elems
        best_trace = str(verdict.get("best_trace", ""))
        synthesized = str(verdict.get("synthesized_answer", ""))
        try:
            confidence = float(verdict.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

    # Fallback: if synthesis failed, use first answer
    if not synthesized and ballots:
        synthesized = ballots[0]["output"]

    return {
        "pattern": "voting",
        "output": synthesized,
        "ballots": ballots,
        "elements": elements,
        "best_trace": best_trace,
        "confidence": confidence,
    }
