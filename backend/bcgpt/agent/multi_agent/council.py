"""Council pattern: heterogeneous models deliberate with structured synthesis.

Inspired by Council Mode research: heterogeneous models (different capabilities,
sizes, or specializations) each answer independently, then a structured
4-section synthesis is produced:
  1. Consensus — points all models agree on
  2. Disagreement — where models diverge
  3. Unique Findings — insights unique to individual models
  4. Analysis — reasoned judgment reconciling conflicts

This pattern achieves ~35.9% hallucination reduction by forcing explicit
attribution and conflict resolution rather than naive merging.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent
from bcgpt.agent.quality.base import judge_json

_COUNCIL_DELIBERATE_SYSTEM = (
    "You are participating in a council of heterogeneous AI models. "
    "Each model has different strengths. Answer the task below thoroughly, "
    "noting your confidence level and any areas of uncertainty.\n\n"
    "At the end of your response, add: CONFIDENCE: 0.XX"
)

_COUNCIL_SYNTHESIS_SYSTEM = (
    "You are the Council Synthesizer. You have received deliberations from "
    "heterogeneous AI models. Produce a structured synthesis.\n\n"
    "Output ONLY JSON:\n"
    "{{\n"
    '  "consensus": "Points ALL models agree on, with attribution.",\n'
    '  "disagreement": "Points where models diverge, stating each view.",\n'
    '  "unique_findings": "Valuable insights unique to individual models.",\n'
    '  "analysis": "Your reasoned judgment reconciling conflicts, citing evidence.",\n'
    '  "final_answer": "The single best answer synthesizing all of the above.",\n'
    '  "confidence": 0.0-1.0\n'
    "}}\n\n"
    "Rules:\n"
    "- Attribute every claim to its source model.\n"
    "- Never silently pick a winner for disagreements — document them.\n"
    "- The final_answer must be consistent with the analysis section.\n"
    "- Do not introduce information not present in any model response.\n"
    "- Weight models by their expressed confidence, but verify claims independently."
)

_CROSS_EXAM_SYSTEM = (
    "You are model '{role}'. You just saw the other council members' deliberations. "
    "In 2-3 sentences, respond to any claims you disagree with or can improve upon. "
    "If you agree with everything, confirm and add any missing nuance."
)


def _extract_confidence(text: str) -> float:
    import re

    match = re.search(r"CONFIDENCE:\s*([0-1]?\.\d+)", text)
    if match:
        try:
            return max(0.0, min(1.0, float(match.group(1))))
        except ValueError:
            pass
    return 0.7


async def execute_council(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    rounds = max(
        1, int(config.get("rounds", 2))
    )  # default 2: deliberate + cross-examine
    judge_id = config.get("judge_model_id") or agents[0].model_id

    # ── Round 1: Independent deliberation ─────────────────────────────
    deliberations = await asyncio.gather(
        *[
            ask_agent(
                request, user, s, input_text, extra_system=_COUNCIL_DELIBERATE_SYSTEM
            )
            for s in agents
        ]
    )
    council_responses = [
        {
            "role": s.role,
            "model_id": s.model_id,
            "output": o,
            "confidence": _extract_confidence(o),
        }
        for s, o in zip(agents, deliberations)
    ]

    transcript: list[dict] = [
        {"round": 1, "type": "deliberation", "responses": council_responses}
    ]

    # ── Round 2+: Cross-examination ───────────────────────────────────
    if rounds >= 2:
        others_text = "\n\n".join(
            f"[{r['role']} ({r['model_id']}, confidence: {r['confidence']:.2f})]: {r['output']}"
            for r in council_responses
        )

        async def cross_examine(spec: AgentSpec) -> dict:
            prompt = (
                f"Original task:\n{input_text}\n\n"
                f"Council deliberations:\n{others_text}\n\n"
                + _CROSS_EXAM_SYSTEM.format(role=spec.role)
            )
            out = await ask_agent(request, user, spec, prompt)
            return {
                "role": spec.role,
                "model_id": spec.model_id,
                "output": out,
                "confidence": _extract_confidence(out),
            }

        cross_examinations = list(
            await asyncio.gather(*[cross_examine(s) for s in agents])
        )
        transcript.append(
            {"round": 2, "type": "cross_examination", "responses": cross_examinations}
        )

    # ── Structured Synthesis ──────────────────────────────────────────
    all_responses = "\n\n".join(
        f"[{r['role']} ({r['model_id']}, confidence: {r['confidence']:.2f})]: {r['output']}"
        for r in council_responses
    )

    if len(transcript) > 1:
        cross_text = "\n\n".join(
            f"[{r['role']}]: {r['output']}" for r in cross_examinations
        )
        all_responses += f"\n\n--- Cross-Examination Responses ---\n{cross_text}"

    synthesis = await judge_json(
        request,
        user,
        judge_id,
        _COUNCIL_SYNTHESIS_SYSTEM,
        f"Task:\n{input_text}\n\nCouncil Deliberations:\n{all_responses}",
    )

    final_answer = ""
    consensus = ""
    disagreement = ""
    unique_findings = ""
    analysis = ""
    confidence = 0.0

    if isinstance(synthesis, dict):
        consensus = str(synthesis.get("consensus", ""))
        disagreement = str(synthesis.get("disagreement", ""))
        unique_findings = str(synthesis.get("unique_findings", ""))
        analysis = str(synthesis.get("analysis", ""))
        final_answer = str(synthesis.get("final_answer", ""))
        try:
            confidence = float(synthesis.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0

    if not final_answer:
        final_answer = council_responses[0]["output"]

    return {
        "pattern": "council",
        "output": final_answer,
        "council_responses": council_responses,
        "structured_synthesis": {
            "consensus": consensus,
            "disagreement": disagreement,
            "unique_findings": unique_findings,
            "analysis": analysis,
        },
        "confidence": confidence,
        "rounds": rounds,
        "transcript": transcript,
    }
