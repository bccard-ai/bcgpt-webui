"""Unit tests for retrieval lifecycle helpers (P0.1).

Covers ``purge_file_vectors`` — the O(1) vector-db cleanup wired into file
deletion. Verifies it removes a file's vectors from its current (KB) collection
when applicable, and always drops the standalone ``file-{id}`` collection.
"""

from __future__ import annotations

import asyncio
import types

from bcgpt.retrieval import lifecycle


class FakeVectorClient:
    """Records calls; mimics the VECTOR_DB_CLIENT surface used by lifecycle."""

    def __init__(self, existing_collections=None):
        self.existing = set(existing_collections or [])
        self.deletes = []  # list of (collection_name, filter)
        self.dropped = []  # list of collection_name

    def delete(self, *, collection_name, filter):
        self.deletes.append((collection_name, dict(filter)))

    def has_collection(self, *, collection_name):
        return collection_name in self.existing

    def delete_collection(self, *, collection_name):
        self.dropped.append(collection_name)
        self.existing.discard(collection_name)


def _file(file_id, collection_name=None):
    meta = {"collection_name": collection_name} if collection_name else None
    return types.SimpleNamespace(id=file_id, meta=meta)


def test_purge_removes_kb_vectors_and_orphan_collection(monkeypatch):
    fake = FakeVectorClient(existing_collections={"file-f1"})
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    asyncio.run(lifecycle.purge_file_vectors(_file("f1", collection_name="kb-9")))

    # filtered delete targets the KB collection the file lives in
    assert ("kb-9", {"file_id": "f1"}) in fake.deletes
    # standalone file-f1 collection is also dropped
    assert "file-f1" in fake.dropped


def test_purge_skips_filtered_delete_when_only_standalone(monkeypatch):
    fake = FakeVectorClient(existing_collections={"file-f2"})
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    asyncio.run(lifecycle.purge_file_vectors(_file("f2", collection_name="file-f2")))

    # collection_name == standalone → no KB-scoped filtered delete
    assert fake.deletes == []
    assert "file-f2" in fake.dropped


def test_purge_with_no_meta_only_drops_orphan(monkeypatch):
    fake = FakeVectorClient(existing_collections={"file-f3"})
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    asyncio.run(lifecycle.purge_file_vectors(_file("f3")))

    assert fake.deletes == []
    assert "file-f3" in fake.dropped


def test_purge_is_resilient_to_non_dict_meta(monkeypatch):
    fake = FakeVectorClient(existing_collections=set())
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    # meta is a list (malformed) — must not crash, just skip filtered delete
    asyncio.run(
        lifecycle.purge_file_vectors(types.SimpleNamespace(id="f4", meta=["nope"]))
    )
    assert fake.deletes == []


# --------------------------------------------------------------------------
# delete_knowledge_vectors (P1.6 — corpus filter-delete on KB delete/reset)
# --------------------------------------------------------------------------


def test_delete_knowledge_vectors_noop_when_flag_off(monkeypatch):
    import bcgpt.config as cfg

    monkeypatch.setattr(cfg, "RAG_USE_CORPUS", types.SimpleNamespace(value=False))
    fake = FakeVectorClient()
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    asyncio.run(lifecycle.delete_knowledge_vectors("kb-9"))

    assert fake.deletes == []  # flag off → corpus untouched


def test_delete_knowledge_vectors_filter_deletes_when_flag_on(monkeypatch):
    import bcgpt.config as cfg

    monkeypatch.setattr(cfg, "RAG_USE_CORPUS", types.SimpleNamespace(value=True))
    fake = FakeVectorClient()
    monkeypatch.setattr(lifecycle, "VECTOR_DB_CLIENT", fake)

    asyncio.run(lifecycle.delete_knowledge_vectors("kb-9"))

    assert len(fake.deletes) == 1
    cname, flt = fake.deletes[0]
    assert cname.startswith("corpus_")
    assert flt == {"knowledge_id": "kb-9"}
