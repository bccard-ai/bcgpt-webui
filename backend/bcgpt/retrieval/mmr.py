"""MMR diversity reranking (Carbonell & Goldstein 1998). Algorithm re-implemented from open-moai `lib/rag/mmr.ts` (Apache-2.0). MMR(d) = λ·rel(d,q) − (1−λ)·max_{d'∈S} sim(d,d'). Pure numpy; cosine similarity."""

from __future__ import annotations

from typing import Optional

import numpy as np


def _cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """L2-normalize rows of a (m,dim) and b (n,dim); return (m,n) cosine sim matrix. numpy. Guard zero-norm."""
    a = np.atleast_2d(a).astype(float)
    b = np.atleast_2d(b).astype(float)

    a_norm = np.linalg.norm(a, axis=1, keepdims=True)
    b_norm = np.linalg.norm(b, axis=1, keepdims=True)

    # Guard zero-norm: replace 0 with 1 to avoid division by zero (result stays 0 dot product)
    a_norm = np.where(a_norm == 0, 1.0, a_norm)
    b_norm = np.where(b_norm == 0, 1.0, b_norm)

    a_normalized = a / a_norm
    b_normalized = b / b_norm

    return a_normalized @ b_normalized.T  # (m, n)


def mmr_select_indices(
    query_embedding,
    doc_embeddings,
    lambda_: float = 0.7,
    top_k: Optional[int] = None,
) -> list[int]:
    """Greedy MMR. Returns selected document INDICES (into doc_embeddings) in selection order.
    - query_embedding: 1D array-like (len dim)
    - doc_embeddings: 2D array-like (n, dim), row i aligned with candidate i
    - lambda_: relevance weight in [0,1]. lambda_=1.0 => pure relevance order (descending sim to query).
               lambda_=0.0 => pure diversity after the first pick.
    - top_k: how many to select; None or >n => select all n.
    Greedy: first pick = argmax relevance. Each subsequent pick = argmax over remaining of
      lambda_*rel[i] - (1-lambda_)*max(sim[i, j] for j in selected).
    Edge cases: n==0 -> []; n==1 -> [0]; never raise on degenerate input."""
    doc_embeddings = np.asarray(doc_embeddings, dtype=float)

    if doc_embeddings.ndim == 1:
        # Treat a single flat array as one document if non-empty, else empty
        if doc_embeddings.size == 0:
            return []
        doc_embeddings = doc_embeddings.reshape(1, -1)

    if doc_embeddings.ndim != 2 or doc_embeddings.shape[0] == 0:
        return []

    n = doc_embeddings.shape[0]

    if top_k is None or top_k > n:
        top_k = n

    if top_k <= 0:
        return []

    query_embedding = np.asarray(query_embedding, dtype=float).reshape(1, -1)

    # rel[i] = cosine(query, doc_i), shape (n,)
    rel = _cosine_matrix(query_embedding, doc_embeddings).reshape(-1)

    # doc-doc similarity matrix, shape (n, n)
    sim = _cosine_matrix(doc_embeddings, doc_embeddings)

    selected: list[int] = []
    remaining: set[int] = set(range(n))

    for _ in range(top_k):
        if not remaining:
            break

        if not selected:
            # First pick: pure relevance
            best = max(remaining, key=lambda i: rel[i])
        else:
            # MMR score for each remaining candidate.
            # Tie-break: prefer candidate with lower max-sim-to-selected (more diverse).
            def mmr_key(i: int) -> tuple:
                max_sim = max(sim[i, j] for j in selected)
                score = lambda_ * rel[i] - (1.0 - lambda_) * max_sim
                return (score, -max_sim)

            best = max(remaining, key=mmr_key)

        selected.append(best)
        remaining.remove(best)

    return selected


def mmr_rerank(
    query_embedding,
    doc_embeddings,
    docs: list,
    lambda_: float = 0.7,
    top_k: Optional[int] = None,
) -> list:
    """Convenience: return `docs` reordered/truncated by mmr_select_indices. len(docs) must == n rows.
    If lengths mismatch or inputs empty -> return docs[:top_k] (safe passthrough)."""
    if not docs:
        return []

    try:
        doc_arr = np.asarray(doc_embeddings, dtype=float)
        if doc_arr.ndim == 2:
            n_rows = doc_arr.shape[0]
        elif doc_arr.ndim == 1 and doc_arr.size == 0:
            n_rows = 0
        else:
            n_rows = -1  # mismatch sentinel
    except Exception:
        n_rows = -1

    if n_rows != len(docs):
        # Mismatch passthrough
        if top_k is not None:
            return docs[:top_k]
        return docs

    indices = mmr_select_indices(
        query_embedding, doc_embeddings, lambda_=lambda_, top_k=top_k
    )
    return [docs[i] for i in indices]
