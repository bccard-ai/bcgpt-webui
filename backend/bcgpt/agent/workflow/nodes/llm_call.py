"""LLM_CALL node: invoke the model, optionally via the ReAct tool loop.

* **assistant / suggest** – single completion. If a merged context exists it is
  injected as a system message (grounded answering).
* **operator** – ``config.enable_tool_loop`` runs the provider-agnostic ReAct
  loop so the model can call ``rag_search`` / ``web_search`` autonomously.
"""

from __future__ import annotations

import logging

from bcgpt.agent.llm import extract_content, llm_complete
from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

log = logging.getLogger(__name__)

_CONTEXT_TEMPLATE = (
    "Use the following retrieved context to answer the user's question. "
    "Cite sources with [n] markers where relevant. If the context is "
    "insufficient, say so.\n\n<context>\n{context}\n</context>"
)


def _build_messages(node: WorkflowNode, state: WorkflowState) -> list[dict]:
    messages: list[dict] = []

    system_parts: list[str] = []
    base_system = node.config.get("system_prompt")
    if base_system:
        system_parts.append(base_system)
    if node.config.get("use_context") and state.merged_context:
        system_parts.append(_CONTEXT_TEMPLATE.format(context=state.merged_context))
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    if state.messages:
        # Drop any pre-existing system message; we supply our own above.
        messages.extend([m for m in state.messages if m.get("role") != "system"])
    elif state.user_input:
        messages.append({"role": "user", "content": state.user_input})

    return messages


class LLMCallHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        model_id = node.config.get("model_id") or context.model_id
        if not model_id or context.request is None:
            raise RuntimeError("LLM_CALL requires a model_id and request context")

        messages = _build_messages(node, state)
        params = {**(context.params or {}), **(node.config.get("params") or {})}

        if node.config.get("enable_tool_loop"):
            from bcgpt.agent.tool_loop import ReactToolLoop
            from bcgpt.agent.tool_loop.tools import resolve_tools

            tools = resolve_tools(node.config.get("tools") or [])
            loop = ReactToolLoop(
                request=context.request,
                user=context.user,
                model_id=model_id,
                tools=tools,
                max_iterations=int(node.config.get("max_iterations", 10)),
                params=params,
                node_config=node.config,
                approval_gate=context.approval_gate,
            )
            loop_result = await loop.run(messages, event_emitter=context.event_emitter)
            return NodeResult(
                output=loop_result.content,
                metadata={
                    "iterations": loop_result.iterations,
                    "tool_calls": loop_result.tool_call_log,
                    "sources": loop_result.sources,
                },
            )

        resp = await llm_complete(
            context.request, context.user, model_id, messages, params=params
        )
        content = extract_content(resp)
        return NodeResult(
            output=content,
            metadata={"usage": resp.get("usage", {})},
        )
