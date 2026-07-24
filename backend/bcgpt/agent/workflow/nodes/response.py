"""RESPONSE node: format the final answer.

Reads the LLM response (or a configured ``source`` field) and, when
``include_citations`` is set and a ``source_mapping`` exists, appends a numbered
sources list. Its output becomes ``state.final_response``.
"""

from __future__ import annotations

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)


class ResponseHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        source = node.config.get("source", "llm_response")
        content = getattr(state, source, None)
        if not isinstance(content, str):
            content = state.llm_response or ""

        if node.config.get("include_citations") and state.source_mapping:
            lines = ["", "---", "**Sources:**"]
            for idx, meta in sorted(
                state.source_mapping.items(), key=lambda kv: int(kv[0])
            ):
                title = meta.get("title") or meta.get("link") or f"Source {idx}"
                link = meta.get("link")
                lines.append(f"[{idx}] {title}" + (f" — {link}" if link else ""))
            content = content + "\n" + "\n".join(lines)

        return NodeResult(output=content, metadata={"length": len(content or "")})
