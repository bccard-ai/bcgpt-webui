"""Unit tests for the DAG workflow engine, validator, generator, serializer."""

from __future__ import annotations

import asyncio

import pytest

run = asyncio.run

from bcgpt.agent.types import NodeType
from bcgpt.agent.workflow import (
    DynamicWorkflowGenerator,
    ExecutionContext,
    NodeHandlerRegistry,
    WorkflowEngine,
    WorkflowNode,
    WorkflowState,
    deserialize_workflow,
    serialize_workflow,
    validate_workflow,
)
from bcgpt.agent.workflow.nodes import NodeHandler
from bcgpt.agent.workflow.nodes.context_merge import ContextMergeHandler
from bcgpt.agent.workflow.nodes.conditional import ConditionalHandler
from bcgpt.agent.workflow.nodes.response import ResponseHandler
from bcgpt.agent.workflow.nodes.user_input import UserInputHandler
from bcgpt.agent.workflow.state import NodeResult
from bcgpt.agent.workflow.validator import (
    WorkflowValidationError,
    topological_layers,
    topological_sort,
)

GEN = DynamicWorkflowGenerator()


# --- handler stubs ----------------------------------------------------------


class EchoLLM(NodeHandler):
    async def execute(self, node, state, context):
        ctx = f" | ctx:{state.merged_context}" if state.merged_context else ""
        return NodeResult(output=f"ANSWER({state.user_input}){ctx}")


class StubRAG(NodeHandler):
    async def execute(self, node, state, context):
        s = [{"document": "doc-rag", "metadata": {}}]
        return NodeResult(output=s, metadata={"sources": s})


class StubWeb(NodeHandler):
    async def execute(self, node, state, context):
        s = [{"document": "doc-web", "metadata": {"title": "T", "link": "http://x"}}]
        return NodeResult(output=s, metadata={"sources": s})


class Boom(NodeHandler):
    async def execute(self, node, state, context):
        raise RuntimeError("boom")


def make_registry(llm=None):
    reg = NodeHandlerRegistry()
    reg.register(NodeType.USER_INPUT, UserInputHandler())
    reg.register(NodeType.RAG_SEARCH, StubRAG())
    reg.register(NodeType.WEB_SEARCH, StubWeb())
    reg.register(NodeType.CONTEXT_MERGE, ContextMergeHandler())
    reg.register(NodeType.CONDITIONAL, ConditionalHandler())
    reg.register(NodeType.LLM_CALL, llm or EchoLLM())
    reg.register(NodeType.RESPONSE, ResponseHandler())
    return reg


# --- topological sort / validation ------------------------------------------


def _diamond():
    return [
        WorkflowNode("a", NodeType.USER_INPUT, next_nodes=["b", "c"]),
        WorkflowNode("b", NodeType.RAG_SEARCH, next_nodes=["d"]),
        WorkflowNode("c", NodeType.WEB_SEARCH, next_nodes=["d"]),
        WorkflowNode("d", NodeType.RESPONSE),
    ]


def test_topological_sort_orders_sources_first():
    order = [n.id for n in topological_sort(_diamond())]
    assert order[0] == "a" and order[-1] == "d"


def test_topological_layers_groups_independent_nodes():
    layers = [[n.id for n in L] for L in topological_layers(_diamond())]
    assert layers == [["a"], ["b", "c"], ["d"]]


def test_cycle_detected():
    cyc = [
        WorkflowNode("x", NodeType.USER_INPUT, next_nodes=["y"]),
        WorkflowNode("y", NodeType.RESPONSE, next_nodes=["x"]),
    ]
    with pytest.raises(WorkflowValidationError):
        topological_sort(cyc)
    with pytest.raises(WorkflowValidationError):
        validate_workflow(cyc)


def test_dangling_edge_rejected():
    nodes = [WorkflowNode("a", NodeType.USER_INPUT, next_nodes=["missing"])]
    with pytest.raises(WorkflowValidationError):
        validate_workflow(nodes)


def test_duplicate_ids_rejected():
    nodes = [
        WorkflowNode("a", NodeType.USER_INPUT, next_nodes=["a"]),
        WorkflowNode("a", NodeType.RESPONSE),
    ]
    with pytest.raises(WorkflowValidationError):
        validate_workflow(nodes)


# --- generator --------------------------------------------------------------


@pytest.mark.parametrize(
    "level,config",
    [
        ("suggest", {}),
        ("assistant", {}),
        ("assistant", {"rag_enabled": True, "web_search_enabled": True}),
        ("operator", {}),
        ("bogus-defaults-to-assistant", {}),
    ],
)
def test_generated_workflows_are_valid(level, config):
    validate_workflow(GEN.generate(level, config))


def test_assistant_runs_rag_and_web_in_parallel():
    nodes = GEN.generate("assistant", {"rag_enabled": True, "web_search_enabled": True})
    layers = [{n.id for n in L} for L in topological_layers(nodes)]
    assert {"rag", "web"} in layers


def test_operator_enables_tool_loop():
    nodes = GEN.generate("operator", {})
    llm = next(n for n in nodes if n.type == NodeType.LLM_CALL)
    assert llm.config.get("enable_tool_loop") is True


# --- engine end-to-end ------------------------------------------------------


def test_assistant_flow_merges_context_and_answers():
    nodes = GEN.generate("assistant", {"rag_enabled": True, "web_search_enabled": True})
    engine = WorkflowEngine(make_registry())
    state = run(
        engine.execute(nodes, WorkflowState(user_input="hello"), ExecutionContext())
    )
    assert state.status.startswith("completed")
    assert state.final_response.startswith("ANSWER(hello)")
    assert "doc-rag" in (state.merged_context or "")
    assert "doc-web" in (state.merged_context or "")
    assert state.sources


def test_conditional_prunes_unselected_branch():
    nodes = [
        WorkflowNode("in", NodeType.USER_INPUT, next_nodes=["cond"]),
        WorkflowNode(
            "cond",
            NodeType.CONDITIONAL,
            config={
                "branches": [{"when": "len(user_input) > 100", "next": "big"}],
                "default": "small",
            },
            next_nodes=["big", "small"],
        ),
        WorkflowNode("big", NodeType.LLM_CALL, next_nodes=["resp"]),
        WorkflowNode("small", NodeType.LLM_CALL, next_nodes=["resp"]),
        WorkflowNode("resp", NodeType.RESPONSE),
    ]
    engine = WorkflowEngine(make_registry())
    state = run(
        engine.execute(nodes, WorkflowState(user_input="short"), ExecutionContext())
    )
    assert "big" not in state.visited
    assert "small" in state.visited


def test_error_strategy_stop_fails_workflow():
    nodes = GEN.generate("suggest", {})
    engine = WorkflowEngine(make_registry(llm=Boom()))
    state = run(
        engine.execute(nodes, WorkflowState(user_input="x"), ExecutionContext())
    )
    assert state.status == "failed"
    assert "llm" in state.errors


def test_error_strategy_continue_does_not_fail():
    nodes = GEN.generate("suggest", {})
    for n in nodes:
        if n.type == NodeType.LLM_CALL:
            n.config["error_strategy"] = "continue"
    engine = WorkflowEngine(make_registry(llm=Boom()))
    state = run(
        engine.execute(nodes, WorkflowState(user_input="x"), ExecutionContext())
    )
    assert state.status != "failed"


def test_fallback_strategy_substitutes_value():
    nodes = GEN.generate("suggest", {})
    for n in nodes:
        if n.type == NodeType.LLM_CALL:
            n.config["error_strategy"] = "fallback"
            n.config["fallback_value"] = "FALLBACK"
    engine = WorkflowEngine(make_registry(llm=Boom()))
    state = run(
        engine.execute(nodes, WorkflowState(user_input="x"), ExecutionContext())
    )
    assert state.llm_response == "FALLBACK"
    assert state.final_response == "FALLBACK"


# --- serializer -------------------------------------------------------------


def test_serializer_roundtrip():
    nodes = GEN.generate("assistant", {"rag_enabled": True, "web_search_enabled": True})
    data = serialize_workflow(nodes)
    restored = deserialize_workflow(data)
    assert [n.id for n in restored] == [n.id for n in nodes]
    assert [n.type for n in restored] == [n.type for n in nodes]


def test_deserialize_rejects_unknown_type():
    with pytest.raises(WorkflowValidationError):
        deserialize_workflow([{"id": "x", "type": "not_a_node"}])
