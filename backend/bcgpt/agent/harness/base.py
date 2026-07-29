from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import Request
    from bcgpt.models.users import User


@dataclass
class HarnessResult:
    answer: str
    iterations: int = 1
    reflections: list[str] = field(default_factory=list)
    drafts: list[str] = field(default_factory=list)
    verified: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class HarnessExecutor:
    """Base class for agent harness executors (plan-then-write, reflexion, etc.).

    Each executor implements a different multi-step LLM reasoning strategy
    on top of ``llm_complete``.
    """

    name: str = "base"
    max_iterations: int = 3

    def __init__(
        self,
        request: Request,
        user: User,
        model_id: str,
        *,
        max_iterations: int | None = None,
        params: dict | None = None,
    ):
        self.request = request
        self.user = user
        self.model_id = model_id
        self.params = params or {}
        if max_iterations is not None:
            self.max_iterations = max_iterations

    async def _llm(self, messages: list[dict], **extra) -> str:
        from bcgpt.agent.llm import llm_complete, extract_content

        resp = await llm_complete(
            request=self.request,
            user=self.user,
            model_id=self.model_id,
            messages=messages,
            params={**self.params, **extra.pop("params", {})},
            tools=None,
            bypass_filter=True,
            extra=extra,
        )
        return extract_content(resp)

    async def execute(self, task: str, context: dict | None = None) -> HarnessResult:
        raise NotImplementedError
