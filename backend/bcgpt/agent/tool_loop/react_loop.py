"""The N-hop ReAct tool loop.

Because BCGPT providers do not expose native function calling, the loop teaches
the model a tiny JSON protocol via the system prompt and parses tool calls out
of the response. If a provider *does* return native ``tool_calls`` they are used
directly. Tools persist across hops (chaining), and a hard
``max_iterations`` cap forces a final answer (safety).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from bcgpt.agent.llm import extract_content, extract_message, llm_complete
from bcgpt.agent.tool_loop.tools import ToolContext, ToolDefinition

log = logging.getLogger(__name__)

_TOOL_CALL_BLOCK = re.compile(r"```(?:tool_call|json)?\s*(\{.*?\})\s*```", re.DOTALL)

_SYSTEM_PROTOCOL = """You are an autonomous agent that can call tools to gather \
information before answering.

Available tools:
{tool_descriptions}

To call a tool, reply with ONLY one or more fenced blocks of this exact form:
```tool_call
{{"name": "<tool_name>", "arguments": {{ ... }}}}
```
You may emit several blocks to call multiple tools at once. After you receive \
the tool results, decide whether to call more tools or give your final answer.

When you have enough information, reply with your final answer as normal prose \
and DO NOT include any tool_call block. Do not invent tool results."""


@dataclass
class LoopResult:
    content: str
    iterations: int
    tool_call_log: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    stopped_reason: str = "completed"


def _parse_tool_calls(message: dict, content: str) -> list[dict]:
    """Return a list of {"name", "arguments", "id"} from native or prompt form."""
    # 1) native OpenAI tool_calls
    native = message.get("tool_calls") if isinstance(message, dict) else None
    if native:
        calls = []
        for tc in native:
            fn = (tc or {}).get("function", {})
            args = fn.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {}
            calls.append(
                {"name": fn.get("name"), "arguments": args or {}, "id": tc.get("id")}
            )
        return [c for c in calls if c["name"]]

    # 2) prompt-protocol fenced blocks
    calls = []
    for i, match in enumerate(_TOOL_CALL_BLOCK.finditer(content or "")):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        name = obj.get("name") or obj.get("tool")
        if not name:
            continue
        args = obj.get("arguments") or obj.get("args") or {}
        if not isinstance(args, dict):
            args = {}
        calls.append({"name": name, "arguments": args, "id": f"call_{i}"})
    return calls


def _strip_tool_blocks(content: str) -> str:
    return _TOOL_CALL_BLOCK.sub("", content or "").strip()


class ReactToolLoop:
    def __init__(
        self,
        *,
        request: Any,
        user: Any,
        model_id: str,
        tools: list[ToolDefinition],
        max_iterations: int = 10,
        params: Optional[dict] = None,
        node_config: Optional[dict] = None,
        approval_gate=None,
    ) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id
        self.tools = {t.name: t for t in tools}
        self.max_iterations = max(1, int(max_iterations))
        self.params = params or {}
        self.approval_gate = approval_gate
        self.ctx = ToolContext(
            request=request, user=user, node_config=node_config or {}
        )

    def _system_prompt(self) -> str:
        descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tools.values()
        )
        return _SYSTEM_PROTOCOL.format(tool_descriptions=descriptions or "(none)")

    async def run(self, messages: list[dict], event_emitter=None) -> LoopResult:
        convo: list[dict] = []
        if self.tools:
            convo.append({"role": "system", "content": self._system_prompt()})
        # Carry any caller system message after our protocol preamble.
        convo.extend(messages)

        tool_schemas = [t.to_openai_schema() for t in self.tools.values()]
        tool_log: list[dict] = []

        for iteration in range(self.max_iterations):
            resp = await llm_complete(
                self.request,
                self.user,
                self.model_id,
                convo,
                params=self.params,
                tools=tool_schemas or None,
            )
            message = extract_message(resp)
            content = extract_content(resp)

            calls = _parse_tool_calls(message, content) if self.tools else []
            if not calls:
                return LoopResult(
                    content=_strip_tool_blocks(content) or content,
                    iterations=iteration + 1,
                    tool_call_log=tool_log,
                    sources=list(self.ctx.sources),
                    stopped_reason="completed",
                )

            # Record the assistant turn that requested tools.
            convo.append({"role": "assistant", "content": content})

            results_text: list[str] = []
            for call in calls:
                name = call["name"]
                args = call["arguments"]
                tool = self.tools.get(name)
                if self.approval_gate is not None:
                    decision = await self.approval_gate(
                        {
                            "scope": "tool_call",
                            "tool_name": name,
                            "arguments": args,
                            "iteration": iteration,
                        }
                    )
                    if not decision.get("approved", False):
                        results_text.append(
                            f"Tool `{name}` blocked: {decision.get('reason', '')}"
                        )
                        tool_log.append(
                            {
                                "name": name,
                                "arguments": args,
                                "blocked": True,
                                "reason": decision.get("reason", ""),
                            }
                        )
                        continue
                if event_emitter:
                    try:
                        await event_emitter(
                            {"type": "status", "data": {"action": "tool", "name": name}}
                        )
                    except Exception:
                        pass
                if tool is None:
                    out = f"Unknown tool: {name}"
                else:
                    try:
                        out = await tool.executor(args, self.ctx)
                    except Exception as e:  # noqa: BLE001
                        out = f"Error executing {name}: {e}"
                tool_log.append({"name": name, "arguments": args, "result": out[:500]})
                results_text.append(f"Tool `{name}` result:\n{out}")

            # Feed results back as a user turn (provider-agnostic; avoids
            # relying on role:"tool" support).
            convo.append(
                {
                    "role": "user",
                    "content": "\n\n".join(results_text)
                    + "\n\nContinue, or give your final answer.",
                }
            )

        # Exhausted iterations → force a final answer with tools disabled.
        convo.append(
            {
                "role": "user",
                "content": "Provide your best final answer now using the "
                "information gathered. Do not call any more tools.",
            }
        )
        resp = await llm_complete(
            self.request, self.user, self.model_id, convo, params=self.params
        )
        return LoopResult(
            content=_strip_tool_blocks(extract_content(resp)),
            iterations=self.max_iterations,
            tool_call_log=tool_log,
            sources=list(self.ctx.sources),
            stopped_reason="max_iterations",
        )
