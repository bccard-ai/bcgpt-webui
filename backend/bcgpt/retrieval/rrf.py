from __future__ import annotations
import hashlib
from dataclasses import dataclass, field


@dataclass
class RRFResult:
    id: str
    content: str
    metadata: dict
    score: float = 0.0


def rrf_fuse(
    track_results: list[list[dict]],
    weights: list[float],
    k: int = 60,
    top_n: int = 10,
    query_weight: float = 1.0,
) -> list[RRFResult]:
    fused: dict[str, RRFResult] = {}

    for results, weight in zip(track_results, weights):
        for rank, doc in enumerate(results):
            content = doc.get("page_content", doc.get("content", ""))
            doc_key = hashlib.sha256(content[:500].encode()).hexdigest()

            rrf_score = weight * query_weight / (k + rank + 1)

            if doc_key in fused:
                fused[doc_key].score += rrf_score
            else:
                fused[doc_key] = RRFResult(
                    id=doc_key,
                    content=content,
                    metadata=doc.get("metadata", {}),
                    score=rrf_score,
                )

    sorted_results = sorted(fused.values(), key=lambda x: x.score, reverse=True)[:top_n]

    if sorted_results:
        max_score = sorted_results[0].score
        if max_score > 0:
            for r in sorted_results:
                r.score = r.score / max_score

    return sorted_results
