"""Node handler registry: maps a :class:`NodeType` to its handler instance."""

from __future__ import annotations

from typing import Optional

from bcgpt.agent.types import NodeType


class NodeHandlerRegistry:
    """A simple type → handler map.

    Handlers are expected to be stateless singletons (they receive all per-run
    state via ``execute(node, state, context)``), so one registry can be shared
    across all concurrent workflow executions.
    """

    def __init__(self) -> None:
        self._handlers: dict[NodeType, object] = {}

    def register(self, node_type: NodeType, handler: object) -> "NodeHandlerRegistry":
        self._handlers[node_type] = handler
        return self

    def get(self, node_type: NodeType) -> Optional[object]:
        return self._handlers.get(node_type)

    def has(self, node_type: NodeType) -> bool:
        return node_type in self._handlers

    def types(self) -> list[NodeType]:
        return list(self._handlers.keys())
