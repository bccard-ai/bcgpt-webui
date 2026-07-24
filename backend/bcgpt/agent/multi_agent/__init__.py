"""Multi-agent coordination (5+ patterns).

Generalises the single MOA endpoint into a unified executor supporting
Sequential, Parallel, Debate, Consensus, Voting, and MoA patterns.
"""

from bcgpt.agent.multi_agent.base import AgentSpec, ask_agent, parse_agents
from bcgpt.agent.multi_agent.executor import MultiAgentExecutor

__all__ = [
    "MultiAgentExecutor",
    "AgentSpec",
    "ask_agent",
    "parse_agents",
]
