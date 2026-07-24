"""Tests for the workflow CONTEXT_MERGE node (``agent/workflow/nodes/context_merge.py``).

CONTEXT_MERGE fuses RAG + web results into one ranked context via RRF. The ``execute`` method
is pure (merge logic only, no I/O), so it is exercised end-to-end via ``asyncio.run`` with a
minimal ``WorkflowState``. Locks: RRF cross-track accumulation, link-based dedup, [n] context
markers, source_mapping, max_items truncation, empty handling, and the ``_doc_key`` helper.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_context_merge.py -q
"""

from __future__ import annotations

import asyncio

from bcgpt.agent.workflow.nodes.context_merge import ContextMergeHandler, _doc_key
from bcgpt.agent.workflow.state import WorkflowNode, WorkflowState

_HANDLER = ContextMergeHandler()
_NODE = WorkflowNode(id="cm", type="context_merge", config={}, next_nodes=[])


def _run(state: WorkflowState):
    return asyncio.run(_HANDLER.execute(_NODE, state, None))


def _src(doc, link=None, title=None, source_type="rag"):
    return {
        "document": doc,
        "metadata": {"link": link, "title": title},
        "source_type": source_type,
    }


# ---------------------------------------------------------------------------
# RRF ranking + dedup
# ---------------------------------------------------------------------------


def test_source_in_both_tracks_ranks_first():
    # "a.com" appears in RAG rank 0 AND web rank 0 -> accumulated score -> top.
    state = WorkflowState(
        rag_results=[_src("rag A", link="a.com"), _src("rag B")],
        web_results=[_src("web A", link="a.com")],
    )
    result = _run(state)
    assert result.metadata["count"] == 2  # a.com deduped to 1, rag B = 2
    assert result.metadata["state_updates"]["source_mapping"]["1"]["link"] == "a.com"


def test_dedup_by_link_one_entry():
    state = WorkflowState(
        rag_results=[_src("doc", link="shared.com")],
        web_results=[_src("same doc different text", link="shared.com")],
    )
    result = _run(state)
    assert result.metadata["count"] == 1  # deduped by link


def test_no_link_dedup_by_doc_prefix():
    state = WorkflowState(
        rag_results=[_src("identical text here")],
        web_results=[_src("identical text here")],
    )
    result = _run(state)
    assert result.metadata["count"] == 1  # deduped by doc[:200]


# ---------------------------------------------------------------------------
# context string + source_mapping
# ---------------------------------------------------------------------------


def test_context_has_numbered_markers():
    state = WorkflowState(
        rag_results=[_src("doc one", title="First"), _src("doc two", title="Second")]
    )
    result = _run(state)
    assert "[1]" in result.output
    assert "[2]" in result.output
    assert "First" in result.output  # title in header


def test_source_mapping_shape():
    state = WorkflowState(rag_results=[_src("a doc", link="x.com", source_type="rag")])
    result = _run(state)
    sm = result.metadata["state_updates"]["source_mapping"]
    assert "1" in sm
    assert sm["1"]["link"] == "x.com"
    assert sm["1"]["source_type"] == "rag"
    assert sm["1"]["score"] > 0.0


# ---------------------------------------------------------------------------
# max_items + empty
# ---------------------------------------------------------------------------


def test_max_items_truncation():
    node = WorkflowNode(
        id="cm", type="context_merge", config={"max_items": 2}, next_nodes=[]
    )
    state = WorkflowState(rag_results=[_src(f"doc {i}") for i in range(5)])
    result = asyncio.run(_HANDLER.execute(node, state, None))
    assert result.metadata["count"] == 2


def test_empty_state_produces_empty_context():
    result = _run(WorkflowState())
    assert result.output == ""
    assert result.metadata["count"] == 0


def test_state_sources_fallback():
    # When rag_results AND web_results are empty, state.sources is used.
    state = WorkflowState(sources=[_src("injected source")])
    result = _run(state)
    assert result.metadata["count"] == 1


# ---------------------------------------------------------------------------
# _doc_key
# ---------------------------------------------------------------------------


def test_doc_key_prefers_link():
    assert _doc_key({"document": "x", "metadata": {"link": "url.com"}}) == "url.com"


def test_doc_key_falls_back_to_doc_prefix():
    assert (
        _doc_key({"document": "hello world" * 50, "metadata": {}})
        == ("hello world" * 50).strip()[:200]
    )


def test_doc_key_empty_returns_empty():
    assert _doc_key({"document": "", "metadata": {}}) == ""
    assert _doc_key({}) == ""
