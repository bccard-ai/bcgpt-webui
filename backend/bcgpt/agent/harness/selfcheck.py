from __future__ import annotations

import random

from bcgpt.agent.harness.base import HarnessExecutor, HarnessResult

_ANSWER_PROMPT = """\
You are an expert agent. Answer the following question.

Question: {task}
Context: {context}

Answer:"""


_CHECK_PROMPT = """\
You are a consistency checker. You will see a question and two candidate answers. \
Determine whether both answers convey the same core information (consistent) or \
if they contradict each other on key points (inconsistent). \
Respond with exactly one word: CONSISTENT or INCONSISTENT.

Question: {task}
Answer A: {answer_a}
Answer B: {answer_b}

Verdict:"""


class SelfCheckGPTExecutor(HarnessExecutor):
    """SelfCheckGPT: generate N sample answers, pairwise-check consistency.

    Samples that are inconsistent with the majority are flagged. The final
    answer is the first sample that is consistent with the majority of others.
    """

    name = "selfcheck_gpt"
    num_samples: int = 3

    def __init__(self, *args, num_samples: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        if num_samples is not None:
            self.num_samples = num_samples

    async def execute(self, task: str, context: dict | None = None) -> HarnessResult:
        ctx = context or {}
        context_str = ctx.get("context", "No additional context provided.")

        samples: list[str] = []
        for _ in range(self.num_samples):
            temperature = self.params.get("temperature", 0.7)
            answer = await self._llm(
                [
                    {
                        "role": "user",
                        "content": _ANSWER_PROMPT.format(task=task, context=context_str),
                    }
                ],
                params={"temperature": temperature},
            )
            samples.append(answer)

        consistent_flags = [True] * len(samples)
        for i in range(len(samples)):
            inconsistencies = 0
            for j in range(len(samples)):
                if i == j:
                    continue
                verdict = await self._llm(
                    [
                        {
                            "role": "user",
                            "content": _CHECK_PROMPT.format(
                                task=task, answer_a=samples[i], answer_b=samples[j]
                            ),
                        }
                    ],
                    params={"temperature": 0.0},
                )
                if "INCONSISTENT" in verdict.upper():
                    inconsistencies += 1
            consistent_flags[i] = inconsistencies <= len(samples) // 2

        verified = any(consistent_flags)
        for i, ok in enumerate(consistent_flags):
            if ok:
                return HarnessResult(
                    answer=samples[i],
                    iterations=len(samples),
                    reflections=[
                        f"sample_{j}: {'consistent' if f else 'inconsistent'}"
                        for j, f in enumerate(consistent_flags)
                    ],
                    drafts=samples,
                    verified=verified,
                    metadata={
                        "strategy": "selfcheck_gpt",
                        "num_samples": self.num_samples,
                        "consistent_flags": consistent_flags,
                    },
                )

        return HarnessResult(
            answer=samples[0],
            iterations=len(samples),
            reflections=[
                f"sample_{j}: {'consistent' if f else 'inconsistent'}"
                for j, f in enumerate(consistent_flags)
            ],
            drafts=samples,
            verified=False,
            metadata={
                "strategy": "selfcheck_gpt",
                "num_samples": self.num_samples,
                "consistent_flags": consistent_flags,
            },
        )
