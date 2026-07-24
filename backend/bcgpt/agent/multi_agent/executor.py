"""MultiAgentExecutor: routes a coordination request to the right pattern."""

from __future__ import annotations

from typing import Any, Optional

from bcgpt.agent.types import MultiAgentPattern
from bcgpt.agent.multi_agent.base import parse_agents
from bcgpt.agent.multi_agent.consensus import execute_consensus
from bcgpt.agent.multi_agent.debate import execute_debate
from bcgpt.agent.multi_agent.moa import execute_moa
from bcgpt.agent.multi_agent.parallel import execute_parallel
from bcgpt.agent.multi_agent.sequential import execute_sequential
from bcgpt.agent.multi_agent.voting import execute_voting
from bcgpt.agent.multi_agent.council import execute_council

_DISPATCH = {
    MultiAgentPattern.SEQUENTIAL: execute_sequential,
    MultiAgentPattern.PARALLEL: execute_parallel,
    MultiAgentPattern.DEBATE: execute_debate,
    MultiAgentPattern.CONSENSUS: execute_consensus,
    MultiAgentPattern.VOTING: execute_voting,
    MultiAgentPattern.MOA: execute_moa,
    MultiAgentPattern.COUNCIL: execute_council,
}


class MultiAgentExecutor:
    """Validates input and dispatches to the chosen multi-agent pattern."""

    async def execute(
        self,
        request: Any,
        user: Any,
        pattern: MultiAgentPattern | str,
        agents: list[dict],
        input_text: str,
        config: Optional[dict] = None,
    ) -> dict:
        pat = (
            pattern
            if isinstance(pattern, MultiAgentPattern)
            else MultiAgentPattern.from_value(pattern)
        )
        specs = parse_agents(agents)
        handler = _DISPATCH.get(pat)
        if handler is None:  # pragma: no cover - from_value already validates
            raise ValueError(f"Unknown multi-agent pattern: {pattern}")
        return await handler(request, user, specs, input_text, config or {})

    @staticmethod
    def patterns() -> list[str]:
        return [p.value for p in MultiAgentPattern]
