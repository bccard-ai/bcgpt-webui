"""CONDITIONAL node: branch selection (if-else / switch).

Config shape::

    {
      "branches": [
        {"when": "<expr>", "next": "<node_id>"},
        ...
      ],
      "default": "<node_id>"      # optional; taken if no branch matches
    }

``when`` is a restricted boolean expression evaluated against a small, safe
namespace exposing the workflow state (``rag_results``, ``web_results``,
``user_input``, ``llm_response``, ``vars``, and helpers ``len``/``bool``). It
must reference only those names — anything else evaluates to ``False``.

The handler returns ``metadata["selected_next"]`` (the chosen successor ids);
the engine deactivates edges to the non-selected successors and prunes any
nodes that thereby become unreachable.
"""

from __future__ import annotations

import json
import logging
import re

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

log = logging.getLogger(__name__)

# Block attempts to access dunder attributes (e.g., __class__, __bases__)
_DUNDER_PATTERN = re.compile(r"__\w+__")

# Whole-word forbidden call tokens. Word boundaries (rather than a naive
# substring check) avoid over-blocking benign words that merely contain a token
# (e.g. "important", "evaluate", "opened") while still rejecting the dangerous
# call when it appears as an identifier. This is defense-in-depth on top of the
# __builtins__ allow-list and dunder block, which are the primary defenses.
_FORBIDDEN_TOKENS_RE = re.compile(
    r"\b(?:import|exec|eval|compile|open|getattr|setattr|delattr)\b"
)


def _is_expression_safe(expr: str) -> bool:
    """Check if an expression is safe to evaluate."""
    if _DUNDER_PATTERN.search(expr):
        return False
    if _FORBIDDEN_TOKENS_RE.search(expr):
        return False
    return True


def _sanitize_namespace(data: dict) -> dict:
    """Convert namespace values to JSON-safe primitives."""
    sanitized = {}
    for key, value in data.items():
        try:
            json.dumps(value)
            sanitized[key] = value
        except (TypeError, ValueError):
            sanitized[key] = str(value)
    return sanitized


_ALLOWED_BUILTINS = {
    "len": len,
    "bool": bool,
    "min": min,
    "max": max,
    "any": any,
    "all": all,
}


def _safe_eval(expr: str, state: WorkflowState) -> bool:
    if not _is_expression_safe(expr):
        log.warning("CONDITIONAL expr blocked by safety check: %r", expr)
        return False

    namespace = {
        "rag_results": state.rag_results or [],
        "web_results": state.web_results or [],
        "sources": state.sources or [],
        "user_input": state.user_input or "",
        "llm_response": state.llm_response or "",
        "vars": state.variables,
    }
    namespace = _sanitize_namespace(namespace)
    try:
        return bool(
            eval(expr, {"__builtins__": _ALLOWED_BUILTINS}, namespace)
        )  # noqa: S307
    except Exception as e:  # noqa: BLE001 - condition errors → False
        log.warning("CONDITIONAL expr %r failed: %s", expr, e)
        return False


class ConditionalHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        branches = node.config.get("branches") or []
        default = node.config.get("default")

        selected: list[str] = []
        for branch in branches:
            expr = branch.get("when")
            target = branch.get("next")
            if target and expr and _safe_eval(expr, state):
                selected.append(target)
                if not node.config.get("multi", False):
                    break

        if not selected and default:
            selected = [default]

        # Only keep targets that are real successors of this node.
        valid = [t for t in selected if t in node.next_nodes]
        return NodeResult(
            output={"selected": valid},
            metadata={"selected_next": valid},
        )
