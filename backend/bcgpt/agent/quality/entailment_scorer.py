"""EntailmentScorer: does the whole answer follow from the sources? (0.0–1.0)."""

from __future__ import annotations

from typing import Any

from bcgpt.agent.quality.base import judge_json

_SYSTEM = (
    "You judge whether an answer is entailed (fully supported) by the provided "
    'sources. Output ONLY JSON: {"entailment": number (0.0-1.0), '
    '"rationale": str}.'
)


class EntailmentScorer:
    def __init__(self, request: Any, user: Any, model_id: str) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id

    async def score(self, answer: str, sources: list[dict]) -> dict:
        if not answer or not sources:
            return {"entailment": 0.0, "rationale": "no answer or no sources"}
        src = "\n".join(
            f"[{i}] {(s.get('document') or '')[:400]}" for i, s in enumerate(sources)
        )
        prompt = f"Sources:\n{src}\n\nAnswer:\n{answer}\n\nReturn the JSON object."
        result = await judge_json(
            self.request, self.user, self.model_id, _SYSTEM, prompt
        )
        if isinstance(result, dict) and "entailment" in result:
            try:
                val = float(result["entailment"])
            except (TypeError, ValueError):
                val = 0.0
            return {
                "entailment": max(0.0, min(1.0, val)),
                "rationale": str(result.get("rationale", "")),
            }
        return {"entailment": 0.0, "rationale": "could not score"}
