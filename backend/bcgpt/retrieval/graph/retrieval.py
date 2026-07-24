import logging

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.graph.entity_extractor import extract_cooccurrence_entities
from bcgpt.retrieval.graph.graph_builder import get_knowledge_graph

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])


def _community_boost(query_entities: list[str], communities: list[frozenset]) -> float:
    if not query_entities or not communities:
        return 0.0
    qset = set(e.lower() for e in query_entities)
    max_overlap = 0.0
    for comm in communities:
        comm_lower = {e.lower() for e in comm}
        overlap = len(qset & comm_lower) / len(qset) if qset else 0.0
        max_overlap = max(max_overlap, overlap)
    return max_overlap


async def graph_enhanced_retrieval(
    query: str,
    documents: list[dict],
    request,
    user,
    config: dict | None = None,
) -> list[dict]:
    if config is None:
        config = {}

    kg = get_knowledge_graph()

    if kg.graph.number_of_nodes() == 0 or not documents:
        for doc in documents:
            doc.setdefault("metadata", {})
            doc["metadata"]["graph_context"] = None
        return documents

    # Use the same deterministic extractor as ingest so query entity names align
    # with the persisted graph node names (and avoid a per-query LLM call).
    try:
        query_entities_raw = extract_cooccurrence_entities(query)
    except Exception as e:
        log.warning(f"GraphRAG query entity extraction failed: {e}")
        query_entities_raw = []

    query_entity_names = [e["entity"] for e in query_entities_raw]

    if not query_entity_names:
        for doc in documents:
            doc.setdefault("metadata", {})
            doc["metadata"]["graph_context"] = None
        return documents

    entity_context = kg.get_entity_context(
        query_entity_names, max_hops=config.get("max_hops", 2)
    )

    communities = kg.detect_communities()
    community_score = _community_boost(query_entity_names, communities)

    # Personalized PageRank: rank entities by proximity-weighted centrality from
    # the query subject (HippoRAG, 3.2). PPR mass becomes a per-doc relevance
    # signal; falls back to the BFS entity context when disabled/empty.
    ppr_scores: dict[str, float] = {}
    if config.get("ppr_enabled", True):
        ranked = kg.personalized_pagerank(
            query_entity_names, top_k=config.get("ppr_top_k", 20)
        )
        ppr_scores = {name: score for name, score in ranked}
    total_ppr = sum(ppr_scores.values()) or 1.0

    related_entities = (
        list(ppr_scores.keys())
        if ppr_scores
        else [e["entity"] for e in entity_context.get("entities", [])]
    )

    for doc in documents:
        doc.setdefault("metadata", {})
        content = doc.get("text", doc.get("content", ""))
        content_lower = content.lower()

        doc_entity_overlap = 0.0
        for ent_name in query_entity_names:
            if ent_name.lower() in content_lower:
                doc_entity_overlap += 1.0
        if query_entity_names:
            doc_entity_overlap /= len(query_entity_names)

        # PPR-weighted presence of related entities in the document.
        ppr_doc_score = 0.0
        if ppr_scores:
            for ent_name, score in ppr_scores.items():
                if ent_name.lower() in content_lower:
                    ppr_doc_score += score
            ppr_doc_score /= total_ppr

        boost = (
            0.5 * doc_entity_overlap
            + 0.25 * ppr_doc_score
            + 0.15 * community_score
            + 0.1
            * min(
                len(entity_context.get("entities", []))
                / max(len(query_entity_names), 1),
                1.0,
            )
        )

        original_score = doc.get("score", 0.0)
        if isinstance(original_score, (int, float)):
            doc["score"] = original_score * (1.0 + boost)

        doc["metadata"]["graph_context"] = {
            "query_entities": query_entity_names,
            "related_entities": related_entities[:20],
            "ppr_top": [
                name
                for name, _ in sorted(
                    ppr_scores.items(), key=lambda kv: kv[1], reverse=True
                )[:5]
            ],
            "community_score": community_score,
            "entity_overlap": doc_entity_overlap,
            "ppr_doc_score": ppr_doc_score,
            "boost": boost,
        }

    documents.sort(key=lambda d: d.get("score", 0.0), reverse=True)
    return documents
