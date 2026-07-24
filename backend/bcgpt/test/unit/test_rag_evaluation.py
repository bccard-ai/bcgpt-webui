"""Unit tests for the RAG-evaluation heuristics + overall-score renormalization.

Covers the cheap, no-LLM heuristics in ``retrieval/evaluation/metrics.py`` and the
renormalization in ``evaluator.py._compute_overall`` (plus a smoke run of
``evaluate_rag`` on the heuristic path). The async LLM metric functions
(``compute_faithfulness`` / ``compute_answer_relevance``) are not exercised.

Notable: ``_compute_overall`` already renormalizes over the metrics actually used
(and excludes None-valued metrics) -- the same property that had to be FIXED in
the agent quality pipeline; these tests lock that the RAG evaluator has it right.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_rag_evaluation.py -q
"""

from __future__ import annotations

import asyncio

import pytest

from bcgpt.retrieval.evaluation.evaluator import (
    RAGEvalResult,
    _compute_overall,
    evaluate_rag,
)
from bcgpt.retrieval.evaluation.metrics import (
    _answer_relevance_heuristic,
    _faithfulness_heuristic,
    compute_context_precision,
    compute_context_recall_heuristic,
    compute_relevance_score,
)

# ---------------------------------------------------------------------------
# compute_relevance_score
# ---------------------------------------------------------------------------


def test_relevance_empty_documents():
    assert compute_relevance_score("query", []) == 0.0


def test_relevance_empty_query():
    assert compute_relevance_score("", [{"text": "abc"}]) == 0.0


def test_relevance_keyword_overlap_only():
    # query terms all present (keyword 1.0), no score (similarity 0.0)
    # -> 0.6*1.0 + 0.4*0.0 = 0.6
    r = compute_relevance_score("apple banana", [{"text": "apple banana cherry"}])
    assert r == pytest.approx(0.6)


def test_relevance_score_scale_normalized():
    # score > 1.0 -> treated as 0-100 scale: 50 -> 0.5
    # keyword 1.0 + similarity 0.5 -> 0.6*1 + 0.4*0.5 = 0.8
    r = compute_relevance_score("apple", [{"text": "apple", "score": 50}])
    assert r == pytest.approx(0.8)


def test_relevance_none_score_does_not_crash():
    """Regression: a doc whose score is None must not raise (``None > 1.0`` is a
    TypeError). Non-numeric scores coerce to 0.0 similarity."""
    r = compute_relevance_score("apple", [{"text": "apple", "score": None}])
    assert isinstance(r, float)
    # keyword 1.0, similarity coerced to 0.0 -> 0.6
    assert r == pytest.approx(0.6)


def test_relevance_capped_at_one():
    r = compute_relevance_score("a", [{"text": "a", "score": 1.0}])
    assert r <= 1.0


# ---------------------------------------------------------------------------
# compute_context_precision (1 - avg pairwise word-overlap)
# ---------------------------------------------------------------------------


def test_precision_empty_is_zero():
    assert compute_context_precision([]) == 0.0


def test_precision_single_doc_is_zero():
    # <=1 doc -> no pairs to measure -> 0.0
    assert compute_context_precision([{"text": "solo"}]) == 0.0


def test_precision_diverse_docs_is_high():
    docs = [{"text": "alpha beta"}, {"text": "gamma delta"}]
    # no shared words -> jaccard 0 -> precision 1.0
    assert compute_context_precision(docs) == 1.0


def test_precision_identical_docs_is_low():
    docs = [{"text": "alpha beta"}, {"text": "alpha beta"}]
    # identical -> jaccard 1 -> precision 0.0
    assert compute_context_precision(docs) == 0.0


def test_precision_empty_content_no_crash():
    r = compute_context_precision([{"text": ""}, {"text": ""}])
    assert (
        0.0 <= r <= 1.0
    )  # both empty -> union empty -> jaccard 0 -> 1.0; must not crash


# ---------------------------------------------------------------------------
# compute_context_recall_heuristic
# ---------------------------------------------------------------------------


def test_recall_empty_docs():
    assert compute_context_recall_heuristic("query", []) == 0.0


def test_recall_empty_query():
    assert compute_context_recall_heuristic("", [{"text": "a"}]) == 0.0


def test_recall_full_coverage():
    assert (
        compute_context_recall_heuristic("apple banana", [{"text": "apple banana"}])
        == 1.0
    )


def test_recall_partial_coverage():
    assert compute_context_recall_heuristic("apple banana", [{"text": "apple"}]) == 0.5


# ---------------------------------------------------------------------------
# _faithfulness_heuristic / _answer_relevance_heuristic (LLM fallbacks)
# ---------------------------------------------------------------------------


def test_faithfulness_empty_answer():
    assert _faithfulness_heuristic("", [{"text": "x"}]) == 0.0


def test_faithfulness_full_support():
    assert (
        _faithfulness_heuristic("apple banana", [{"text": "apple banana cherry"}])
        == 1.0
    )


def test_faithfulness_partial_support():
    assert _faithfulness_heuristic("apple cherry", [{"text": "apple banana"}]) == 0.5


def test_answer_relevance_empty_inputs():
    assert _answer_relevance_heuristic("", "answer") == 0.0
    assert _answer_relevance_heuristic("query", "") == 0.0


def test_answer_relevance_full_overlap():
    assert _answer_relevance_heuristic("apple banana", "apple banana") == 1.0


# ---------------------------------------------------------------------------
# evaluator._compute_overall -- renormalization over metrics actually used
# ---------------------------------------------------------------------------


def test_overall_no_metrics_used_is_zero():
    assert _compute_overall(RAGEvalResult(query="q"), []) == 0.0


def test_overall_subset_is_renormalized():
    # only relevance (0.3) + context_precision (0.2) used -> renormalized over 0.5
    r = RAGEvalResult(query="q", relevance=1.0, context_precision=1.0)
    assert _compute_overall(r, ["relevance", "context_precision"]) == 1.0


def test_overall_none_valued_metric_is_excluded():
    # faithfulness used but None -> excluded, not scored 0
    r = RAGEvalResult(query="q", relevance=1.0, faithfulness=None)
    assert _compute_overall(r, ["relevance", "faithfulness"]) == 1.0


def test_overall_weighted_average():
    r = RAGEvalResult(query="q", relevance=0.5, context_precision=1.0)
    # (0.3*0.5 + 0.2*1.0) / 0.5 = 0.35 / 0.5 = 0.7
    assert _compute_overall(r, ["relevance", "context_precision"]) == 0.7


# ---------------------------------------------------------------------------
# evaluate_rag -- heuristic path (no LLM, no request/user needed)
# ---------------------------------------------------------------------------


def test_evaluate_rag_heuristic_path():
    result = asyncio.run(
        evaluate_rag(
            "apple banana",
            [{"text": "apple banana", "score": 0.9}],
            metrics="relevance,context_precision,context_recall",
        )
    )
    assert set(result.metrics_used) == {
        "relevance",
        "context_precision",
        "context_recall",
    }
    # keyword overlap full + similarity 0.9 -> 0.6*1 + 0.4*0.9 = 0.96
    assert result.relevance == pytest.approx(0.96)
    assert result.context_recall == 1.0  # full query coverage
    assert result.context_precision == 0.0  # single doc -> <=1 doc -> 0.0
    assert result.overall_score > 0.0
