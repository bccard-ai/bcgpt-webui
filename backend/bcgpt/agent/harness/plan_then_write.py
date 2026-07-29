from __future__ import annotations

from bcgpt.agent.harness.base import HarnessExecutor, HarnessResult

_PLAN_PROMPT = """\
You are a planning agent. Given the task below, produce a concise step-by-step \
plan (max 5 steps). Each step should be a single actionable instruction. \
Output only the numbered plan, nothing else.

Task: {task}
"""

_EXECUTE_PROMPT = """\
You are an execution agent. Follow the plan below to complete the task. \
Produce a high-quality final answer.

Task: {task}

Plan:
{plan}

Context:
{context}

Answer:"""


class PlanThenWriteExecutor(HarnessExecutor):
    name = "plan_then_write"

    async def execute(self, task: str, context: dict | None = None) -> HarnessResult:
        ctx = context or {}
        context_str = ctx.get("context", "No additional context provided.")

        plan = await self._llm(
            [{"role": "user", "content": _PLAN_PROMPT.format(task=task)}]
        )

        answer = await self._llm(
            [
                {
                    "role": "user",
                    "content": _EXECUTE_PROMPT.format(
                        task=task, plan=plan, context=context_str
                    ),
                }
            ]
        )

        return HarnessResult(
            answer=answer,
            iterations=2,
            reflections=[f"Plan:\n{plan}"],
            metadata={"strategy": "plan_then_write"},
        )
