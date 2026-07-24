import logging
import threading
from collections import deque

import networkx as nx
from networkx.algorithms import community

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# Serializes graph build + persistence so concurrent ingests don't corrupt the
# shared in-memory graph or race on the single DB row.
_build_lock = threading.Lock()


class KnowledgeGraph:
    def __init__(self):
        self.graph = nx.Graph()
        self._entity_docs: dict[str, set[str]] = {}
        self._communities: list[frozenset] = []
        self._communities_stale = True

    def add_entities(self, doc_id: str, chunk_id: str, entities: list[dict]) -> None:
        names = []
        for ent in entities:
            name = ent["entity"]
            etype = ent.get("type", "UNKNOWN")
            desc = ent.get("description", "")

            if name not in self.graph:
                self.graph.add_node(
                    name, type=etype, description=desc, docs=set(), chunks=set()
                )
            self.graph.nodes[name]["docs"].add(doc_id)
            self.graph.nodes[name]["chunks"].add(chunk_id)
            names.append(name)

            if name not in self._entity_docs:
                self._entity_docs[name] = set()
            self._entity_docs[name].add(doc_id)

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                if self.graph.has_edge(a, b):
                    self.graph[a][b]["weight"] += 1.0
                    self.graph[a][b]["co_occurrence_chunks"].add(chunk_id)
                else:
                    self.graph.add_edge(
                        a,
                        b,
                        weight=1.0,
                        relation="co_occurs",
                        co_occurrence_chunks={chunk_id},
                    )

        self._communities_stale = True

    def add_relations(self, relations: list[dict]) -> None:
        for rel in relations:
            source = rel["source"]
            target = rel["target"]
            weight = rel.get("weight", 0.5)
            relation = rel.get("relation", "related_to")

            if source not in self.graph:
                self.graph.add_node(
                    source, type="UNKNOWN", description="", docs=set(), chunks=set()
                )
            if target not in self.graph:
                self.graph.add_node(
                    target, type="UNKNOWN", description="", docs=set(), chunks=set()
                )

            if self.graph.has_edge(source, target):
                self.graph[source][target]["weight"] = max(
                    self.graph[source][target]["weight"], weight
                )
            else:
                self.graph.add_edge(source, target, weight=weight, relation=relation)

        self._communities_stale = True

    def get_entity_context(self, query_entities: list[str], max_hops: int = 2) -> dict:
        if not query_entities:
            return {"entities": [], "relations": [], "docs": [], "context_text": ""}

        visited_nodes = set()
        visited_edges = set()
        doc_ids = set()

        for seed in query_entities:
            if seed not in self.graph:
                continue
            queue = deque([(seed, 0)])
            seen = {seed}

            while queue:
                node, depth = queue.popleft()
                visited_nodes.add(node)

                if "docs" in self.graph.nodes[node]:
                    doc_ids.update(self.graph.nodes[node]["docs"])

                if depth < max_hops:
                    for neighbor in self.graph.neighbors(node):
                        edge = tuple(sorted((node, neighbor)))
                        visited_edges.add(edge)
                        if neighbor not in seen:
                            seen.add(neighbor)
                            queue.append((neighbor, depth + 1))

        entity_info = []
        for node in visited_nodes:
            data = self.graph.nodes[node]
            entity_info.append(
                {
                    "entity": node,
                    "type": data.get("type", "UNKNOWN"),
                    "description": data.get("description", ""),
                }
            )

        relation_info = []
        for a, b in visited_edges:
            if self.graph.has_edge(a, b):
                edge_data = self.graph[a][b]
                relation_info.append(
                    {
                        "source": a,
                        "target": b,
                        "relation": edge_data.get("relation", "related_to"),
                        "weight": edge_data.get("weight", 0.0),
                    }
                )

        context_parts = []
        for ent in entity_info:
            context_parts.append(
                f"{ent['entity']} ({ent['type']}): {ent['description']}"
            )
        for rel in relation_info:
            context_parts.append(
                f"{rel['source']} --[{rel['relation']}]--> {rel['target']}"
            )

        return {
            "entities": entity_info,
            "relations": relation_info,
            "docs": list(doc_ids),
            "context_text": "\n".join(context_parts),
        }

    def detect_communities(self) -> list[frozenset]:
        if self._communities_stale:
            if self.graph.number_of_nodes() == 0:
                self._communities = []
            else:
                self._communities = list(
                    community.greedy_modularity_communities(self.graph)
                )
            self._communities_stale = False
        return self._communities

    def get_community_for_entity(self, entity: str) -> frozenset | None:
        communities = self.detect_communities()
        for comm in communities:
            if entity in comm:
                return comm
        return None

    # ── Personalized PageRank (HippoRAG, 3.2) ──────────────────────────────

    def personalized_pagerank(
        self,
        seed_entities: list[str],
        top_k: int | None = None,
        alpha: float = 0.85,
    ) -> list[tuple[str, float]]:
        """Rank graph nodes by Personalized PageRank seeded on query entities.

        Restarts the random walk from the seed entities so structurally-central
        nodes *near the query subject* score highest (HippoRAG NeurIPS'24).
        Returns ``[(entity, score), ...]`` sorted desc. Empty if no seed is in
        the graph.
        """
        seeds = [e for e in seed_entities if e in self.graph]
        if not seeds or self.graph.number_of_nodes() == 0:
            return []
        personalization = {n: 0.0 for n in self.graph.nodes}
        for s in seeds:
            personalization[s] = 1.0
        try:
            scores = nx.pagerank(
                self.graph,
                alpha=alpha,
                personalization=personalization,
                weight="weight",
            )
        except Exception as e:  # power-iteration may fail to converge
            log.warning("PPR failed: %s", e)
            return []
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked[:top_k] if top_k else ranked

    def community_summaries(self, top_n: int = 5) -> list[dict]:
        """Deterministic structural summary per community: the highest-degree
        member entities (no LLM). Useful as compact graph context."""
        communities = self.detect_communities()
        summaries = []
        for i, comm in enumerate(communities):
            members = sorted(
                comm,
                key=lambda n: self.graph.degree(n, weight="weight"),
                reverse=True,
            )
            top = members[:top_n]
            summaries.append(
                {
                    "community_id": i,
                    "size": len(comm),
                    "top_entities": top,
                    "summary": ", ".join(top),
                }
            )
        return summaries

    def prune_isolated(self, min_docs: int = 1) -> int:
        """Deterministic fact-worthiness gate: drop entities that never co-occur
        (degree 0) or appear in fewer than ``min_docs`` documents. Returns the
        number of nodes removed."""
        to_remove = []
        for node, data in self.graph.nodes(data=True):
            degree = self.graph.degree(node)
            doc_count = len(data.get("docs", set()))
            if degree == 0 or doc_count < min_docs:
                to_remove.append(node)
        for node in to_remove:
            self.graph.remove_node(node)
            self._entity_docs.pop(node, None)
        if to_remove:
            self._communities_stale = True
        return len(to_remove)

    def clear(self) -> None:
        self.graph = nx.Graph()
        self._entity_docs = {}
        self._communities = []
        self._communities_stale = True

    # ── Persistence (3.1) ──────────────────────────────────────────────────
    # Sets aren't JSON-serializable, so node/edge set attributes are stored as
    # sorted lists and restored to sets on load.

    def serialize(self) -> dict:
        """Return a JSON-safe snapshot of the graph."""
        nodes = []
        for name, data in self.graph.nodes(data=True):
            nodes.append(
                {
                    "id": name,
                    "type": data.get("type", "UNKNOWN"),
                    "description": data.get("description", ""),
                    "docs": sorted(data.get("docs", set())),
                    "chunks": sorted(data.get("chunks", set())),
                }
            )
        edges = []
        for a, b, data in self.graph.edges(data=True):
            edge = {
                "source": a,
                "target": b,
                "weight": data.get("weight", 1.0),
                "relation": data.get("relation", "related_to"),
            }
            if "co_occurrence_chunks" in data:
                edge["co_occurrence_chunks"] = sorted(data["co_occurrence_chunks"])
            edges.append(edge)
        return {
            "nodes": nodes,
            "edges": edges,
            "entity_docs": {k: sorted(v) for k, v in self._entity_docs.items()},
        }

    def deserialize(self, data: dict) -> None:
        """Rebuild the graph from a :meth:`serialize` snapshot."""
        self.clear()
        if not data:
            return
        for n in data.get("nodes", []):
            self.graph.add_node(
                n["id"],
                type=n.get("type", "UNKNOWN"),
                description=n.get("description", ""),
                docs=set(n.get("docs", [])),
                chunks=set(n.get("chunks", [])),
            )
        for e in data.get("edges", []):
            attrs = {
                "weight": e.get("weight", 1.0),
                "relation": e.get("relation", "related_to"),
            }
            if "co_occurrence_chunks" in e:
                attrs["co_occurrence_chunks"] = set(e["co_occurrence_chunks"])
            self.graph.add_edge(e["source"], e["target"], **attrs)
        self._entity_docs = {
            k: set(v) for k, v in (data.get("entity_docs") or {}).items()
        }
        self._communities_stale = True

    def save_to_db(self, scope: str = "global") -> bool:
        from bcgpt.models.knowledge_graph import KnowledgeGraphStores

        return KnowledgeGraphStores.save(scope, self.serialize())

    def load_from_db(self, scope: str = "global") -> bool:
        from bcgpt.models.knowledge_graph import KnowledgeGraphStores

        data = KnowledgeGraphStores.load(scope)
        if data:
            self.deserialize(data)
            return True
        return False


_knowledge_graph: KnowledgeGraph | None = None


def get_knowledge_graph() -> KnowledgeGraph:
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = KnowledgeGraph()
    return _knowledge_graph


def load_graph_from_db(scope: str = "global") -> int:
    """Load the persisted graph into the in-memory singleton (startup). Returns
    the resulting node count."""
    kg = get_knowledge_graph()
    with _build_lock:
        try:
            kg.load_from_db(scope)
        except Exception as e:
            log.warning("GraphRAG load_from_db failed: %s", e)
    return kg.graph.number_of_nodes()


def build_graph_from_chunks(
    doc_id: str,
    chunk_ids: list[str],
    texts: list[str],
    max_entities_per_chunk: int | None = None,
    min_entity_docs: int = 0,
    scope: str = "global",
) -> int:
    """Deterministic (no-LLM) co-occurrence graph build from ingested chunks.

    Extracts named entities per chunk (reusing the regex entity extractor) and
    records co-occurrence edges, applies a deterministic fact-worthiness gate
    (``prune_isolated``), then persists the graph. Thread-safe. Returns the
    resulting node count.
    """
    from bcgpt.retrieval.graph.entity_extractor import extract_cooccurrence_entities

    kg = get_knowledge_graph()
    with _build_lock:
        for chunk_id, text in zip(chunk_ids, texts):
            entities = extract_cooccurrence_entities(
                text, max_entities=max_entities_per_chunk
            )
            if entities:
                kg.add_entities(doc_id, chunk_id, entities)
        # Fact-worthiness gate (3.2): drop isolated / low-frequency entities.
        if min_entity_docs and min_entity_docs > 0:
            kg.prune_isolated(min_docs=min_entity_docs)
        kg.save_to_db(scope)
    return kg.graph.number_of_nodes()
