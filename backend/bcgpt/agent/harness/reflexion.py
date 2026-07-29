from __future__ import annotations

from bcgpt.agent.harness.base import HarnessExecutor, HarnessResult

_INITIAL_PROMPT = """\
You are an expert agent. Complete the following task to the best of your ability.

Task: {task}
Context: {context}

Provide your answer:"""


_REFLECT_PROMPT = """\
You are a critical reviewer. Given the task and the current answer, identify \
specific weaknesses, errors, or areas for improvement. Be concise (max 3 bullet points).

Task: {task}
Current answer: {answer}

Critique:"""


_REFINE_PROMPT = """\
You are an expert agent. Improve the answer based on the critique. \
Output only the improved answer.

Task: {task}
Current answer: {answer}
Critique: {critique}

Improved answer:"""


class ReflexionExecutor(HarnessExecutor):
    name = "reflexion"

    async def execute(self, task: str, context: dict | None = None) -> HarnessResult:
        ctx = context or {}
        context_str = ctx.get("context", "No additional context provided.")

        reflections: list[str] = []
        drafts: list[str] = []

        answer = await self._llm(
            [
                {
                    "role": "user",
                    "content": _INITIAL_PROMPT.format(task=task, context=context_str),
                }
            ]
        )
        drafts.append(answer)

        for i in range(self.max_iterations - 1):
            critique = await self._llm(
                [
                    {
                        "role": "user",
                        "content": _REFLECT_PROMPT.format(task=task, answer=answer),
                    }
                ]
            )
            reflections.append(critique)

            if "no issues" in critique.lower() or "no improvement" in critique.lower():
                break

            answer = await self._llm(
                [
                    {
                        "role": "user",
                        "content": _REFINE_PROMPT.format(
                            task=task, answer=answer, critique=critique
                        ),
                    }
                ]
            )
            drafts.append(answer)

        return HarnessResult(
            answer=answer,
            iterations=len(drafts),
            reflections=reflections,
            drafts=drafts,
            metadata={"strategy": "reflexion"},
        )
