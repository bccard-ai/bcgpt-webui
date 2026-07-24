"""Vector search and collection-query functions.

Public API
----------
* ``VectorSearchRetriever``    – LangChain ``BaseRetriever`` adapter
* ``query_doc``                – single-collection vector search
* ``get_doc``                  – fetch all items from a collection
* ``query_doc_with_hybrid_search`` – BM25 + vector + rerank for one collection
* ``query_collection``         – multi-collection, multi-query vector search
* ``query_collection_with_hybrid_search`` – multi-collection hybrid search
* ``merge_get_results``        – combine raw ``GetResult`` dicts
* ``merge_and_sort_query_results`` – deduplicate, sort, diversity-cap
* ``get_all_items_from_collections`` – fetch + merge all items
"""

from __future__ import annotations

import hashlib
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from langchain_community.retrievers import BM25Retriever
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from bcgpt.config import RAG_EMBEDDING_QUERY_PREFIX, RAG_EMBEDDING_CONTENT_PREFIX
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import UserModel
from bcgpt.retrieval.vector.connector import VECTOR_DB_CLIENT
from bcgpt.retrieval.vector.main import GetResult, SearchResult
from bcgpt.retrieval.rrf import rrf_fuse

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


# ---------------------------------------------------------------------------
# LangChain retriever adapter
# ---------------------------------------------------------------------------


class VectorSearchRetriever(BaseRetriever):
    """Thin LangChain ``BaseRetriever`` that delegates to ``VECTOR_DB_CLIENT``."""

    collection_name: Any
    embedding_function: Any
    top_k: int

    def _get_relevant_documents(
        self,
        query: str,
        *,
        run_manager: CallbackManagerForRetrieverRun,
    ) -> list[Document]:
        result = VECTOR_DB_CLIENT.search(
            collection_name=self.collection_name,
            vectors=[self.embedding_function(query, RAG_EMBEDDING_QUERY_PREFIX)],
            limit=self.top_k,
        )

        ids = result.ids[0]
        metadatas = result.metadatas[0]
        documents = result.documents[0]

        return [
            Document(metadata=metadatas[idx], page_content=documents[idx])
            for idx in range(len(ids))
        ]


# ---------------------------------------------------------------------------
# Single-collection queries
# ---------------------------------------------------------------------------


def query_doc(
    collection_name: str,
    query_embedding: list[float],
    k: int,
    user: UserModel | None = None,
) -> SearchResult | None:
    """Vector-search a single collection and optionally resolve parent chunks."""
    try:
        result = VECTOR_DB_CLIENT.search(
            collection_name=collection_name,
            vectors=[query_embedding],
            limit=k,
        )

        if result:
            log.info("query_doc:result %s %s", result.ids, result.metadatas)

            if (
                result.metadatas
                and result.metadatas[0]
                and any(m.get("chunk_type") == "child" for m in result.metadatas[0])
            ):
                from bcgpt.retrieval.parent_child import replace_children_with_parents

                distances = result.distances[0] if result.distances else []
                documents = result.documents[0] if result.documents else []
                metadatas = result.metadatas[0] if result.metadatas else []

                resolved_d, resolved_doc, resolved_meta = replace_children_with_parents(
                    distances, documents, metadatas, collection_name
                )
                return SearchResult(
                    ids=[["resolved"] * len(resolved_d)],
                    documents=[resolved_doc],
                    metadatas=[resolved_meta],
                    distances=[resolved_d],
                )

        return result
    except Exception as exc:
        log.exception(
            "Error querying doc %s with limit %d: %s", collection_name, k, exc
        )
        raise


def get_doc(collection_name: str, user: UserModel | None = None):
    """Retrieve all items stored in *collection_name*."""
    try:
        result = VECTOR_DB_CLIENT.get(collection_name=collection_name)
        if result:
            log.info("get_doc:result %s %s", result.ids, result.metadatas)
        return result
    except Exception as exc:
        log.exception("Error getting doc %s: %s", collection_name, exc)
        raise


# ---------------------------------------------------------------------------
# Hybrid search (single collection)
# ---------------------------------------------------------------------------


def query_doc_with_hybrid_search(
    collection_name: str,
    collection_result: GetResult,
    query: str,
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
    rrf_k: int = 60,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> dict:
    """BM25 + vector search with RRF fusion and optional reranking."""
    try:
        documents = (
            collection_result.documents[0] if collection_result.documents else []
        )
        metadatas = (
            collection_result.metadatas[0] if collection_result.metadatas else []
        )

        if not documents:
            log.debug(
                "query_doc_with_hybrid_search: no documents in '%s', returning empty",
                collection_name,
            )
            return {"distances": [[]], "documents": [[]], "metadatas": [[]]}

        # BM25 track
        bm25_retriever = BM25Retriever.from_texts(texts=documents, metadatas=metadatas)
        bm25_retriever.k = k
        bm25_docs = bm25_retriever.invoke(query)

        # Vector track
        vector_retriever = VectorSearchRetriever(
            collection_name=collection_name,
            embedding_function=embedding_function,
            top_k=k,
        )
        vector_docs = vector_retriever.invoke(query)

        # Fuse via RRF
        bm25_results = [
            {"page_content": d.page_content, "metadata": d.metadata} for d in bm25_docs
        ]
        vector_results = [
            {"page_content": d.page_content, "metadata": d.metadata}
            for d in vector_docs
        ]

        fused = rrf_fuse(
            track_results=[vector_results, bm25_results],
            weights=[vector_weight, keyword_weight],
            k=rrf_k,
            top_n=k_reranker,
        )

        fused_documents = [
            Document(page_content=r.content, metadata=r.metadata) for r in fused
        ]

        # Rerank
        from bcgpt.retrieval.reranking.compressor import RerankCompressor

        compressor = RerankCompressor(
            embedding_function=embedding_function,
            top_n=k_reranker,
            reranking_function=reranking_function,
            r_score=r,
        )
        result = compressor.compress_documents(fused_documents, query)

        distances = [d.metadata.get("score") for d in result]
        documents = [d.page_content for d in result]
        metadatas = [d.metadata for d in result]

        if k < k_reranker:
            sorted_items = sorted(
                zip(distances, metadatas, documents), key=lambda x: x[0], reverse=True
            )
            sorted_items = sorted_items[:k]
            distances, documents, metadatas = map(list, zip(*sorted_items))

        result_dict = {
            "distances": [distances],
            "documents": [documents],
            "metadatas": [metadatas],
        }
        log.info(
            "query_doc_with_hybrid_search:result %s %s",
            result_dict["metadatas"],
            result_dict["distances"],
        )
        return result_dict
    except Exception as exc:
        raise


# ---------------------------------------------------------------------------
# Result merging utilities
# ---------------------------------------------------------------------------


def merge_get_results(get_results: list[dict]) -> dict:
    """Combine multiple raw ``GetResult``-style dicts into one."""
    combined_documents: list = []
    combined_metadatas: list = []
    combined_ids: list = []

    for data in get_results:
        combined_documents.extend(data["documents"][0])
        combined_metadatas.extend(data["metadatas"][0])
        combined_ids.extend(data["ids"][0])

    return {
        "documents": [combined_documents],
        "metadatas": [combined_metadatas],
        "ids": [combined_ids],
    }


def merge_and_sort_query_results(
    query_results: list[dict],
    k: int,
    max_per_source: int = 3,
) -> dict:
    """Deduplicate, sort by score, and apply per-source diversity cap."""
    combined: dict[str, tuple] = {}

    for data in query_results:
        # Tolerate missing / flat-shaped source results (a source may legitimately
        # return ``{}`` or a non-nested list) without raising IndexError.
        distances = (data.get("distances") or [[]])[0]
        documents = (data.get("documents") or [[]])[0]
        metadatas = (data.get("metadatas") or [[]])[0]

        for distance, document, metadata in zip(distances, documents, metadatas):
            if not isinstance(document, str):
                continue

            doc_hash = hashlib.sha256(document.encode()).hexdigest()
            if doc_hash not in combined:
                combined[doc_hash] = (distance, document, metadata)
            elif distance > combined[doc_hash][0]:
                combined[doc_hash] = (distance, document, metadata)

    items = list(combined.values())
    items.sort(key=lambda x: x[0], reverse=True)

    # Diversity cap: limit results per source file
    if max_per_source > 0:
        source_counts: dict[str, int] = {}
        diversified = []
        for entry in items:
            meta = entry[2]
            source_id = (
                (meta.get("file_id") or meta.get("source", ""))
                if isinstance(meta, dict)
                else ""
            )
            count = source_counts.get(source_id, 0)
            if count < max_per_source:
                diversified.append(entry)
                source_counts[source_id] = count + 1
        items = diversified

    if not items:
        return {"distances": [[]], "documents": [[]], "metadatas": [[]]}

    sorted_distances, sorted_documents, sorted_metadatas = zip(*items[:k])
    return {
        "distances": [list(sorted_distances)],
        "documents": [list(sorted_documents)],
        "metadatas": [list(sorted_metadatas)],
    }


# ---------------------------------------------------------------------------
# Multi-collection queries
# ---------------------------------------------------------------------------


def get_all_items_from_collections(collection_names: list[str]) -> dict:
    """Fetch and merge all items from the given collections."""
    results: list[dict] = []
    for name in collection_names:
        if not name:
            continue
        try:
            result = get_doc(collection_name=name)
            if result is not None:
                results.append(result.model_dump())
        except Exception as exc:
            log.exception("Error querying collection %s: %s", name, exc)
    return merge_get_results(results)


def query_collection(
    collection_names: list[str],
    queries: list[str],
    embedding_function,
    k: int,
) -> dict:
    """Pure vector search across multiple collections and queries."""
    results: list[dict] = []
    for query in queries:
        query_embedding = embedding_function(query, prefix=RAG_EMBEDDING_QUERY_PREFIX)
        for name in collection_names:
            if not name:
                continue
            try:
                result = query_doc(
                    collection_name=name,
                    k=k,
                    query_embedding=query_embedding,
                )
                if result is not None:
                    results.append(result.model_dump())
            except Exception as exc:
                log.exception("Error querying collection %s: %s", name, exc)

    return merge_and_sort_query_results(results, k=k)


def query_corpus(
    *,
    corpus_name: str,
    queries: list[str],
    embedding_function,
    k: int,
    knowledge_ids: list[str] | None = None,
    file_ids: list[str] | None = None,
    workspace_id: str | None = None,
) -> dict:
    """Filtered vector search over the shared corpus collection (P1.3).

    A single approximate-nearest-neighbour pass per query, constrained by a
    metadata filter: ``knowledge_id IN (allowed KBs)`` and/or ``file_id IN (...)``
    and/or ``workspace_id = ...``. Replaces the per-collection Python loop in
    :func:`query_collection` when ``RAG_USE_CORPUS`` is on. Backend must support
    :meth:`search_filtered` (Qdrant does); falls back to empty if it does not.

    NOTE: vector-only. Hybrid (BM25 + vector + rerank) over a filtered corpus
    subset is a follow-up — under ``RAG_USE_CORPUS`` a hybrid request currently
    still resolves via this vector-filtered path.
    """
    if not hasattr(VECTOR_DB_CLIENT, "search_filtered"):
        log.warning(
            "query_corpus: backend has no search_filtered; skipping (corpus=%s)",
            corpus_name,
        )
        return merge_and_sort_query_results([], k=k)

    conditions: list[tuple[str, object]] = []
    if knowledge_ids:
        conditions.append(("knowledge_id", knowledge_ids))
    if file_ids:
        conditions.append(("file_id", file_ids))
    if workspace_id:
        conditions.append(("workspace_id", workspace_id))

    results: list[dict] = []
    for query in queries:
        query_embedding = embedding_function(query, prefix=RAG_EMBEDDING_QUERY_PREFIX)
        try:
            result = VECTOR_DB_CLIENT.search_filtered(
                collection_name=corpus_name,
                vectors=[query_embedding],
                conditions=conditions,
                limit=k,
            )
            if result is not None:
                results.append(result.model_dump())
        except Exception as exc:
            log.exception("Error querying corpus %s: %s", corpus_name, exc)
    return merge_and_sort_query_results(results, k=k)


def query_collection_with_hybrid_search(
    collection_names: list[str],
    queries: list[str],
    embedding_function,
    k: int,
    reranking_function,
    k_reranker: int,
    r: float,
    rrf_k: int = 60,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> dict:
    """Hybrid (BM25 + vector + rerank) search across collections and queries.

    Collection data is fetched once per collection, then searches run in
    parallel via ``ThreadPoolExecutor``.
    """
    results: list[dict] = []
    error = False

    # Pre-fetch collection data to avoid redundant network calls
    collection_cache: dict[str, Any] = {}
    for name in collection_names:
        try:
            collection_cache[name] = VECTOR_DB_CLIENT.get(collection_name=name)
        except Exception as exc:
            log.exception("Failed to fetch collection %s: %s", name, exc)
            collection_cache[name] = None

    log.info(
        "Starting hybrid search for %d queries in %d collections…",
        len(queries),
        len(collection_names),
    )

    def _process(name: str, query: str):
        try:
            result = query_doc_with_hybrid_search(
                collection_name=name,
                collection_result=collection_cache[name],
                query=query,
                embedding_function=embedding_function,
                k=k,
                reranking_function=reranking_function,
                k_reranker=k_reranker,
                r=r,
                rrf_k=rrf_k,
                vector_weight=vector_weight,
                keyword_weight=keyword_weight,
            )
            return result, None
        except Exception as exc:
            log.exception("Hybrid search error for %s: %s", name, exc)
            return None, exc

    tasks = [(name, q) for name in collection_names for q in queries]

    with ThreadPoolExecutor() as executor:
        future_results = [executor.submit(_process, n, q) for n, q in tasks]
        task_results = [f.result() for f in future_results]

    for result, err in task_results:
        if err is not None:
            error = True
        elif result is not None:
            results.append(result)

    if error and not results:
        raise Exception(
            "Hybrid search failed for all collections. Using Non-hybrid search as fallback."
        )

    return merge_and_sort_query_results(results, k=k)
