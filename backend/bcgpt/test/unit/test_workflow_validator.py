"""Tests for workflow DAG validation / topological ordering (``agent/workflow/validator.py``).

The validator is what prevents a crafted or buggy workflow graph from sending the
engine into an infinite loop (cycle), executing a dangling edge, or running nodes in a
wrong order. It is pure (graph algorithm over ``WorkflowNode``), so it is exercised
directly. Reviewed correct (iter-77); locked here.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_workflow_validator.py -q
"""

from __future__ import annotations

import pytest

from bcgpt.agent.workflow.state import WorkflowNode
from bcgpt.agent.workflow.validator import (
    WorkflowValidationError,
    topological_layers,
    topological_sort,
    validate_workflow,
)


def N(i: str, nxt: list[str]) -> WorkflowNode:
    return WorkflowNode(id=i, type="llm_call", config={}, next_nodes=nxt)


# ---------------------------------------------------------------------------
# validate_workflow -- structural integrity
# ---------------------------------------------------------------------------


def test_valid_chain_passes():
    validate_workflow([N("A", ["B"]), N("B", ["C"]), N("C", [])])  # no raise


def test_single_node_passes():
    validate_workflow([N("only", [])])


def test_empty_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([])


def test_duplicate_id_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([N("A", []), N("A", [])])


def test_dangling_edge_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([N("A", ["does_not_exist"])])


def test_self_loop_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([N("A", ["A"])])


def test_two_node_cycle_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([N("A", ["B"]), N("B", ["A"])])


def test_three_node_cycle_rejected():
    with pytest.raises(WorkflowValidationError):
        validate_workflow([N("A", ["B"]), N("B", ["C"]), N("C", ["A"])])


# ---------------------------------------------------------------------------
# topological_sort
# ---------------------------------------------------------------------------


def test_topo_sort_chain_order():
    order = [n.id for n in topological_sort([N("A", ["B"]), N("B", ["C"]), N("C", [])])]
    assert order == ["A", "B", "C"]


def test_topo_sort_cycle_raises():
    with pytest.raises(WorkflowValidationError):
        topological_sort([N("A", ["B"]), N("B", ["A"])])


def test_topo_sort_stable_tiebreak_by_input_index():
    # Independent nodes keep their input order on ties (deterministic execution).
    nodes = [N("B", ["C"]), N("A", ["C"]), N("C", [])]  # B before A in input
    order = [n.id for n in topological_sort(nodes)]
    assert order == ["B", "A", "C"]


# ---------------------------------------------------------------------------
# topological_layers -- parallel grouping for the engine
# ---------------------------------------------------------------------------


def test_layers_diamond_parallel_middle():
    # A -> {B, C} -> D : B and C are independent and share a layer.
    layers = [
        [n.id for n in L]
        for L in topological_layers(
            [N("A", ["B", "C"]), N("B", ["D"]), N("C", ["D"]), N("D", [])]
        )
    ]
    assert layers[0] == ["A"]
    assert set(layers[1]) == {"B", "C"}
    assert layers[2] == ["D"]


def test_layers_cycle_raises():
    with pytest.raises(WorkflowValidationError):
        topological_layers([N("A", ["B"]), N("B", ["A"])])


def test_layers_independent_roots_share_first_layer():
    layers = [
        [n.id for n in L]
        for L in topological_layers([N("x", []), N("y", []), N("z", [])])
    ]
    assert len(layers) == 1
    assert set(layers[0]) == {"x", "y", "z"}
