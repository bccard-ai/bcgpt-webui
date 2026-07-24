"""Tests for Late Chunking span mapping (``retrieval/chunking/late_chunking.py``).

Late Chunking embeds the full document once, then mean-pools the per-token embeddings
within each chunk's span. The correctness-critical pure piece is
``LateChunker._char_to_token_spans`` -- mapping (char_start, char_end) chunk spans to
(token_start, token_end) indices over the tokenizer's offset mapping. A wrong mapping
pools the wrong tokens into the wrong chunk vector. ``embed_with_spans`` itself needs the
bge-m3 model so it isn't exercised, except its empty-input guard.

``_char_to_token_spans`` does not touch the model, so ``LateChunker(None)`` is used.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_late_chunking.py -q
"""

from __future__ import annotations

from bcgpt.retrieval.chunking.late_chunking import LateChunker

# model is unused by _char_to_token_spans / the empty-spans guard
_chunker = LateChunker(None)


# ---------------------------------------------------------------------------
# _char_to_token_spans -- single-char tokens (offsets = (i, i+1))
# ---------------------------------------------------------------------------


def test_single_char_tokens_basic_spans():
    offsets = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]  # tokens "a","b","c","d","e"
    assert _chunker._char_to_token_spans([(0, 2)], offsets) == [(0, 2)]
    assert _chunker._char_to_token_spans([(2, 4)], offsets) == [(2, 4)]
    assert _chunker._char_to_token_spans([(4, 5)], offsets) == [(4, 5)]


def test_multiple_spans_in_one_call():
    offsets = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    assert _chunker._char_to_token_spans([(0, 2), (2, 4)], offsets) == [(0, 2), (2, 4)]


def test_empty_char_spans_returns_empty():
    assert _chunker._char_to_token_spans([], [(0, 1)]) == []


# ---------------------------------------------------------------------------
# multi-char tokens
# ---------------------------------------------------------------------------


def test_multi_char_tokens_whole_spans():
    # tokens "abc"(0-3), "def"(3-6), "ghi"(6-9)
    offsets = [(0, 3), (3, 6), (6, 9)]
    assert _chunker._char_to_token_spans([(3, 9)], offsets) == [
        (1, 3)
    ]  # tokens def,ghi
    assert _chunker._char_to_token_spans([(0, 3)], offsets) == [(0, 1)]  # token abc


def test_span_ending_mid_token_excludes_that_token():
    # The mapping includes a token only if its END <= char_end, so a span that
    # ends inside a token excludes it.
    offsets = [(0, 3), (3, 6), (6, 9)]
    # char span (2,5): token0 end=3<=5 include; token1 end=6<=5? no -> exclude
    assert _chunker._char_to_token_spans([(2, 5)], offsets) == [(0, 1)]


# ---------------------------------------------------------------------------
# degenerate / out-of-range spans never produce an empty token span
# ---------------------------------------------------------------------------


def test_degenerate_span_yields_at_least_one_token():
    offsets = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    # (3,3): zero-width char span -> still >=1 token (mean-pool must not be empty/NaN)
    spans = _chunker._char_to_token_spans([(3, 3)], offsets)
    assert spans == [(3, 4)]
    assert all(e > s for s, e in spans)


def test_out_of_range_span_clamps_to_last_token():
    offsets = [(0, 1), (1, 2), (2, 3)]
    # char span past the end maps to the final token (no IndexError).
    spans = _chunker._char_to_token_spans([(10, 12)], offsets)
    assert spans == [(2, 3)]


# ---------------------------------------------------------------------------
# embed_with_spans -- empty-input guard (no model needed)
# ---------------------------------------------------------------------------


def test_embed_with_spans_empty_returns_empty():
    # The guard at the top returns [] before touching the tokenizer/model.
    assert LateChunker(None).embed_with_spans("anything", []) == []
