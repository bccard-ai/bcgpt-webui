"""Dynamic ReAct tool loop (operator autonomy).

Provider-agnostic: BCGPT's providers don't (yet) expose native function calling,
so the loop drives tool use through a small prompt protocol while *also*
honouring native ``tool_calls`` if a provider returns them — forward-compatible
with the planned native function-calling work.
"""

from bcgpt.agent.tool_loop.react_loop import LoopResult, ReactToolLoop
from bcgpt.agent.tool_loop.tools import (
    BUILTIN_TOOLS,
    ToolContext,
    ToolDefinition,
    resolve_tools,
)

__all__ = [
    "ReactToolLoop",
    "LoopResult",
    "ToolDefinition",
    "ToolContext",
    "BUILTIN_TOOLS",
    "resolve_tools",
]
