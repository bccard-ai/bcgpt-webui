"""DAG workflow engine for the agent subsystem.

A workflow is a directed acyclic graph of typed nodes. The engine validates the
graph, topologically sorts it, and runs each node's handler in order, threading
a mutable :class:`WorkflowState` and a runtime :class:`ExecutionContext`.

Public surface::

    from bcgpt.agent.workflow import (
        WorkflowEngine, WorkflowNode, WorkflowState, NodeResult,
        ExecutionContext, NodeHandlerRegistry, DynamicWorkflowGenerator,
        validate_workflow, serialize_workflow, deserialize_workflow,
    )
"""

from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)
from bcgpt.agent.workflow.registry import NodeHandlerRegistry
from bcgpt.agent.workflow.validator import (
    WorkflowValidationError,
    topological_sort,
    validate_workflow,
)
from bcgpt.agent.workflow.engine import WorkflowEngine
from bcgpt.agent.workflow.generator import DynamicWorkflowGenerator
from bcgpt.agent.workflow.serializer import (
    deserialize_workflow,
    serialize_workflow,
)

__all__ = [
    "ExecutionContext",
    "NodeResult",
    "WorkflowNode",
    "WorkflowState",
    "NodeHandlerRegistry",
    "WorkflowValidationError",
    "topological_sort",
    "validate_workflow",
    "WorkflowEngine",
    "DynamicWorkflowGenerator",
    "deserialize_workflow",
    "serialize_workflow",
]
