"""RAG_SEARCH node: retrieve relevant documents from knowledge collections.

Integrates with BCGPT's vector store via ``query_collection`` /
``query_collection_with_hybrid_search``. Best-effort: if the embedding function
or collections are unavailable it returns an empty result set (and the node's
``error_strategy: continue`` keeps the workflow going) rather than crashing.
"""

from __future__ import annotations

import logging

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.state import (
    ExecutionContext,
    NodeResult,
    WorkflowNode,
    WorkflowState,
)

log = logging.getLogger(__name__)


def _to_sources(result: dict) -> list[dict]:
    """Flatten a query_collection result into a list of source dicts."""
    sources: list[dict] = []
    if not isinstance(result, dict):
        return sources
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    distances = result.get("distances") or []
    for q_idx, docs in enumerate(documents):
        metas = metadatas[q_idx] if q_idx < len(metadatas) else []
        dists = distances[q_idx] if q_idx < len(distances) else []
        for d_idx, doc in enumerate(docs or []):
            sources.append(
                {
                    "document": doc,
                    "metadata": metas[d_idx] if d_idx < len(metas) else {},
                    "distance": dists[d_idx] if d_idx < len(dists) else None,
                    "source_type": "rag",
                }
            )
    return sources


class RAGSearchHandler(NodeHandler):
    async def execute(
        self, node: WorkflowNode, state: WorkflowState, context: ExecutionContext
    ) -> NodeResult:
        query = state.user_input
        collection_ids = node.config.get("collection_ids") or []
        top_k = int(node.config.get("top_k", 5))

        if not query or not collection_ids or context.request is None:
            return NodeResult(output=[], metadata={"count": 0, "skipped": True})

        await context.emit(
            {"type": "status", "data": {"action": "rag_search", "query": query}}
        )

        try:
            embedding_function = getattr(
                context.request.app.state, "EMBEDDING_FUNCTION", None
            )
            if embedding_function is None:
                log.info("RAG_SEARCH: no EMBEDDING_FUNCTION on app.state; skipping")
                return NodeResult(output=[], metadata={"count": 0, "skipped": True})

            from bcgpt.retrieval import query_collection

            result = query_collection(
                collection_names=list(collection_ids),
                queries=[query],
                embedding_function=embedding_function,
                k=top_k,
            )
            sources = _to_sources(result)
            return NodeResult(
                output=sources,
                metadata={"count": len(sources), "sources": sources},
            )
        except Exception as e:  # noqa: BLE001 - best-effort retrieval
            log.warning("RAG_SEARCH failed: %s", e)
            return NodeResult(output=[], metadata={"count": 0, "error": str(e)})
