"""Abstract base for all workflow node handlers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)


class NodeHandler(ABC):
    """Base class for node handlers.

    Handlers are stateless singletons. They **read** from ``state`` / ``context``
    and **return** a :class:`NodeResult`; they must not mutate ``state`` directly
    (the engine applies results after each layer, keeping concurrent siblings
    race-free). Returning a bare value instead of a NodeResult is tolerated — the
    engine wraps it.
    """

    @abstractmethod
    async def execute(
        self,
        node: WorkflowNode,
        state: WorkflowState,
        context: ExecutionContext,
    ) -> NodeResult: ...
