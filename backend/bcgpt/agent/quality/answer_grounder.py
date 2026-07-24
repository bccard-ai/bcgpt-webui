"""AnswerGrounder: check whether each claim is supported by the sources."""

from __future__ import annotations

from typing import Any

from bcgpt.agent.quality.base import judge_json

_SYSTEM = (
    "You verify whether each claim is supported by the provided sources. For "
    "each claim, decide: 'supported' (sources back it), 'contradicted' (sources "
    "refute it), or 'unsupported' (sources are silent). Respond with ONLY a JSON "
    'array of objects: {"claim": str, "verdict": str, "source_index": int|null}.'
)


def _format_sources(sources: list[dict]) -> str:
    lines = []
    for i, s in enumerate(sources or []):
        doc = (s.get("document") or "")[:500]
        lines.append(f"[{i}] {doc}")
    return "\n".join(lines) or "(no sources)"


class AnswerGrounder:
    def __init__(self, request: Any, user: Any, model_id: str) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id

    async def verify(self, claims: list[str], sources: list[dict]) -> list[dict]:
        if not claims:
            return []
        prompt = (
            "Sources:\n"
            f"{_format_sources(sources)}\n\n"
            "Claims:\n"
            + "\n".join(f"- {c}" for c in claims)
            + "\n\nReturn the JSON array described in the system prompt."
        )
        result = await judge_json(
            self.request, self.user, self.model_id, _SYSTEM, prompt
        )
        if isinstance(result, list):
            out = []
            for item in result:
                if isinstance(item, dict) and "claim" in item:
                    out.append(
                        {
                            "claim": str(item.get("claim")),
                            "verdict": str(item.get("verdict", "unsupported")),
                            "source_index": item.get("source_index"),
                        }
                    )
            return out
        # Fallback: mark all unsupported (neutral, non-blocking).
        return [
            {"claim": c, "verdict": "unsupported", "source_index": None} for c in claims
        ]

    @staticmethod
    def score(grounding: list[dict]) -> float:
        if not grounding:
            return 0.0
        supported = sum(1 for g in grounding if g.get("verdict") == "supported")
        return round(supported / len(grounding), 4)
