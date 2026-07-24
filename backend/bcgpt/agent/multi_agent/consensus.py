"""Consensus pattern: progressive escalation (HCP-MAD inspired).

3-stage process:
  Stage 1 — Pair Verification: Agents paired up, each pair verifies
    agreement. If all pairs agree, exit early.
  Stage 2 — Pair Debate: Disagreeing pairs debate their differences,
    attempting convergence.
  Stage 3 — Full Synthesis: Remaining disagreements escalated to a
    judge who synthesizes the final consensus answer.

This avoids the cost of full-group deliberation when simple pairs agree,
and provides structured escalation for genuine disagreements.
"""

from __future__ import annotations

import asyncio
from typing import Any

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent
from bcgpt.agent.quality.base import judge_json

_PAIR_AGREE_SYSTEM = (
    "Two agents answered the same task. Assess if they agree on the core answer.\n"
    "Output ONLY JSON: "
    '{"agreed": bool, "agreement_score": 0.0-1.0, "shared_answer": str}.'
)

_PAIR_DEBATE_SYSTEM = (
    "You are mediating a debate between two agents who disagree. "
    "Help them find common ground.\n"
    "Output ONLY JSON: "
    '{"resolved": bool, "compromise_answer": str, "remaining_issue": str}.'
)

_CONSENSUS_SYSTEM = (
    "You assess how much a set of agent answers agree after structured "
    "deliberation. Output ONLY JSON: "
    '{"agreement": 0.0-1.0, "consensus_answer": str, '
    '"unresolved_points": [str]}. The consensus_answer is the best single '
    "answer reflecting the shared view."
)


def _pair_up(agents: list[AgentSpec]) -> list[tuple[int, int]]:
    """Return index pairs. Odd agent out is paired with itself as self-check."""
    pairs = []
    for i in range(0, len(agents) - 1, 2):
        pairs.append((i, i + 1))
    if len(agents) % 2 == 1:
        # Odd agent: self-pair (trivially agrees)
        pairs.append((len(agents) - 1, len(agents) - 1))
    return pairs


async def execute_consensus(
    request: Any,
    user: Any,
    agents: list[AgentSpec],
    input_text: str,
    config: dict,
) -> dict:
    threshold = float(config.get("threshold", 0.8))
    max_rounds = max(1, int(config.get("rounds", 3)))
    judge_id = config.get("judge_model_id") or agents[0].model_id

    history: list[dict] = []

    # ── Stage 0: Initial answers ──────────────────────────────────────
    current_answers = await asyncio.gather(
        *[ask_agent(request, user, s, input_text) for s in agents]
    )
    labelled = [{"role": s.role, "output": o} for s, o in zip(agents, current_answers)]
    history.append({"stage": "initial", "answers": labelled})

    # ── Stage 1: Pair Verification ────────────────────────────────────
    pairs = _pair_up(agents)
    pair_results: list[dict] = []
    all_pairs_agreed = True

    async def verify_pair(i: int, j: int) -> dict:
        if i == j:
            # Self-check: trivially agree
            return {
                "pair": (agents[i].role, agents[i].role),
                "agreed": True,
                "score": 1.0,
                "shared": current_answers[i],
            }
        v = await judge_json(
            request,
            user,
            judge_id,
            _PAIR_AGREE_SYSTEM,
            f"[{agents[i].role}]: {current_answers[i]}\n\n"
            f"[{agents[j].role}]: {current_answers[j]}",
        )
        agreed = False
        score = 0.0
        shared = ""
        if isinstance(v, dict):
            agreed = bool(v.get("agreed", False))
            try:
                score = float(v.get("agreement_score", 0.0))
            except (TypeError, ValueError):
                score = 0.0
            shared = str(v.get("shared_answer", ""))
        return {
            "pair": (agents[i].role, agents[j].role),
            "agreed": agreed,
            "score": score,
            "shared": shared,
        }

    pair_results = await asyncio.gather(*[verify_pair(i, j) for i, j in pairs])
    history.append({"stage": "pair_verification", "results": pair_results})

    for pr in pair_results:
        if not pr["agreed"]:
            all_pairs_agreed = False
            break

    if all_pairs_agreed:
        # Early exit: all pairs agreed
        final = pair_results[0]["shared"] if pair_results else current_answers[0]
        return {
            "pattern": "consensus",
            "output": final,
            "agreement": 1.0,
            "converged": True,
            "early_exit": "pair_verification",
            "threshold": threshold,
            "history": history,
        }

    # ── Stage 2: Pair Debate for disagreeing pairs ────────────────────
    disagreeing_indices: set[int] = set()
    for (i, j), pr in zip(pairs, pair_results):
        if not pr["agreed"]:
            disagreeing_indices.add(i)
            disagreeing_indices.add(j)

    debate_results: list[dict] = []

    async def debate_pair(i: int, j: int) -> dict:
        if i == j:
            return {
                "pair": (agents[i].role,),
                "resolved": True,
                "answer": current_answers[i],
            }
        v = await judge_json(
            request,
            user,
            judge_id,
            _PAIR_DEBATE_SYSTEM,
            f"[{agents[i].role}]: {current_answers[i]}\n\n"
            f"[{agents[j].role}]: {current_answers[j]}\n\n"
            f"Task context: {input_text}",
        )
        resolved = False
        compromise = ""
        issue = ""
        if isinstance(v, dict):
            resolved = bool(v.get("resolved", False))
            compromise = str(v.get("compromise_answer", ""))
            issue = str(v.get("remaining_issue", ""))
        return {
            "pair": (agents[i].role, agents[j].role),
            "resolved": resolved,
            "answer": compromise,
            "issue": issue,
        }

    # Debate only the disagreeing pairs
    disagreeing_pairs = [
        (i, j) for (i, j), pr in zip(pairs, pair_results) if not pr["agreed"]
    ]
    if disagreeing_pairs:
        debate_results = await asyncio.gather(
            *[debate_pair(i, j) for i, j in disagreeing_pairs]
        )
        history.append({"stage": "pair_debate", "results": debate_results})

        # Update current_answers with debate compromises
        for (i, j), dr in zip(disagreeing_pairs, debate_results):
            if dr["resolved"] and dr["answer"]:
                current_answers[i] = dr["answer"]
                current_answers[j] = dr["answer"]

    # Check if debates resolved everything
    all_debates_resolved = (
        all(dr.get("resolved", False) for dr in debate_results)
        if debate_results
        else True
    )
    if all_debates_resolved and debate_results:
        final = debate_results[0]["answer"] if debate_results else current_answers[0]
        return {
            "pattern": "consensus",
            "output": final,
            "agreement": 0.9,
            "converged": True,
            "early_exit": "pair_debate",
            "threshold": threshold,
            "history": history,
        }

    # ── Stage 3: Full Group Synthesis ─────────────────────────────────
    labelled = [{"role": s.role, "output": o} for s, o in zip(agents, current_answers)]

    # Allow reconsideration rounds (legacy behavior for final stage)
    consensus_answer = ""
    agreement = 0.0
    converged = False

    for r in range(1, max_rounds + 1):
        verdict = await judge_json(
            request,
            user,
            judge_id,
            _CONSENSUS_SYSTEM,
            "Answers after pair deliberation:\n"
            + "\n".join(f"[{a['role']}]: {a['output']}" for a in labelled),
        )
        if isinstance(verdict, dict):
            try:
                agreement = float(verdict.get("agreement", 0.0))
            except (TypeError, ValueError):
                agreement = 0.0
            consensus_answer = str(verdict.get("consensus_answer", consensus_answer))

        history.append({"stage": "synthesis", "round": r, "agreement": agreement})

        if agreement >= threshold:
            converged = True
            break

        if r < max_rounds:
            shared = "\n\n".join(f"[{a['role']}]: {a['output']}" for a in labelled)

            async def reconsider(spec: AgentSpec) -> str:
                return await ask_agent(
                    request,
                    user,
                    spec,
                    f"Task:\n{input_text}\n\nOther agents said:\n{shared}\n\n"
                    "Reconsider and converge toward a shared answer.",
                )

            revised = await asyncio.gather(*[reconsider(s) for s in agents])
            labelled = [{"role": s.role, "output": o} for s, o in zip(agents, revised)]

    return {
        "pattern": "consensus",
        "output": consensus_answer,
        "agreement": agreement,
        "converged": converged,
        "threshold": threshold,
        "history": history,
    }
