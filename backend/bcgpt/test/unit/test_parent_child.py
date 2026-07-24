"""Tests for parent-child document chunking (``retrieval/parent_child.py``).

Locks the iter-71 fix: ``create_parent_child_chunks`` now generates a unique
``parent_id`` PER PARENT CHUNK (it used to generate one per *document*, so a large
document that split into several parent chunks collided on a single id -- all but the
last-written were silently lost in the docstore, breaking parent-child retrieval for
any document over ``PARENT_CHUNK_SIZE``).

The vector-DB-backed loaders (``load_parents_from_docstore`` / ``replace_children_with_
parents``) are not exercised; the chunking + the pure resolution helpers are.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_parent_child.py -q
"""

from __future__ import annotations

from langchain_core.documents import Document

from bcgpt.retrieval.parent_child import (
    build_parent_score_map,
    create_parent_child_chunks,
    get_docstore_collection_name,
    resolve_to_parents,
)

# ---------------------------------------------------------------------------
# create_parent_child_chunks -- the iter-71 fix
# ---------------------------------------------------------------------------


def test_small_document_single_parent():
    parents, children = create_parent_child_chunks([Document(page_content="short doc")])
    assert len(parents) == 1
    assert parents[0]["chunk_type"] == "parent"
    assert parents[0]["parent_id"] is None
    # children link to the one parent
    assert all(c["parent_id"] == parents[0]["id"] for c in children)
    assert all(c["chunk_type"] == "child" for c in children)


def test_large_document_parents_have_unique_ids():
    """Regression (iter-71): a document larger than PARENT_CHUNK_SIZE splits into
    multiple parent chunks, and EACH must get a unique id (previously they all
    shared one document-level id, so the docstore kept only one)."""
    big = Document(page_content="word " * 1500)  # well over the 2000-char parent size
    parents, children = create_parent_child_chunks([big])
    assert len(parents) > 1, "expected multiple parent chunks for a large document"
    parent_ids = [p["id"] for p in parents]
    assert len(set(parent_ids)) == len(parent_ids), "parent ids must be unique"


def test_children_link_to_their_specific_parent():
    big = Document(page_content="word " * 1500)
    parents, children = create_parent_child_chunks([big])
    parent_id_set = {p["id"] for p in parents}
    # every child's parent_id must be one of the parent chunk ids
    assert all(c["parent_id"] in parent_id_set for c in children)
    # children of the same parent chunk share that chunk's id
    for p in parents:
        kids = [c for c in children if c["parent_id"] == p["id"]]
        for k in kids:
            assert k["metadata"]["parent_id"] == p["id"]


def test_multiple_documents_kept_separate():
    parents, children = create_parent_child_chunks(
        [
            Document(page_content="document one text"),
            Document(page_content="document two text"),
        ]
    )
    # each input document yields at least one parent; all parent ids unique overall
    assert len(parents) >= 2
    assert len({p["id"] for p in parents}) == len(parents)


# ---------------------------------------------------------------------------
# resolve_to_parents / build_parent_score_map (pure)
# ---------------------------------------------------------------------------


def test_resolve_to_parents_collects_child_parent_ids():
    results = [
        {
            "metadata": {"chunk_type": "child", "parent_id": "p1"},
            "score": 0.9,
            "text": "c1",
        },
        {
            "metadata": {"chunk_type": "child", "parent_id": "p2"},
            "score": 0.8,
            "text": "c2",
        },
        {
            "metadata": {"chunk_type": "parent", "parent_id": "pX"},
            "score": 0.7,
            "text": "pX",
        },
        {
            "metadata": {"chunk_type": "child"},
            "score": 0.6,
            "text": "orphan",
        },  # no parent_id
    ]
    child_results, parent_ids = resolve_to_parents(results)
    assert parent_ids == {"p1", "p2"}
    assert (
        len(child_results) == 2
    )  # only the two valid children (parent + orphan excluded)


def test_build_parent_score_map_keeps_best():
    child_results = [
        {"metadata": {"parent_id": "p1"}, "score": 0.5},
        {"metadata": {"parent_id": "p1"}, "score": 0.9},  # higher -> wins
        {"metadata": {"parent_id": "p1"}, "score": 0.3},
        {"metadata": {"parent_id": "p2"}, "score": 0.8},
        {"metadata": {}, "score": 0.99},  # no parent_id -> ignored
    ]
    scores = build_parent_score_map(child_results)
    assert scores == {"p1": 0.9, "p2": 0.8}


def test_build_parent_score_map_empty():
    assert build_parent_score_map([]) == {}


# ---------------------------------------------------------------------------
# get_docstore_collection_name
# ---------------------------------------------------------------------------


def test_docstore_collection_name():
    assert get_docstore_collection_name("my_kb") == "my_kb_parent_docstore"
