"""The DAG workflow execution engine.

Execution model (mirrors the Open-MoAI engine, Section 4 / pattern 2):

  1. **Validation**   – reject empty graphs, dangling edges, cycles.
  2. **Resolution**   – look up each node's handler in the registry.
  3. **Execution**    – run nodes in topological *layers*. Independent nodes in
     the same layer (e.g. RAG_SEARCH ∥ WEB_SEARCH) run concurrently.
  4. **Error handling** – per-node strategy: stop / continue / retry / fallback.
  5. **Result compilation** – outputs written to ``state.node_outputs`` and
     mapped to typed state fields; sources accumulated.

Concurrency contract: handlers **read** from ``state``/``context`` and **return**
a :class:`NodeResult`; they must not mutate ``state`` directly. The engine
applies results after each layer (in deterministic node order), which keeps
concurrent sibling nodes race-free.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from bcgpt.agent.types import ErrorStrategy, NodeType
from bcgpt.agent.workflow.registry import NodeHandlerRegistry
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)
from bcgpt.agent.workflow.validator import topological_layers, validate_workflow

log = logging.getLogger(__name__)


# Maps a node type to the typed ``WorkflowState`` attribute its output feeds.
_OUTPUT_FIELD: dict[NodeType, str] = {
    NodeType.RAG_SEARCH: "rag_results",
    NodeType.WEB_SEARCH: "web_results",
    NodeType.CONTEXT_MERGE: "merged_context",
    NodeType.LLM_CALL: "llm_response",
    NodeType.RESPONSE: "final_response",
}


class WorkflowEngine:
    """Executes a workflow DAG against a mutable :class:`WorkflowState`."""

    def __init__(
        self,
        registry: NodeHandlerRegistry,
        *,
        node_timeout: Optional[float] = None,
        concurrent: bool = True,
    ) -> None:
        self.registry = registry
        self.node_timeout = node_timeout
        self.concurrent = concurrent

    async def execute(
        self,
        nodes: list[WorkflowNode],
        state: WorkflowState,
        context: Optional[ExecutionContext] = None,
    ) -> WorkflowState:
        context = context or ExecutionContext()
        validate_workflow(nodes)

        layers = topological_layers(nodes)

        # Conditional branch pruning state.
        preds = self._predecessors(nodes)
        active_edge: dict[tuple[str, str], bool] = {
            (n.id, nxt): True for n in nodes for nxt in n.next_nodes
        }
        skipped: set[str] = set()

        for layer in layers:
            # Determine which nodes in this layer are still reachable. A
            # non-source node is reachable iff at least one incoming edge is
            # active and its predecessor was not skipped.
            runnable: list[WorkflowNode] = []
            for node in layer:
                node_preds = preds.get(node.id, [])
                if node_preds:
                    reachable = any(
                        active_edge.get((p, node.id), False) and p not in skipped
                        for p in node_preds
                    )
                    if not reachable:
                        skipped.add(node.id)
                        continue
                runnable.append(node)

            if self.concurrent and len(runnable) > 1:
                results = await asyncio.gather(
                    *[self._run_node(n, state, context) for n in runnable]
                )
            else:
                results = [await self._run_node(n, state, context) for n in runnable]

            # Apply results in deterministic order; honour error strategies.
            for node, result in zip(runnable, results):
                state.visited.append(node.id)
                strategy = node.error_strategy

                # Conditional nodes deactivate edges to non-selected successors.
                selected_next = (result.metadata or {}).get("selected_next")
                if selected_next is not None:
                    for nxt in node.next_nodes:
                        if nxt not in selected_next:
                            active_edge[(node.id, nxt)] = False

                if result.error is not None:
                    if strategy == ErrorStrategy.CONTINUE:
                        state.errors[node.id] = result.error
                        log.warning(
                            "workflow node %s failed (continue): %s",
                            node.id,
                            result.error,
                        )
                        continue
                    if strategy == ErrorStrategy.FALLBACK:
                        fallback = node.config.get("fallback_value")
                        self._apply_output(node, fallback, {}, state)
                        log.warning(
                            "workflow node %s failed, using fallback: %s",
                            node.id,
                            result.error,
                        )
                        continue
                    # STOP / RETRY-exhausted → fail the workflow.
                    state.errors[node.id] = result.error
                    state.status = "failed"
                    log.error(
                        "workflow node %s failed (stop): %s", node.id, result.error
                    )
                    return state

                self._apply_output(node, result.output, result.metadata, state)

        state.status = "completed" if not state.errors else "completed_with_errors"
        return state

    @staticmethod
    def _predecessors(nodes: list[WorkflowNode]) -> dict[str, list[str]]:
        preds: dict[str, list[str]] = {n.id: [] for n in nodes}
        for n in nodes:
            for nxt in n.next_nodes:
                if nxt in preds:
                    preds[nxt].append(n.id)
        return preds

    async def _run_node(
        self,
        node: WorkflowNode,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> NodeResult:
        handler = self.registry.get(node.type)
        if handler is None:
            return NodeResult(
                error=ValueError(f"No handler registered for {node.type}")
            )

        if context.approval_gate is not None:
            decision = await context.approval_gate(
                {
                    "scope": "workflow_node",
                    "node_id": node.id,
                    "node_type": node.type.value,
                    "tool_name": node.config.get("tool_name", ""),
                    "arguments": node.config,
                }
            )
            if not decision.get("approved", False):
                return NodeResult(
                    error=PermissionError(decision.get("reason", "approval denied")),
                    metadata={"approval": decision},
                )

        timeout = node.config.get("timeout", self.node_timeout)
        attempts = node.max_retries if node.error_strategy == ErrorStrategy.RETRY else 1
        attempts = max(1, attempts)

        last_error: Optional[Exception] = None
        for attempt in range(attempts):
            try:
                await context.emit(
                    {
                        "type": "workflow:node",
                        "data": {"id": node.id, "status": "running"},
                    }
                )
                coro = handler.execute(node, state, context)
                if timeout:
                    result = await asyncio.wait_for(coro, timeout=float(timeout))
                else:
                    result = await coro
                if not isinstance(result, NodeResult):
                    result = NodeResult(output=result)
                await context.emit(
                    {"type": "workflow:node", "data": {"id": node.id, "status": "done"}}
                )
                return result
            except asyncio.TimeoutError:
                last_error = TimeoutError(f"node {node.id} timed out after {timeout}s")
                log.warning(
                    "workflow node %s timed out (attempt %d)", node.id, attempt + 1
                )
            except Exception as e:  # noqa: BLE001 - engine boundary
                last_error = e
                log.warning(
                    "workflow node %s raised (attempt %d): %s", node.id, attempt + 1, e
                )

        return NodeResult(error=last_error or RuntimeError(f"node {node.id} failed"))

    @staticmethod
    def _apply_output(
        node: WorkflowNode, output, metadata: dict, state: WorkflowState
    ) -> None:
        state.node_outputs[node.id] = output
        state.variables[node.id] = output

        field = _OUTPUT_FIELD.get(node.type)
        if field is not None and output is not None:
            setattr(state, field, output)

        # Accumulate any sources the node surfaced.
        srcs = (metadata or {}).get("sources")
        if srcs:
            state.sources.extend(srcs)

        # Generic escape hatch: a handler may request explicit state writes.
        updates = (metadata or {}).get("state_updates")
        if isinstance(updates, dict):
            for k, v in updates.items():
                if hasattr(state, k):
                    setattr(state, k, v)
                else:
                    state.variables[k] = v
