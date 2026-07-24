"""Generate workflow graphs from an agent's autonomy level + config.

The generator encodes the 3-Tier design:

  * **suggest**   – USER_INPUT → LLM → RESPONSE (no search, no tools)
  * **assistant** – USER_INPUT → (RAG ∥ WEB) → MERGE → LLM → RESPONSE (default)
  * **operator**  – USER_INPUT → LLM(tool loop) → RESPONSE (ReAct, autonomous)

Edges are wired dynamically so the produced graph is always valid regardless of
which optional features (RAG / web search) are enabled.
"""

from __future__ import annotations

from typing import Optional

from bcgpt.agent.types import AgentAutonomyLevel, NodeType
from bcgpt.agent.workflow.state import WorkflowNode


class DynamicWorkflowGenerator:
    """Builds a list of :class:`WorkflowNode` for a given autonomy level."""

    def generate(
        self,
        autonomy_level: AgentAutonomyLevel | str,
        agent_config: Optional[dict] = None,
    ) -> list[WorkflowNode]:
        level = AgentAutonomyLevel.from_value(
            autonomy_level.value
            if isinstance(autonomy_level, AgentAutonomyLevel)
            else autonomy_level
        )
        config = agent_config or {}

        if level == AgentAutonomyLevel.SUGGEST:
            return self._suggest_workflow(config)
        if level == AgentAutonomyLevel.OPERATOR:
            return self._operator_workflow(config)
        return self._assistant_workflow(config)

    # -- suggest -------------------------------------------------------------

    def _suggest_workflow(self, config: dict) -> list[WorkflowNode]:
        return [
            WorkflowNode(id="input", type=NodeType.USER_INPUT, next_nodes=["llm"]),
            WorkflowNode(
                id="llm",
                type=NodeType.LLM_CALL,
                config={"model_id": config.get("model_id")},
                next_nodes=["response"],
            ),
            WorkflowNode(id="response", type=NodeType.RESPONSE),
        ]

    # -- assistant (default) -------------------------------------------------

    def _assistant_workflow(self, config: dict) -> list[WorkflowNode]:
        rag_enabled = bool(config.get("rag_enabled"))
        web_enabled = bool(config.get("web_search_enabled"))

        search_nodes: list[WorkflowNode] = []
        if rag_enabled:
            search_nodes.append(
                WorkflowNode(
                    id="rag",
                    type=NodeType.RAG_SEARCH,
                    config={
                        "collection_ids": config.get("collection_ids", []),
                        "top_k": config.get("top_k", 5),
                        "hybrid": config.get("hybrid_search", False),
                        "error_strategy": "continue",
                    },
                    next_nodes=["merge"],
                )
            )
        if web_enabled:
            search_nodes.append(
                WorkflowNode(
                    id="web",
                    type=NodeType.WEB_SEARCH,
                    config={
                        "engine": config.get("web_search_engine"),
                        "top_k": config.get("web_top_k", 5),
                        "error_strategy": "continue",
                    },
                    next_nodes=["merge"],
                )
            )

        if search_nodes:
            input_next = [n.id for n in search_nodes]
            nodes = [
                WorkflowNode(
                    id="input", type=NodeType.USER_INPUT, next_nodes=input_next
                ),
                *search_nodes,
                WorkflowNode(
                    id="merge", type=NodeType.CONTEXT_MERGE, next_nodes=["llm"]
                ),
                WorkflowNode(
                    id="llm",
                    type=NodeType.LLM_CALL,
                    config={"model_id": config.get("model_id"), "use_context": True},
                    next_nodes=["response"],
                ),
                WorkflowNode(id="response", type=NodeType.RESPONSE),
            ]
            return nodes

        # No search features enabled → behaves like suggest but keeps the
        # assistant label (still a single LLM call).
        return self._suggest_workflow(config)

    # -- operator (autonomous ReAct) ----------------------------------------

    def _operator_workflow(self, config: dict) -> list[WorkflowNode]:
        tools = config.get("tools") or ["rag_search", "web_search"]
        return [
            WorkflowNode(id="input", type=NodeType.USER_INPUT, next_nodes=["llm"]),
            WorkflowNode(
                id="llm",
                type=NodeType.LLM_CALL,
                config={
                    "model_id": config.get("model_id"),
                    "enable_tool_loop": True,
                    "tools": tools,
                    "max_iterations": config.get("max_iterations", 10),
                    "collection_ids": config.get("collection_ids", []),
                },
                next_nodes=["response"],
            ),
            WorkflowNode(id="response", type=NodeType.RESPONSE),
        ]
