"""PII_PROCESSOR node: detect and mask personal data.

Regex-based masking of common PII (email, phone, credit-card-like numbers,
US SSN-like patterns, IPv4). Operates on a configurable ``target`` field
(default ``llm_response``) and writes the masked text back onto that field via
``state_updates`` so the downstream RESPONSE node emits the sanitised text.

Detection is best-effort, not a compliance guarantee — intended as a guardrail
layer, mirroring Open-MoAI's PII node.
"""

from __future__ import annotations

import re

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

_PATTERNS: dict[str, re.Pattern] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,16}\b"),
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone": re.compile(r"\b(?:\+?\d{1,3}[ -]?)?(?:\(?\d{2,4}\)?[ -]?){2,4}\d{2,4}\b"),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_MASK = "[REDACTED:{kind}]"


def _mask(text: str, kinds: list[str]) -> tuple[str, dict[str, int]]:
    counts: dict[str, int] = {}
    out = text
    for kind in kinds:
        pattern = _PATTERNS.get(kind)
        if not pattern:
            continue
        found = pattern.findall(out)
        if found:
            counts[kind] = counts.get(kind, 0) + len(found)
            out = pattern.sub(_MASK.format(kind=kind), out)
    return out, counts


class PIIProcessorHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        target = node.config.get("target", "llm_response")
        kinds = node.config.get("kinds") or list(_PATTERNS.keys())

        text = getattr(state, target, None)
        if not isinstance(text, str) or not text:
            return NodeResult(output=text, metadata={"masked": {}, "skipped": True})

        masked, counts = _mask(text, kinds)
        return NodeResult(
            output=masked,
            metadata={"masked": counts, "state_updates": {target: masked}},
        )
