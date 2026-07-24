"""Unit tests for query_corpus filtered search + corpus-filter helpers (P1.3)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.retrieval import search as search_mod
from bcgpt.retrieval import source_resolution as sr
from bcgpt.retrieval.vector import SearchResult

# --------------------------------------------------------------------------
# _resolve_corpus_filter
# --------------------------------------------------------------------------


def test_corpus_filter_kb_ref():
    assert sr._resolve_corpus_filter({"id": "kb-1", "type": "collection"}) == (
        ["kb-1"],
        None,
    )


def test_corpus_filter_standalone_file():
    assert sr._resolve_corpus_filter({"id": "f-1"}) == (None, ["f-1"])


def test_corpus_filter_legacy_returns_none():
    assert (
        sr._resolve_corpus_filter(
            {"type": "collection", "legacy": True, "collection_names": ["x"]}
        )
        is None
    )


def test_corpus_filter_explicit_collection_name_returns_none():
    # explicit collection_name stays on the legacy per-collection path
    assert sr._resolve_corpus_filter({"collection_name": "somename"}) is None


def test_corpus_filter_empty_returns_none():
    assert sr._resolve_corpus_filter({}) is None


# --------------------------------------------------------------------------
# _context_has_documents
# --------------------------------------------------------------------------


def test_context_has_documents_true():
    assert sr._context_has_documents({"documents": [["a", "b"]]}) is True


def test_context_has_documents_empty_rows():
    assert sr._context_has_documents({"documents": [[]]}) is False


def test_context_has_documents_missing_key():
    assert sr._context_has_documents({}) is False
    assert sr._context_has_documents(None) is False


# --------------------------------------------------------------------------
# query_corpus — mocked VECTOR_DB_CLIENT.search_filtered
# --------------------------------------------------------------------------


class _FakeClient:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def search_filtered(self, *, collection_name, vectors, conditions, limit):
        self.calls.append(
            {
                "collection_name": collection_name,
                "conditions": conditions,
                "limit": limit,
            }
        )
        return self.result


def _embedding_fn(query, prefix=None):
    return [0.1, 0.2, 0.3]


def test_query_corpus_builds_must_conditions(monkeypatch):
    fake = _FakeClient(
        SearchResult(
            ids=[["p1"]], documents=[["doc"]], metadatas=[[{"x": 1}]], distances=[[0.9]]
        )
    )
    monkeypatch.setattr(search_mod, "VECTOR_DB_CLIENT", fake)

    out = search_mod.query_corpus(
        corpus_name="corpus_abc",
        queries=["hello"],
        embedding_function=_embedding_fn,
        k=5,
        knowledge_ids=["kb-1", "kb-2"],
        workspace_id="default",
    )

    assert fake.calls and fake.calls[0]["collection_name"] == "corpus_abc"
    cond = dict((k, v) for k, v in fake.calls[0]["conditions"])
    assert cond["knowledge_id"] == ["kb-1", "kb-2"]
    assert cond["workspace_id"] == "default"
    # result merged and surfaced
    assert sr._context_has_documents(out) is True


def test_query_corpus_no_filters_no_conditions(monkeypatch):
    fake = _FakeClient(None)
    monkeypatch.setattr(search_mod, "VECTOR_DB_CLIENT", fake)
    search_mod.query_corpus(
        corpus_name="corpus_abc",
        queries=["q"],
        embedding_function=_embedding_fn,
        k=3,
    )
    assert fake.calls[0]["conditions"] == []


def test_query_corpus_backend_without_search_filtered_returns_empty(monkeypatch):
    # a backend that lacks search_filtered (e.g. a non-Qdrant adapter) → empty, no crash
    monkeypatch.setattr(search_mod, "VECTOR_DB_CLIENT", SimpleNamespace())
    out = search_mod.query_corpus(
        corpus_name="corpus_abc",
        queries=["q"],
        embedding_function=_embedding_fn,
        k=3,
        knowledge_ids=["kb-1"],
    )
    assert sr._context_has_documents(out) is False
