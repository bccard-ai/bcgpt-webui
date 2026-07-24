"""TEXT_PROCESSOR node: deterministic text transformations.

Config ``operation`` selects the transform:

  * ``template``    – ``format`` with state fields ({user_input}, {llm_response},
                      {merged_context}) and ``config.vars``.
  * ``replace``     – regex ``pattern`` → ``repl``.
  * ``truncate``    – cap to ``max_chars``.
  * ``lower`` / ``upper`` / ``strip``.
  * ``extract_json`` – pull the first JSON object/array out of the input text.

The ``source`` config (default ``llm_response`` then ``user_input``) chooses the
input field. Output is written to ``node_outputs``; set ``write_to`` to also
mirror it onto a state field (e.g. ``llm_response``).
"""

from __future__ import annotations

import json
import re

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)


def _source_text(node: WorkflowNode, state: WorkflowState) -> str:
    src = node.config.get("source")
    if src:
        val = getattr(state, src, None)
        if val is None:
            val = state.variables.get(src)
        return val if isinstance(val, str) else ("" if val is None else str(val))
    return state.llm_response or state.user_input or ""


def _extract_json(text: str):
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                continue
    return None


class TextProcessorHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        op = (node.config.get("operation") or "template").lower()
        text = _source_text(node, state)
        out = text

        if op == "template":
            template = node.config.get("template", "{input}")
            fields = {
                "input": text,
                "user_input": state.user_input or "",
                "llm_response": state.llm_response or "",
                "merged_context": state.merged_context or "",
                **(node.config.get("vars") or {}),
            }
            try:
                out = template.format(**fields)
            except (KeyError, IndexError):
                out = template
        elif op == "replace":
            pattern = node.config.get("pattern", "")
            repl = node.config.get("repl", "")
            out = re.sub(pattern, repl, text) if pattern else text
        elif op == "truncate":
            max_chars = int(node.config.get("max_chars", 2000))
            out = text[:max_chars]
        elif op == "lower":
            out = text.lower()
        elif op == "upper":
            out = text.upper()
        elif op == "strip":
            out = text.strip()
        elif op == "extract_json":
            out = _extract_json(text)

        metadata: dict = {"operation": op}
        write_to = node.config.get("write_to")
        if write_to:
            metadata["state_updates"] = {write_to: out}
        return NodeResult(output=out, metadata=metadata)
