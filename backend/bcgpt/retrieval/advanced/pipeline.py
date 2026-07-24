import asyncio
import logging

from fastapi import HTTPException

from bcgpt.config import RAG_EMBEDDING_CONTENT_PREFIX, RAG_EMBEDDING_QUERY_PREFIX
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.mmr import mmr_select_indices
from bcgpt.retrieval.query.expansion import expand_queries
from bcgpt.retrieval.query.hyde import generate_hypothetical_document
from bcgpt.retrieval.query.step_back import generate_step_back_queries
from bcgpt.retrieval.utils import query_collection

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


async def search_with_advanced_pipeline(
    request,
    query: str,
    collection_names: list[str],
    user,
    k: int = 20,
    enable_hyde: bool = False,
    enable_expansion: bool = False,
    enable_step_back: bool = False,
) -> dict:
    queries = [query]

    if enable_hyde:
        try:
            hyde_doc = await generate_hypothetical_document(
                query=query, request=request, user=user
            )
            if hyde_doc:
                queries.append(hyde_doc)
        except Exception as e:
            log.warning(f"HyDE generation failed, skipping: {e}")

    if enable_expansion:
        try:
            expanded = await expand_queries(
                query=query, request=request, user=user, max_expansions=3
            )
            if expanded:
                queries.extend(expanded)
        except Exception as e:
            log.warning(f"Query expansion failed, skipping: {e}")

    if enable_step_back:
        try:
            step_back = await generate_step_back_queries(
                query=query, request=request, user=user
            )
            if step_back:
                queries.extend(step_back)
        except Exception as e:
            log.warning(f"Step-back generation failed, skipping: {e}")

    embedding_function = request.app.state.EMBEDDING_FUNCTION
    if embedding_function is None:
        raise HTTPException(
            status_code=500,
            detail="Embedding model is not configured.",
        )

    def _embed_fn(q, prefix=None):
        return embedding_function(q, prefix=prefix, user=user)

    log.info(
        f"Advanced search: {len(queries)} queries against {len(collection_names)} collections (hyde={enable_hyde}, expansion={enable_expansion}, step_back={enable_step_back})"
    )

    result = await asyncio.to_thread(
        query_collection,
        collection_names=collection_names,
        queries=queries,
        embedding_function=_embed_fn,
        k=k,
    )

    points = []
    if result and result.get("distances") and result["distances"][0]:
        distances = result["distances"][0]
        documents = result["documents"][0] if result.get("documents") else []
        metadatas = result["metadatas"][0] if result.get("metadatas") else []
        for i in range(len(distances)):
            points.append(
                {
                    "id": str(i),
                    "text": documents[i] if i < len(documents) else "",
                    "metadata": metadatas[i] if i < len(metadatas) else {},
                    "score": distances[i],
                }
            )

    # MMR diversity reranking: greedily trade relevance for novelty to avoid
    # near-duplicate top-k. Embeddings are not retained by query_collection, so
    # the query and candidate docs are re-embedded here. Disabled => no change.
    if request.app.state.config.RAG_MMR_ENABLED and len(points) > 1:
        try:
            lambda_ = float(request.app.state.config.RAG_MMR_LAMBDA)
            query_vec = _embed_fn(query, prefix=RAG_EMBEDDING_QUERY_PREFIX)
            doc_vecs = _embed_fn(
                [p["text"] for p in points], prefix=RAG_EMBEDDING_CONTENT_PREFIX
            )
            order = mmr_select_indices(query_vec, doc_vecs, lambda_=lambda_, top_k=k)
            if order:
                points = [points[i] for i in order]
        except Exception as e:
            log.warning(f"MMR reranking failed, keeping original order: {e}")

    return {"points": points}
