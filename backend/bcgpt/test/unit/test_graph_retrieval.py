"""Unit tests for the GraphRAG retrieval layer (open-moai adoption 3.1/3.2).

The ``KnowledgeGraph`` class itself is covered by ``test_graph_builder.py``. These
tests lock the *retrieval* layer in ``retrieval/graph/retrieval.py``:

  * ``_community_boost`` -- the pure community-overlap helper (case-insensitive,
    takes the max over communities, empty-safe).
  * ``graph_enhanced_retrieval`` -- end-to-end scoring/rerank. With
    ``get_knowledge_graph`` and ``extract_cooccurrence_entities`` monkeypatched, a
    document containing a query entity receives a strictly higher score boost than
    one that does not, ``graph_context`` metadata is populated, and documents are
    re-sorted by the boosted score. Empty-graph / no-entity short-circuits are
    also locked.

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_graph_retrieval.py -q
"""

from __future__ import annotations

import asyncio

from bcgpt.retrieval.graph import retrieval as gretrieval
from bcgpt.retrieval.graph.graph_builder import KnowledgeGraph
from bcgpt.retrieval.graph.retrieval import _community_boost, graph_enhanced_retrieval

# ---------------------------------------------------------------------------
# _community_boost -- pure helper
# ---------------------------------------------------------------------------


def test_community_boost_empty_query():
    assert _community_boost([], [frozenset({"a"})]) == 0.0


def test_community_boost_empty_communities():
    assert _community_boost(["a"], []) == 0.0


def test_community_boost_full_overlap():
    assert _community_boost(["a", "b"], [frozenset({"a", "b", "c"})]) == 1.0


def test_community_boost_partial_overlap():
    # query {a,b} vs community {a,x} -> intersection {a} / query 2 = 0.5
    assert _community_boost(["a", "b"], [frozenset({"a", "x"})]) == 0.5


def test_community_boost_takes_max_over_communities():
    communities = [frozenset({"a"}), frozenset({"a", "b"})]
    assert _community_boost(["a", "b"], communities) == 1.0


def test_community_boost_case_insensitive():
    assert _community_boost(["AAPL"], [frozenset({"aapl"})]) == 1.0


# ---------------------------------------------------------------------------
# graph_enhanced_retrieval -- scoring + rerank (kg + extractor monkeypatched)
# ---------------------------------------------------------------------------


def _kg_with_entities() -> KnowledgeGraph:
    kg = KnowledgeGraph()
    kg.add_entities(
        "doc-1",
        "chunk-1",
        [
            {"entity": "AAPL", "type": "TICKER", "description": "Apple"},
            {"entity": "GOOG", "type": "TICKER", "description": "Alphabet"},
        ],
    )
    return kg


def _run(query, documents, config=None):
    return asyncio.run(
        graph_enhanced_retrieval(query, documents, None, None, config=config or {})
    )


def test_empty_graph_passes_documents_through(monkeypatch):
    """An empty graph short-circuits: documents tagged graph_context=None, score unchanged."""
    monkeypatch.setattr(gretrieval, "get_knowledge_graph", lambda: KnowledgeGraph())
    docs = [{"id": "d1", "text": "anything", "score": 0.5}]
    out = _run("AAPL", docs)
    assert out[0]["metadata"]["graph_context"] is None
    assert out[0]["score"] == 0.5


def test_no_query_entities_passes_through(monkeypatch):
    """When extraction yields no entities, documents are returned tagged None."""
    monkeypatch.setattr(gretrieval, "get_knowledge_graph", lambda: _kg_with_entities())
    monkeypatch.setattr(gretrieval, "extract_cooccurrence_entities", lambda text: [])
    docs = [{"id": "d1", "text": "text", "score": 0.5}]
    out = _run("nothing here", docs)
    assert out[0]["metadata"]["graph_context"] is None
    assert out[0]["score"] == 0.5


def test_doc_with_entity_outscores_doc_without(monkeypatch):
    """A document containing a query entity gets a strictly higher boosted score
    and is re-sorted to the front."""
    monkeypatch.setattr(gretrieval, "get_knowledge_graph", lambda: _kg_with_entities())
    # Decouple from the regex extractor: both AAPL and GOOG exist in the graph.
    monkeypatch.setattr(
        gretrieval,
        "extract_cooccurrence_entities",
        lambda text: [{"entity": "AAPL"}, {"entity": "GOOG"}],
    )
    documents = [
        {
            "id": "no-entity",
            "text": "a completely unrelated prose paragraph",
            "score": 0.5,
        },
        {"id": "with-entity", "text": "AAPL announced record earnings", "score": 0.5},
    ]
    out = _run("AAPL GOOG", documents)
    assert out[0]["id"] == "with-entity"
    assert out[0]["score"] > out[1]["score"]


def test_graph_context_metadata_populated(monkeypatch):
    monkeypatch.setattr(gretrieval, "get_knowledge_graph", lambda: _kg_with_entities())
    monkeypatch.setattr(
        gretrieval,
        "extract_cooccurrence_entities",
        lambda text: [{"entity": "AAPL"}, {"entity": "GOOG"}],
    )
    documents = [{"id": "d1", "text": "AAPL earnings beat", "score": 0.4}]
    out = _run("AAPL GOOG", documents)
    ctx = out[0]["metadata"]["graph_context"]
    assert ctx is not None
    assert ctx["query_entities"] == ["AAPL", "GOOG"]
    assert ctx["boost"] > 0.0
    assert ctx["entity_overlap"] > 0.0  # AAPL appears in the doc text


def test_boost_is_multiplicative_on_original_score(monkeypatch):
    """score = original * (1 + boost) -- a higher original score stays higher post-boost."""
    monkeypatch.setattr(gretrieval, "get_knowledge_graph", lambda: _kg_with_entities())
    monkeypatch.setattr(
        gretrieval,
        "extract_cooccurrence_entities",
        lambda text: [{"entity": "AAPL"}, {"entity": "GOOG"}],
    )
    documents = [
        {"id": "hi-base", "text": "AAPL and GOOG both", "score": 0.9},
        {"id": "lo-base", "text": "AAPL and GOOG both", "score": 0.1},
    ]
    out = _run("AAPL GOOG", documents)
    # Same entity overlap -> same boost multiplier; ordering follows the base score.
    assert out[0]["id"] == "hi-base"
    assert out[0]["score"] > out[1]["score"]
