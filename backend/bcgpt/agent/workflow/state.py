"""Workflow data structures: nodes, mutable state, node results, runtime context.

These are deliberately dependency-free (no DB, no FastAPI, no config imports) so
the engine core can be unit-tested in isolation. Runtime dependencies that a
handler needs (the FastAPI ``Request``, the authenticated user, the resolved
model dict, an event emitter) live on :class:`ExecutionContext`, which is passed
*alongside* — not inside — the serialisable :class:`WorkflowState`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from bcgpt.agent.types import ErrorStrategy, NodeType


@dataclass
class WorkflowNode:
    """A single node in the workflow DAG.

    ``next_nodes`` lists the ids of downstream nodes (edges out of this node).
    ``config`` holds node-type-specific settings (e.g. ``collection_ids`` for
    a RAG node, ``error_strategy`` / ``max_retries`` / ``fallback_value`` for
    error handling, ``enable_tool_loop`` for an operator LLM node).
    """

    id: str
    type: NodeType
    config: dict = field(default_factory=dict)
    next_nodes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Allow constructing with a raw string type for convenience/JSON.
        if not isinstance(self.type, NodeType):
            self.type = NodeType.from_value(self.type)

    @property
    def error_strategy(self) -> ErrorStrategy:
        return ErrorStrategy.from_value(self.config.get("error_strategy"))

    @property
    def max_retries(self) -> int:
        try:
            return int(self.config.get("max_retries", 1))
        except (TypeError, ValueError):
            return 1


@dataclass
class NodeResult:
    """The result of executing one node.

    ``output`` is written into ``state.node_outputs[node.id]``. ``metadata`` is
    free-form (counts, timings, citations). ``error`` is set when the handler
    failed in a recoverable way without raising.
    """

    output: Any = None
    metadata: dict = field(default_factory=dict)
    error: Optional[Exception] = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class WorkflowState:
    """Mutable state threaded through the workflow.

    Mirrors Open-MoAI's ``WorkflowState`` (a Promise-based variable store)
    adapted to Python: ``variables`` is the general-purpose key/value store and
    ``node_outputs`` records each node's output for observability and for
    downstream nodes to consume.
    """

    user_input: str = ""
    messages: list[dict] = field(default_factory=list)
    rag_results: Optional[list] = None
    web_results: Optional[list] = None
    sources: list[dict] = field(default_factory=list)
    merged_context: Optional[str] = None
    llm_response: Optional[str] = None
    final_response: Optional[str] = None
    variables: dict = field(default_factory=dict)
    node_outputs: dict = field(default_factory=dict)
    source_mapping: Optional[dict] = None
    status: str = "running"  # running | completed | failed
    errors: dict = field(default_factory=dict)  # node_id -> Exception
    visited: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """JSON-safe snapshot (exceptions rendered as strings)."""
        return {
            "user_input": self.user_input,
            "rag_results": self.rag_results,
            "web_results": self.web_results,
            "sources": self.sources,
            "merged_context": self.merged_context,
            "llm_response": self.llm_response,
            "final_response": self.final_response,
            "variables": self.variables,
            "node_outputs": self.node_outputs,
            "source_mapping": self.source_mapping,
            "status": self.status,
            "errors": {k: str(v) for k, v in self.errors.items()},
            "visited": self.visited,
        }


# An async hook used to stream status/progress events to the client. Optional.
EventEmitter = Callable[[dict], Awaitable[None]]


@dataclass
class ExecutionContext:
    """Runtime dependencies handed to node handlers.

    Kept separate from :class:`WorkflowState` so state stays serialisable. Any
    field may be ``None`` in tests; handlers must degrade gracefully.
    """

    request: Any = None  # FastAPI Request (for app.state / config)
    user: Any = None  # authenticated UserModel
    model: Optional[dict] = None  # resolved runtime model dict
    model_id: Optional[str] = None
    params: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)
    event_emitter: Optional[EventEmitter] = None
    approval_gate: Optional[Callable[[dict], Awaitable[dict]]] = None

    async def emit(self, event: dict) -> None:
        if self.event_emitter is not None:
            try:
                await self.event_emitter(event)
            except Exception:  # never let telemetry break execution
                pass
