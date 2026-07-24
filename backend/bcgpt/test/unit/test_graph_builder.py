"""Unit tests for the GraphRAG knowledge-graph (no-DB pure parts)."""

from bcgpt.retrieval.graph.entity_extractor import (
    extract_cooccurrence_entities,
    _guess_entity_type,
)
from bcgpt.retrieval.graph.graph_builder import KnowledgeGraph


def test_cooccurrence_extraction_korean():
    ents = extract_cooccurrence_entities("삼성전자와 미래에셋증권이 협력한다")
    names = [e["entity"] for e in ents]
    assert "삼성전자" in names
    # every result has the required shape
    assert all({"entity", "type", "description"} <= set(e) for e in ents)


def test_cooccurrence_extraction_tickers_and_cap():
    ents = extract_cooccurrence_entities("Compare AAPL and MSFT", max_entities=1)
    assert len(ents) == 1  # cap honored


def test_guess_entity_type():
    assert _guess_entity_type("005930") == "STOCK_CODE"
    assert _guess_entity_type("AAPL") == "TICKER"
    assert _guess_entity_type("삼성전자") == "ENTITY"


def test_empty_text_no_entities():
    assert extract_cooccurrence_entities("") == []
    assert extract_cooccurrence_entities("the of and a") == []  # no named entities


def test_add_entities_creates_cooccurrence_edges():
    kg = KnowledgeGraph()
    kg.add_entities(
        "doc1",
        "c1",
        [{"entity": "삼성전자"}, {"entity": "미래에셋증권"}],
    )
    assert kg.graph.number_of_nodes() == 2
    assert kg.graph.has_edge("삼성전자", "미래에셋증권")
    assert kg.graph["삼성전자"]["미래에셋증권"]["relation"] == "co_occurs"


def test_serialize_deserialize_roundtrip():
    kg = KnowledgeGraph()
    kg.add_entities("doc1", "c1", [{"entity": "A"}, {"entity": "B"}])
    kg.add_entities("doc1", "c2", [{"entity": "B"}, {"entity": "C"}])
    kg.add_relations(
        [{"source": "A", "target": "C", "relation": "rivals", "weight": 0.9}]
    )

    snap = kg.serialize()
    assert isinstance(snap, dict) and "nodes" in snap and "edges" in snap

    kg2 = KnowledgeGraph()
    kg2.deserialize(snap)
    assert kg2.graph.number_of_nodes() == kg.graph.number_of_nodes()
    assert kg2.graph.number_of_edges() == kg.graph.number_of_edges()
    # set-typed attributes restored as sets
    assert isinstance(kg2.graph.nodes["B"]["docs"], set)
    assert "doc1" in kg2.graph.nodes["B"]["docs"]
    # explicit relation preserved
    assert kg2.graph["A"]["C"]["relation"] == "rivals"


def test_deserialize_empty_is_safe():
    kg = KnowledgeGraph()
    kg.deserialize({})
    assert kg.graph.number_of_nodes() == 0


def test_get_entity_context_on_filled_graph():
    kg = KnowledgeGraph()
    kg.add_entities("doc1", "c1", [{"entity": "삼성전자"}, {"entity": "SK"}])
    ctx = kg.get_entity_context(["삼성전자"], max_hops=2)
    assert "삼성전자" in [e["entity"] for e in ctx["entities"]]
    assert "doc1" in ctx["docs"]


# --- 3.2: PPR / community summary / fact-worthiness gate --------------------


def _hub_graph():
    """A graph where 'A' is a hub connected to B, C, D; E is a peripheral leaf."""
    kg = KnowledgeGraph()
    kg.add_entities("d1", "c1", [{"entity": "A"}, {"entity": "B"}])
    kg.add_entities("d1", "c2", [{"entity": "A"}, {"entity": "C"}])
    kg.add_entities("d1", "c3", [{"entity": "A"}, {"entity": "D"}])
    kg.add_entities("d1", "c4", [{"entity": "D"}, {"entity": "E"}])
    return kg


def test_ppr_ranks_seed_and_neighbours_high():
    kg = _hub_graph()
    ranked = kg.personalized_pagerank(["A"], top_k=5)
    assert ranked, "PPR returned nothing on a non-empty graph"
    names = [n for n, _ in ranked]
    assert names[0] == "A"  # the seed scores highest
    # E (2 hops from seed) should rank below the directly-connected B/C/D
    assert names.index("E") > names.index("B")


def test_ppr_empty_when_seed_absent():
    kg = _hub_graph()
    assert kg.personalized_pagerank(["NOT_IN_GRAPH"]) == []
    assert KnowledgeGraph().personalized_pagerank(["A"]) == []  # empty graph


def test_community_summaries_shape():
    kg = _hub_graph()
    summaries = kg.community_summaries(top_n=3)
    assert isinstance(summaries, list)
    for s in summaries:
        assert {"community_id", "size", "top_entities", "summary"} <= set(s)
        assert len(s["top_entities"]) <= 3


def test_prune_isolated_removes_degree_zero():
    kg = KnowledgeGraph()
    kg.add_entities("d1", "c1", [{"entity": "A"}, {"entity": "B"}])  # A-B edge
    kg.add_entities("d1", "c2", [{"entity": "LONE"}])  # single entity, no edge
    assert "LONE" in kg.graph
    removed = kg.prune_isolated(min_docs=1)
    assert removed == 1
    assert "LONE" not in kg.graph
    assert "A" in kg.graph and "B" in kg.graph  # connected entities survive
