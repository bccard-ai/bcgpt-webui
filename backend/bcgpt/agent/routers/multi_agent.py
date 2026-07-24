"""Multi-agent coordination endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.agent.multi_agent import MultiAgentExecutor
from bcgpt.agent.types import MultiAgentPattern
from bcgpt.utils.auth import get_verified_user

log = logging.getLogger(__name__)
router = APIRouter()

_EXECUTOR = MultiAgentExecutor()


@router.get("/patterns")
async def list_patterns(user=Depends(get_verified_user)):
    descriptions = {
        "sequential": "A → B → C; each agent refines the previous output.",
        "parallel": "All agents answer concurrently; optional aggregation.",
        "debate": "Agents critique each other over rounds, then synthesise.",
        "consensus": "Iterate until agreement passes a threshold.",
        "voting": "Agents answer; a judge tallies the majority.",
        "moa": "Mixture of Agents: proposers draft, an aggregator synthesises.",
    }
    return {
        "patterns": [
            {"value": p.value, "description": descriptions.get(p.value, "")}
            for p in MultiAgentPattern
        ]
    }


class MultiAgentForm(BaseModel):
    pattern: str
    agents: (
        list  # [{"model_id": str, "role": str, "system_prompt"?: str, "params"?: {}}]
    )
    input: str
    config: dict = {}


@router.post("/completions")
async def multi_agent_completions(
    form: MultiAgentForm, request: Request, user=Depends(get_verified_user)
):
    from bcgpt.agent.config import (
        MULTI_AGENT_DEBATE_ROUNDS,
        MULTI_AGENT_ENABLED,
        MULTI_AGENT_MAX_PARALLEL,
    )

    if not bool(MULTI_AGENT_ENABLED.value):
        raise HTTPException(
            status_code=403,
            detail="Multi-agent execution is disabled (set MULTI_AGENT_ENABLED).",
        )

    try:
        pattern = MultiAgentPattern.from_value(form.pattern)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown pattern: {form.pattern}")

    # Apply server-side defaults/caps from config.
    config = dict(form.config or {})
    config.setdefault("rounds", int(MULTI_AGENT_DEBATE_ROUNDS.value))
    config["max_parallel"] = min(
        int(config.get("max_parallel", MULTI_AGENT_MAX_PARALLEL.value)),
        int(MULTI_AGENT_MAX_PARALLEL.value),
    )

    try:
        result = await _EXECUTOR.execute(
            request, user, pattern, form.agents, form.input, config
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        log.exception("multi-agent execution failed")
        raise HTTPException(status_code=500, detail=f"Execution error: {e}")
    return result
