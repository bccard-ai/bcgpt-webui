"""Tests for the RAG result merge (``retrieval/search.py::merge_and_sort_query_results``).

This is the core retrieval merge: deduplicate across sources, sort by score, apply a
per-source diversity cap, then take top-k -- its ordering decides which documents the
LLM sees. ``merge_and_sort_query_results`` is pure (``hashlib`` + dict ops), so it is
exercised directly. The iter-70 hardening (tolerate ``None`` metadata and missing /
flat-shaped source results without raising) is locked too.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_search.py -q
"""

from __future__ import annotations

from bcgpt.retrieval.search import merge_and_sort_query_results


def _src(score_doc_meta: list[tuple[float, str, dict]]):
    """Build one source result dict from (score, document, metadata) triples."""
    distances, documents, metadatas = [], [], []
    for score, doc, meta in score_doc_meta:
        distances.append(score)
        documents.append(doc)
        metadatas.append(meta)
    return {
        "distances": [distances],
        "documents": [documents],
        "metadatas": [metadatas],
    }


def test_dedup_keeps_highest_score():
    r = merge_and_sort_query_results(
        [
            _src([(0.9, "doc A", {"source": "s1"}), (0.5, "doc B", {"source": "s2"})]),
            _src([(0.95, "doc A", {"source": "s1"})]),
        ],  # duplicate doc A, higher score
        k=5,
    )
    assert r["documents"][0] == ["doc A", "doc B"]
    assert r["distances"][0] == [0.95, 0.5]  # kept the 0.95, not 0.9


def test_sort_descending_by_score():
    r = merge_and_sort_query_results(
        [_src([(0.1, "low", {}), (0.9, "high", {}), (0.5, "mid", {})])],
        k=3,
    )
    assert r["documents"][0] == ["high", "mid", "low"]


def test_top_k_truncation():
    r = merge_and_sort_query_results(
        [
            _src(
                [
                    (0.9, "a", {"source": "s1"}),
                    (0.8, "b", {"source": "s2"}),
                    (0.7, "c", {"source": "s3"}),
                ]
            )
        ],
        k=2,
        max_per_source=3,
    )
    assert r["documents"][0] == ["a", "b"]  # top 2 by score


def test_diversity_cap_per_source():
    # All from one source; cap=2 keeps only the top 2 even though k=5.
    r = merge_and_sort_query_results(
        [
            _src(
                [
                    (0.9, "a", {"source": "s1"}),
                    (0.8, "b", {"source": "s1"}),
                    (0.7, "c", {"source": "s1"}),
                    (0.6, "d", {"source": "s1"}),
                ]
            )
        ],
        k=5,
        max_per_source=2,
    )
    assert r["documents"][0] == ["a", "b"]
    assert len(r["documents"][0]) == 2


def test_diversity_cap_disabled_when_zero():
    # max_per_source=0 -> no cap (all kept, subject to k).
    r = merge_and_sort_query_results(
        [_src([(0.9, "a", {"source": "s1"}), (0.8, "b", {"source": "s1"})])],
        k=5,
        max_per_source=0,
    )
    assert len(r["documents"][0]) == 2


def test_empty_input_returns_empty_structure():
    r = merge_and_sort_query_results([], k=5)
    assert r == {"distances": [[]], "documents": [[]], "metadatas": [[]]}


def test_non_string_documents_skipped():
    r = merge_and_sort_query_results(
        [_src([(0.9, "real doc", {}), (0.99, None, {}), (0.99, 123, {})])],
        k=5,
    )
    assert r["documents"][0] == ["real doc"]


# ---------------------------------------------------------------------------
# iter-70 hardening: tolerate malformed source shapes / None metadata
# ---------------------------------------------------------------------------


def test_none_metadata_does_not_crash():
    # A None metadata must not raise on the diversity-cap .get() (iter-70).
    r = merge_and_sort_query_results(
        [_src([(0.9, "doc A", None), (0.8, "doc B", {"source": "s2"})])],
        k=5,
    )
    assert set(r["documents"][0]) == {"doc A", "doc B"}


def test_missing_or_flat_shaped_source_does_not_crash():
    # Sources missing keys, or a flat (non-nested) list, must be tolerated.
    r = merge_and_sort_query_results(
        [
            {},  # empty source
            {"distances": [], "documents": [], "metadatas": []},  # flat-empty
            _src([(0.9, "doc A", {"source": "s1"})]),
        ],
        k=5,
    )
    assert r["documents"][0] == ["doc A"]
