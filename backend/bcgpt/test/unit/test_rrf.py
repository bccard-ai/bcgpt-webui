"""Tests for Reciprocal Rank Fusion (``retrieval/rrf.py``).

RRF fuses multiple ranked retrieval tracks (vector + BM25) into one ranking -- it is the
core of hybrid search and decides which documents the LLM sees. ``rrf_fuse`` is pure
(``hashlib`` + dataclasses), so the RRF math, cross-track accumulation, dedup,
normalization, and truncation are locked directly. Reviewed correct (iter-76); these guard
against a regression that would silently reorder retrieval.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_rrf.py -q
"""

from __future__ import annotations

from bcgpt.retrieval.rrf import rrf_fuse


def test_single_track_preserves_rank_order():
    res = rrf_fuse(
        [[{"content": "a"}, {"content": "b"}, {"content": "c"}]], [1.0], k=60
    )
    assert [r.content for r in res] == ["a", "b", "c"]
    assert res[0].score > res[1].score > res[2].score


def test_rrf_score_normalizes_top_to_one():
    # A single doc normalizes to 1.0 (max / itself).
    res = rrf_fuse([[{"content": "x"}]], [0.7], k=60)
    assert abs(res[0].score - 1.0) < 1e-9


def test_rank_score_formula():
    # Without normalization interference: rank 1 score / rank 0 score = (k+1)/(k+2).
    res = rrf_fuse([[{"content": "first"}, {"content": "second"}]], [1.0], k=60)
    ratio = res[1].score / res[0].score
    assert abs(ratio - 61 / 62) < 1e-9


def test_doc_in_both_tracks_ranks_first():
    # A doc present in BOTH tracks accumulates both scores -> outranks a doc in only one.
    shared = [{"content": "shared"}]
    res = rrf_fuse([shared + [{"content": "vonly"}], shared], weights=[0.7, 0.3], k=60)
    assert res[0].content == "shared"


def test_dedup_same_content_accumulates():
    res = rrf_fuse([[{"content": "dup"}], [{"content": "dup"}]], [0.5, 0.5])
    assert len(res) == 1
    assert res[0].content == "dup"


def test_top_n_truncation():
    res = rrf_fuse([[{"content": str(i)} for i in range(10)]], [1.0], top_n=3)
    assert len(res) == 3


def test_empty_inputs_return_empty():
    assert rrf_fuse([], []) == []
    assert rrf_fuse([[]], [1.0]) == []


def test_weights_affect_ordering():
    # The top doc of the heavily-weighted track outranks the top of the light track.
    res = rrf_fuse(
        [[{"content": "heavy_top"}], [{"content": "light_top"}]],
        weights=[0.9, 0.1],
        k=60,
    )
    assert res[0].content == "heavy_top"


def test_page_content_and_content_keys_both_accepted():
    # The fusion reads "page_content" or "content" (langchain vs plain dict).
    res = rrf_fuse(
        [[{"page_content": "via_page"}], [{"content": "via_content"}]], [0.5, 0.5]
    )
    assert {r.content for r in res} == {"via_page", "via_content"}
