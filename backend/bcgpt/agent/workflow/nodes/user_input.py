"""USER_INPUT node: the workflow entry point.

Normalises the incoming user message. If ``state.user_input`` is empty it falls
back to the last user message in ``state.messages``.
"""

from __future__ import annotations

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)


class UserInputHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        text = state.user_input
        if not text and state.messages:
            for msg in reversed(state.messages):
                if msg.get("role") == "user":
                    content = msg.get("content")
                    text = content if isinstance(content, str) else str(content)
                    break
        return NodeResult(output=text, metadata={"length": len(text or "")})
