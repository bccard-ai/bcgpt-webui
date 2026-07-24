"""BCGPT Agent subsystem.

Implements the Open-MoAI architecture patterns adapted for BCGPT-WebUI:

  - 3-Tier agent autonomy (suggest / assistant / operator)         [types, config]
  - DAG workflow engine (10 node types + registry + generator)     [workflow/]
  - Dynamic ReAct tool loop (provider-agnostic)                    [tool_loop/]
  - Quality control pipeline (claim / grounding / grading)         [quality/]
  - Multi-agent coordination (sequential/parallel/debate/...)      [multi_agent/]
  - Agent & skill definition import/export (YAML frontmatter + MD) [definitions/]

The whole package is *additive* and opt-in: the existing chat flow in
``utils/middleware.py`` is untouched. Agents default to ``assistant`` autonomy
(pre-search → LLM → response), preserving zero-regression behaviour. ``operator``
(autonomous ReAct tool loop) must be explicitly enabled per model.
"""

from bcgpt.agent.types import (
    AgentAutonomyLevel,
    AgentType,
    ErrorStrategy,
    MultiAgentPattern,
    NodeType,
)

__all__ = [
    "AgentAutonomyLevel",
    "AgentType",
    "ErrorStrategy",
    "MultiAgentPattern",
    "NodeType",
]
