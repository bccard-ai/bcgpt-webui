"""DAG validation and topological sorting.

Pure functions over a list of :class:`WorkflowNode` — no I/O, no external deps.
"""

from __future__ import annotations

from bcgpt.agent.types import NodeType
from bcgpt.agent.workflow.state import WorkflowNode


class WorkflowValidationError(ValueError):
    """Raised when a workflow graph is structurally invalid."""


def validate_workflow(nodes: list[WorkflowNode]) -> None:
    """Validate structural integrity of a workflow graph.

    Checks: non-empty, unique ids, edges point to existing nodes, no cycles,
    exactly the expected entry/terminal shape (at least one source and one
    sink, where a sink is typically a RESPONSE node). Raises
    :class:`WorkflowValidationError` on the first problem found.
    """
    if not nodes:
        raise WorkflowValidationError("Workflow has no nodes")

    ids = [n.id for n in nodes]
    seen: set[str] = set()
    for nid in ids:
        if not nid:
            raise WorkflowValidationError("A node has an empty id")
        if nid in seen:
            raise WorkflowValidationError(f"Duplicate node id: {nid!r}")
        seen.add(nid)

    id_set = set(ids)
    for node in nodes:
        for nxt in node.next_nodes:
            if nxt not in id_set:
                raise WorkflowValidationError(
                    f"Node {node.id!r} points to unknown node {nxt!r}"
                )
            if nxt == node.id:
                raise WorkflowValidationError(f"Node {node.id!r} links to itself")

    # Cycle detection happens inside topological_sort.
    order = topological_sort(nodes)
    if len(order) != len(nodes):  # pragma: no cover - topo_sort raises first
        raise WorkflowValidationError("Workflow contains a cycle")

    # Soft structural expectations (warn-by-raise only on clearly broken graphs).
    indeg = _in_degrees(nodes)
    sources = [n for n in nodes if indeg[n.id] == 0]
    if not sources:
        raise WorkflowValidationError("Workflow has no entry node (cycle?)")

    sinks = [n for n in nodes if not n.next_nodes]
    if not sinks:
        raise WorkflowValidationError("Workflow has no terminal node")


def _in_degrees(nodes: list[WorkflowNode]) -> dict[str, int]:
    indeg = {n.id: 0 for n in nodes}
    for node in nodes:
        for nxt in node.next_nodes:
            if nxt in indeg:
                indeg[nxt] += 1
    return indeg


def topological_sort(nodes: list[WorkflowNode]) -> list[WorkflowNode]:
    """Kahn's algorithm. Raises :class:`WorkflowValidationError` on a cycle.

    Ties are broken by the node's original position to keep ordering stable and
    deterministic (important for reproducible execution and tests).
    """
    node_map = {n.id: n for n in nodes}
    order_index = {n.id: i for i, n in enumerate(nodes)}
    indeg = _in_degrees(nodes)

    queue = sorted(
        [nid for nid, deg in indeg.items() if deg == 0],
        key=lambda nid: order_index[nid],
    )
    result: list[WorkflowNode] = []

    while queue:
        nid = queue.pop(0)
        result.append(node_map[nid])
        new_ready: list[str] = []
        for nxt in node_map[nid].next_nodes:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                new_ready.append(nxt)
        if new_ready:
            queue.extend(new_ready)
            queue.sort(key=lambda nid: order_index[nid])

    if len(result) != len(nodes):
        remaining = sorted(set(node_map) - {n.id for n in result})
        raise WorkflowValidationError(
            f"Workflow contains a cycle involving: {', '.join(remaining)}"
        )
    return result


def topological_layers(nodes: list[WorkflowNode]) -> list[list[WorkflowNode]]:
    """Group nodes into dependency layers (Kahn by level).

    All nodes in layer *i* depend only on nodes in layers ``< i``, so a layer's
    nodes are mutually independent and may be executed concurrently. Within a
    layer, nodes keep their original relative order for determinism.

    Raises :class:`WorkflowValidationError` on a cycle.
    """
    node_map = {n.id: n for n in nodes}
    order_index = {n.id: i for i, n in enumerate(nodes)}
    indeg = _in_degrees(nodes)

    current = sorted(
        [nid for nid, deg in indeg.items() if deg == 0],
        key=lambda nid: order_index[nid],
    )
    layers: list[list[WorkflowNode]] = []
    processed = 0

    while current:
        layers.append([node_map[nid] for nid in current])
        nxt_ready: list[str] = []
        for nid in current:
            processed += 1
            for nxt in node_map[nid].next_nodes:
                indeg[nxt] -= 1
                if indeg[nxt] == 0:
                    nxt_ready.append(nxt)
        current = sorted(nxt_ready, key=lambda nid: order_index[nid])

    if processed != len(nodes):
        remaining = sorted(set(node_map) - {n.id for layer in layers for n in layer})
        raise WorkflowValidationError(
            f"Workflow contains a cycle involving: {', '.join(remaining)}"
        )
    return layers


# A small allow-list so the serializer/validator can reject unknown node types
# early with a clear message.
KNOWN_NODE_TYPES = {t.value for t in NodeType}
