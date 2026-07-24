"""DocumentGrader: rate how relevant each retrieved document is to the query."""

from __future__ import annotations

from typing import Any

from bcgpt.agent.quality.base import judge_json

_SYSTEM = (
    "You grade the relevance of each document to a user query on a 0.0–1.0 "
    "scale (1.0 = directly answers, 0.0 = irrelevant). Respond with ONLY a JSON "
    'array of objects: {"index": int, "relevance": number}.'
)


class DocumentGrader:
    def __init__(self, request: Any, user: Any, model_id: str) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id

    async def grade(self, documents: list[dict], query: str) -> list[dict]:
        if not documents:
            return []
        doc_text = "\n".join(
            f"[{i}] {(d.get('document') or '')[:400]}" for i, d in enumerate(documents)
        )
        prompt = (
            f"Query: {query}\n\nDocuments:\n{doc_text}\n\n"
            "Return the JSON array described in the system prompt."
        )
        result = await judge_json(
            self.request, self.user, self.model_id, _SYSTEM, prompt
        )
        graded: list[dict] = []
        if isinstance(result, list):
            for item in result:
                if isinstance(item, dict) and "index" in item:
                    try:
                        rel = float(item.get("relevance", 0.0))
                    except (TypeError, ValueError):
                        rel = 0.0
                    graded.append(
                        {
                            "index": int(item["index"]),
                            "relevance": max(0.0, min(1.0, rel)),
                        }
                    )
        if graded:
            return graded
        return [{"index": i, "relevance": 0.5} for i in range(len(documents))]

    @staticmethod
    def score(graded: list[dict]) -> float:
        if not graded:
            return 0.0
        return round(sum(g["relevance"] for g in graded) / len(graded), 4)
