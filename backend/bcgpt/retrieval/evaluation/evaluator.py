import logging
from dataclasses import dataclass, field

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.evaluation.metrics import (
    compute_relevance_score,
    compute_context_precision,
    compute_context_recall_heuristic,
    compute_faithfulness,
    compute_answer_relevance,
)

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

WEIGHTS = {
    "relevance": 0.3,
    "context_precision": 0.2,
    "context_recall": 0.1,
    "faithfulness": 0.25,
    "answer_relevance": 0.15,
}

HEURISTIC_METRICS = {"relevance", "context_precision", "context_recall"}
LLM_METRICS = {"faithfulness", "answer_relevance"}


@dataclass
class RAGEvalResult:
    query: str
    relevance: float = 0.0
    context_precision: float = 0.0
    context_recall: float = 0.0
    faithfulness: float | None = None
    answer_relevance: float | None = None
    overall_score: float = 0.0
    metrics_used: list[str] = field(default_factory=list)


async def evaluate_rag(
    query: str,
    documents: list[dict],
    answer: str | None = None,
    request=None,
    user=None,
    include_llm_metrics: bool = False,
    metrics: str = "faithfulness,relevance,context_precision",
) -> RAGEvalResult:
    requested = {m.strip() for m in metrics.split(",") if m.strip()}
    metrics_used = []

    result = RAGEvalResult(query=query)

    if "relevance" in requested:
        result.relevance = compute_relevance_score(query, documents)
        metrics_used.append("relevance")

    if "context_precision" in requested:
        result.context_precision = compute_context_precision(documents)
        metrics_used.append("context_precision")

    if "context_recall" in requested:
        result.context_recall = compute_context_recall_heuristic(query, documents)
        metrics_used.append("context_recall")

    if include_llm_metrics and request is not None and user is not None:
        if "faithfulness" in requested and answer:
            result.faithfulness = await compute_faithfulness(
                query, answer, documents, request, user
            )
            metrics_used.append("faithfulness")

        if "answer_relevance" in requested and answer:
            result.answer_relevance = await compute_answer_relevance(
                query, answer, request, user
            )
            metrics_used.append("answer_relevance")

    result.metrics_used = metrics_used
    result.overall_score = _compute_overall(result, metrics_used)

    return result


def _compute_overall(result: RAGEvalResult, metrics_used: list[str]) -> float:
    if not metrics_used:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0

    for metric_name in metrics_used:
        weight = WEIGHTS.get(metric_name, 0.0)
        value = getattr(result, metric_name, None)
        if value is not None and weight > 0:
            weighted_sum += weight * value
            total_weight += weight

    if total_weight == 0:
        return 0.0

    return weighted_sum / total_weight
