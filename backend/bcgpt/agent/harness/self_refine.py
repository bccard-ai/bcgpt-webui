from __future__ import annotations

from bcgpt.agent.harness.base import HarnessExecutor, HarnessResult

_INITIAL_PROMPT = """\
You are an expert agent. Complete the following task.

Task: {task}
Context: {context}

Answer:"""


_FEEDBACK_PROMPT = """\
You are a quality reviewer. Given the task and the current answer, provide \
specific, actionable feedback for improvement. If the answer is already \
excellent and needs no changes, respond with exactly: NO_FEEDBACK

Task: {task}
Current answer: {answer}

Feedback:"""


_REFINE_PROMPT = """\
You are an expert agent. Refine the answer based on the feedback. \
Output only the refined answer.

Task: {task}
Current answer: {answer}
Feedback: {feedback}

Refined answer:"""


class SelfRefineExecutor(HarnessExecutor):
    name = "self_refine"

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
            feedback = await self._llm(
                [
                    {
                        "role": "user",
                        "content": _FEEDBACK_PROMPT.format(task=task, answer=answer),
                    }
                ]
            )

            if feedback.strip().upper().startswith("NO_FEEDBACK"):
                break

            reflections.append(feedback)

            answer = await self._llm(
                [
                    {
                        "role": "user",
                        "content": _REFINE_PROMPT.format(
                            task=task, answer=answer, feedback=feedback
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
            metadata={"strategy": "self_refine"},
        )
