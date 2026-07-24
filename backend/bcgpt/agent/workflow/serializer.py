"""JSON (de)serialisation for workflow graphs.

Lets a custom per-agent workflow be stored in ``Model.meta`` (or a dedicated
table) and round-tripped through the API. The wire format is a list of node
objects::

    [
      {"id": "input", "type": "user_input", "config": {}, "next_nodes": ["llm"]},
      {"id": "llm",   "type": "llm_call",  "config": {...}, "next_nodes": ["response"]},
      {"id": "response", "type": "response", "config": {}, "next_nodes": []}
    ]
"""

from __future__ import annotations

from bcgpt.agent.types import NodeType
from bcgpt.agent.workflow.state import WorkflowNode
from bcgpt.agent.workflow.validator import KNOWN_NODE_TYPES, WorkflowValidationError


def serialize_workflow(nodes: list[WorkflowNode]) -> list[dict]:
    return [
        {
            "id": n.id,
            "type": n.type.value,
            "config": n.config or {},
            "next_nodes": list(n.next_nodes or []),
        }
        for n in nodes
    ]


def deserialize_workflow(data: list[dict]) -> list[WorkflowNode]:
    if not isinstance(data, list):
        raise WorkflowValidationError("Workflow must be a list of node objects")

    nodes: list[WorkflowNode] = []
    for i, raw in enumerate(data):
        if not isinstance(raw, dict):
            raise WorkflowValidationError(f"Node #{i} is not an object")
        nid = raw.get("id")
        ntype = raw.get("type")
        if not nid:
            raise WorkflowValidationError(f"Node #{i} is missing 'id'")
        if ntype not in KNOWN_NODE_TYPES:
            raise WorkflowValidationError(
                f"Node {nid!r} has unknown type {ntype!r}; "
                f"expected one of {sorted(KNOWN_NODE_TYPES)}"
            )
        nodes.append(
            WorkflowNode(
                id=str(nid),
                type=NodeType.from_value(ntype),
                config=raw.get("config") or {},
                next_nodes=list(raw.get("next_nodes") or []),
            )
        )
    return nodes
