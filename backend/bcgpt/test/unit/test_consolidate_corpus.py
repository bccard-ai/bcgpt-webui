"""Unit tests for the corpus-consolidation migration (P1.5)."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.retrieval.migrations import consolidate_corpus as cc


def _app_state(dim_probe_len=3):
    """request-like object with app.state.EMBEDDING_FUNCTION returning a vector."""
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                EMBEDDING_FUNCTION=lambda text, prefix=None: [0.1] * dim_probe_len
            )
        )
    )


class _FakeClient:
    """Records upserts; serves paginated points with vectors."""

    def __init__(self, collections, points_by_name, dims_by_name):
        # collections: list of display names; points_by_name: list of point dicts
        self._collections = collections
        self._points = points_by_name
        self._dims = dims_by_name
        self.upserts = []  # (corpus_name, items)

    def list_collections(self):
        return [SimpleNamespace(name=n) for n in self._collections]

    def get_collection_info(self, *, collection_name):
        return {"dimension": self._dims.get(collection_name)}

    def list_points_with_vectors(self, *, collection_name, limit, offset):
        pts = self._points.get(collection_name, [])
        # naive paging by offset index encoded as str(int)
        start = int(offset) if offset is not None else 0
        page = pts[start : start + limit]
        nxt = str(start + limit) if start + limit < len(pts) else None
        return {"points": page, "next_offset": nxt}

    def upsert(self, *, collection_name, items):
        self.upserts.append((collection_name, items))


def test_migrates_same_dim_collection_with_knowledge_id(monkeypatch):

    # corpus dim = 3; KB collection "kb-1" also dim 3
    points = [
        {
            "id": "p1",
            "text": "a",
            "metadata": {"file_id": "f1"},
            "vector": [0.1, 0.2, 0.3],
        },
        {
            "id": "p2",
            "text": "b",
            "metadata": {"file_id": "f1"},
            "vector": [0.4, 0.5, 0.6],
        },
    ]
    fake = _FakeClient(["kb-1"], {"kb-1": points}, {"kb-1": 3})
    import bcgpt.retrieval as _ret

    monkeypatch.setattr(_ret, "VECTOR_DB_CLIENT", fake)

    out = cc.consolidate_corpus(_app_state(3))

    assert out["migrated"] == 2
    assert out["seen"] == ["kb-1"]
    assert out["skipped_dim_mismatch"] == []
    corpus_name, items = fake.upserts[0]
    assert corpus_name.startswith("corpus_")
    # KB-id collection → knowledge_id = collection name; workspace_id stamped
    assert all(it["metadata"]["knowledge_id"] == "kb-1" for it in items)
    assert all(it["metadata"]["workspace_id"] == "default" for it in items)
    # vectors preserved
    assert items[0]["vector"] == [0.1, 0.2, 0.3]


def test_file_collection_gets_null_knowledge_id(monkeypatch):

    points = [
        {"id": "x", "text": "t", "metadata": {"file_id": "f-9"}, "vector": [1, 1, 1]}
    ]
    fake = _FakeClient(["file-f-9"], {"file-f-9": points}, {"file-f-9": 3})
    import bcgpt.retrieval as _ret

    monkeypatch.setattr(_ret, "VECTOR_DB_CLIENT", fake)

    out = cc.consolidate_corpus(_app_state(3))

    assert out["migrated"] == 1
    _, items = fake.upserts[0]
    # file-{id} → standalone, knowledge_id None (scoped by file_id)
    assert items[0]["metadata"]["knowledge_id"] is None


def test_dim_mismatched_collection_left_in_place(monkeypatch):
    points = [{"id": "p", "text": "t", "metadata": {}, "vector": [1, 1, 1, 1]}]
    fake = _FakeClient(
        ["kb-old"], {"kb-old": points}, {"kb-old": 4}
    )  # dim 4 vs corpus 3
    import bcgpt.retrieval as _ret

    monkeypatch.setattr(_ret, "VECTOR_DB_CLIENT", fake)

    out = cc.consolidate_corpus(_app_state(3))

    assert out["migrated"] == 0
    assert fake.upserts == []
    assert out["skipped_dim_mismatch"] == [{"collection": "kb-old", "dim": 4}]


def test_dry_run_does_not_upsert(monkeypatch):
    points = [{"id": "p1", "text": "a", "metadata": {}, "vector": [0.1, 0.2, 0.3]}]
    fake = _FakeClient(["kb-1"], {"kb-1": points}, {"kb-1": 3})
    import bcgpt.retrieval as _ret

    monkeypatch.setattr(_ret, "VECTOR_DB_CLIENT", fake)

    out = cc.consolidate_corpus(_app_state(3), dry_run=True)

    assert out["migrated"] == 0
    assert out["seen"] == ["kb-1"]
    assert fake.upserts == []


def test_skips_corpus_user_web_docstore_collections(monkeypatch):
    # none of these are legacy corpus candidates → nothing migrated
    fake = _FakeClient(
        ["corpus_abc", "user-u1", "web-search-x", "kb-1__docstore"],
        {},
        {},
    )
    import bcgpt.retrieval as _ret

    monkeypatch.setattr(_ret, "VECTOR_DB_CLIENT", fake)
    out = cc.consolidate_corpus(_app_state(3))
    assert out["seen"] == []
    assert out["migrated"] == 0
