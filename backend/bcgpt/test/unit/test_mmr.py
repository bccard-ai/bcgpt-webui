"""Unit tests for bcgpt.retrieval.mmr — deterministic, pure numpy."""

from __future__ import annotations

import math
import sys
import os

import numpy as np
import pytest

# Ensure backend root is on path so import works regardless of invocation directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from bcgpt.retrieval.mmr import _cosine_matrix, mmr_select_indices, mmr_rerank

# ---------------------------------------------------------------------------
# _cosine_matrix helpers
# ---------------------------------------------------------------------------


class TestCosineMatrix:
    def test_identical_vectors(self):
        a = np.array([[1.0, 0.0]])
        result = _cosine_matrix(a, a)
        assert result.shape == (1, 1)
        assert abs(result[0, 0] - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = np.array([[1.0, 0.0]])
        b = np.array([[0.0, 1.0]])
        result = _cosine_matrix(a, b)
        assert abs(result[0, 0]) < 1e-9

    def test_zero_norm_guard(self):
        a = np.array([[0.0, 0.0]])
        b = np.array([[1.0, 0.0]])
        # Should not raise; result is 0
        result = _cosine_matrix(a, b)
        assert result.shape == (1, 1)
        assert result[0, 0] == 0.0

    def test_shape(self):
        a = np.random.randn(3, 4)
        b = np.random.randn(5, 4)
        result = _cosine_matrix(a, b)
        assert result.shape == (3, 5)


# ---------------------------------------------------------------------------
# Test 1: Duplicate suppression
# ---------------------------------------------------------------------------


class TestDuplicateSuppression:
    """lambda_=0.5, top_k=2. Two identical [1,0] docs + one orthogonal [0,1].
    After picking index 0 ([1,0]), duplicate index 1 should be demoted below index 2 ([0,1]).
    """

    def test_duplicate_demoted(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
        result = mmr_select_indices(query, docs, lambda_=0.5, top_k=2)
        assert len(result) == 2
        assert result[0] == 0  # first pick is always the most relevant
        assert 1 not in result  # duplicate demoted out
        assert result == [0, 2]  # orthogonal wins second slot


# ---------------------------------------------------------------------------
# Test 2: lambda_=1.0 gives pure relevance order
# ---------------------------------------------------------------------------


class TestPureRelevance:
    """lambda_=1.0 => MMR degenerates to relevance ranking."""

    def test_lambda_one_is_pure_relevance(self):
        query = [1.0, 0.0]
        # cosine sims: [0,1]->0, [0.7,0.7]->~0.707, [1,0]->1.0
        docs = [[0.0, 1.0], [0.7, 0.7], [1.0, 0.0]]
        result = mmr_select_indices(query, docs, lambda_=1.0)
        assert result == [2, 1, 0], f"Expected [2,1,0], got {result}"


# ---------------------------------------------------------------------------
# Test 3: Empty inputs
# ---------------------------------------------------------------------------


class TestEmpty:
    def test_empty_embeddings_returns_empty_list(self):
        result = mmr_select_indices([1.0, 0.0], [], 0.7)
        assert result == []

    def test_mmr_rerank_empty(self):
        result = mmr_rerank([1.0, 0.0], [], [], 0.7)
        assert result == []


# ---------------------------------------------------------------------------
# Test 4: Single document
# ---------------------------------------------------------------------------


class TestSingleDoc:
    def test_single_doc_returns_zero(self):
        result = mmr_select_indices([1.0, 0.0], [[0.0, 1.0]], 0.7)
        assert result == [0]


# ---------------------------------------------------------------------------
# Test 5: top_k truncation
# ---------------------------------------------------------------------------


class TestTopKTruncation:
    def test_top_k_limits_output_length(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        result = mmr_select_indices(query, docs, lambda_=0.7, top_k=2)
        assert len(result) == 2

    def test_top_k_none_returns_all(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        result = mmr_select_indices(query, docs, lambda_=0.7, top_k=None)
        assert len(result) == 3

    def test_top_k_larger_than_n_returns_all(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [0.0, 1.0]]
        result = mmr_select_indices(query, docs, lambda_=0.7, top_k=100)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Test 6: mmr_rerank returns actual doc objects
# ---------------------------------------------------------------------------


class TestRerank:
    def test_rerank_returns_doc_objects(self):
        query = [1.0, 0.0]
        embeddings = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        docs = ["a", "b", "c"]
        result = mmr_rerank(query, embeddings, docs, lambda_=0.7, top_k=2)
        assert len(result) == 2
        assert all(isinstance(d, str) for d in result)
        assert all(d in docs for d in result)
        # first doc must be "a" (most relevant to [1,0])
        assert result[0] == "a"

    def test_rerank_all_docs(self):
        query = [1.0, 0.0]
        embeddings = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        docs = ["a", "b", "c"]
        result = mmr_rerank(query, embeddings, docs, lambda_=0.7)
        assert len(result) == 3
        assert set(result) == {"a", "b", "c"}


# ---------------------------------------------------------------------------
# Test 7: Length mismatch passthrough
# ---------------------------------------------------------------------------


class TestMismatchPassthrough:
    def test_mismatch_does_not_raise(self):
        # 1 embedding row but 2 docs -> mismatch
        result = mmr_rerank([1.0, 0.0], [[1.0, 0.0]], ["a", "b"], top_k=1)
        assert result == ["a"]

    def test_mismatch_returns_docs_slice(self):
        result = mmr_rerank([1.0, 0.0], [[1.0, 0.0]], ["a", "b"], top_k=1)
        assert result == ["a"]


# ---------------------------------------------------------------------------
# Additional edge-case robustness
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_top_k_zero_returns_empty(self):
        result = mmr_select_indices([1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], top_k=0)
        assert result == []

    def test_no_duplicate_indices_in_output(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5], [0.3, 0.7]]
        result = mmr_select_indices(query, docs, lambda_=0.5)
        assert len(result) == len(set(result)), "Duplicate indices returned"

    def test_all_indices_valid(self):
        query = [1.0, 0.0]
        docs = [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]]
        result = mmr_select_indices(query, docs, lambda_=0.5)
        assert all(0 <= i < 3 for i in result)
