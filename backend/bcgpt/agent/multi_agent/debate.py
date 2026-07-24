"""Debate pattern: agents critique each other over rounds with position
anchoring and confidence tracking (anchored refinement).

Key improvements over basic debate:
- Position anchoring: Each agent's opening position is preserved as an anchor.
  Subsequent refinements must explicitly acknowledge if they're departing
  from their anchor and justify why.
- Confidence tracking: Each round, agents self-assess confidence (0-1).
  When confidence stabilizes (delta < 0.05 across all agents), debate
  converges early.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent

_ANCHORED_REFINE_PROMPT = (
    "Task:\n{task}\n\n"
    "Your anchored opening position:\n{anchor}\n\n"
    "Other agents' current positions:\n{others}\n\n"
    "As '{role}', critique the others and refine your answer.\n"
    "RULES:\n"
    "- If you change your position from your anchor, explicitly state what changed and why.\n"
    "- If you maintain your position, state what evidence supports it.\n"
    "- End your response with a confidence score: CONFIDENCE: 0.XX\n"
    "- Respond first with your refined answer, then on the last line: CONFIDENCE: 0.XX"
)

_CONFIDENCE_REGEX_FALLBACK = 0.7  # default if parsing fails


def _extract_confidence(text: str) -> float:
    """Extract confidence score from agent response."""
    import re

    match = re.search(r"CONFIDENCE:\s*([0-1]?\.\d+)", text)
    if match:
        try:
            val = float(match.group(1))
            return max(0.0, min(1.0, val))
        except ValueError:
            pass
    return _CONFIDENCE_REGEX_FALLBACK


def _confidence_stabilized(
    prev: list[float], curr: list[float], delta: float = 0.05
) -> bool:
    """Check if confidence scores have stabilized across all agents."""
    if not prev or len(prev) != len(curr):
        return False
    return all(abs(p - c) < delta for p, c in zip(prev, curr))


async def execute_debate(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    rounds = max(1, int(config.get("rounds", 3)))
    transcript: list[dict] = []

    # ── Round 1: Independent opening answers (anchors) ────────────────
    opening = await asyncio.gather(
        *[ask_agent(request, user, s, input_text) for s in agents]
    )
    anchors = [
        {
            "role": s.role,
            "model_id": s.model_id,
            "output": o,
            "anchor": o,
            "confidence": _extract_confidence(o),
        }
        for s, o in zip(agents, opening)
    ]
    transcript.append({"round": 1, "type": "opening", "responses": anchors})

    prev_confidences = [a["confidence"] for a in anchors]
    current = anchors

    # ── Subsequent rounds: Anchored refinement ────────────────────────
    for r in range(2, rounds + 1):
        others_by_role = {c["role"]: c["output"] for c in current}

        async def refine(spec: AgentSpec, anchor_text: str) -> dict:
            # Build others text excluding this agent
            others_text = "\n\n".join(
                f"[{role}]: {output}"
                for role, output in others_by_role.items()
                if role != spec.role
            )
            prompt = _ANCHORED_REFINE_PROMPT.format(
                task=input_text,
                anchor=anchor_text,
                others=others_text,
                role=spec.role,
            )
            out = await ask_agent(request, user, spec, prompt)
            return {
                "role": spec.role,
                "model_id": spec.model_id,
                "output": out,
                "anchor": anchor_text,
                "confidence": _extract_confidence(out),
            }

        current = await asyncio.gather(
            *[refine(s, a["anchor"]) for s, a in zip(agents, anchors)]
        )
        current = list(current)
        curr_confidences = [c["confidence"] for c in current]
        transcript.append(
            {
                "round": r,
                "type": "refinement",
                "responses": current,
                "confidence_delta": [
                    round(abs(p - c), 3)
                    for p, c in zip(prev_confidences, curr_confidences)
                ],
            }
        )

        # Early convergence: confidence stabilized
        if _confidence_stabilized(prev_confidences, curr_confidences):
            transcript[-1]["early_exit"] = "confidence_stabilized"
            break

        prev_confidences = curr_confidences

    # ── Final Synthesis ───────────────────────────────────────────────
    judge_id = config.get("judge_model_id") or agents[0].model_id
    final_input = "\n\n".join(
        f"[{c['role']}] (confidence: {c['confidence']:.2f}):\n{c['output']}"
        for c in current
    )
    final = await ask_agent(
        request,
        user,
        AgentSpec(model_id=judge_id, role="judge"),
        f"Task:\n{input_text}\n\nFinal positions after anchored debate:\n{final_input}\n\n"
        "Produce the single best, reconciled answer. Weight higher-confidence "
        "positions more heavily. Explicitly resolve any remaining disagreements.",
    )

    return {
        "pattern": "debate",
        "output": final,
        "rounds": rounds,
        "transcript": transcript,
        "final_confidences": [c["confidence"] for c in current],
    }
