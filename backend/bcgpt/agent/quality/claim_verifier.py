"""ClaimVerifier: decompose an answer into atomic, checkable claims."""

from __future__ import annotations

from typing import Any

from bcgpt.agent.quality.base import judge_json

_SYSTEM = (
    "You break an assistant's answer into atomic factual claims. A claim is a "
    "single, self-contained, verifiable statement. Ignore opinions, hedges, and "
    "filler. Respond with ONLY a JSON array of strings."
)


class ClaimVerifier:
    def __init__(self, request: Any, user: Any, model_id: str) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id

    async def decompose(self, response: str) -> list[str]:
        if not response or not response.strip():
            return []
        prompt = (
            "Answer to decompose:\n\n"
            f"{response}\n\n"
            'Return JSON like ["claim 1", "claim 2", ...].'
        )
        result = await judge_json(
            self.request, self.user, self.model_id, _SYSTEM, prompt
        )
        if isinstance(result, list):
            return [str(c) for c in result if isinstance(c, (str, int, float))]
        return []
