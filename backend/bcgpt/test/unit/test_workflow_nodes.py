"""Tests for workflow node-handler pure helpers.

Locks the deterministic parsing helpers used by the TEXT_PROCESSOR (``_extract_json``)
and API_CALL (``_dig``) nodes -- both are pure and untested, and a regression in either
silently corrupts what a workflow feeds downstream (the JSON it parsed, the API field it
extracted). The handlers' I/O paths (HTTP/LLM) are not covered.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_workflow_nodes.py -q
"""

from __future__ import annotations

from bcgpt.agent.workflow.nodes.api_call import _dig
from bcgpt.agent.workflow.nodes.llm_call import _build_messages
from bcgpt.agent.workflow.nodes.rag_search import _to_sources
from bcgpt.agent.workflow.nodes.text_processor import _extract_json
from bcgpt.agent.workflow.state import WorkflowNode, WorkflowState

# ---------------------------------------------------------------------------
# _extract_json -- pull the first JSON object/array out of text
# ---------------------------------------------------------------------------


def test_extract_simple_object():
    assert _extract_json('here: {"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_extract_nested_object():
    assert _extract_json('result {"a": {"b": [1, 2]}} tail') == {"a": {"b": [1, 2]}}


def test_extract_array():
    assert _extract_json("prefix [1, 2, 3] suffix") == [1, 2, 3]


def test_extract_none_when_no_json():
    assert _extract_json("just plain text") is None


def test_extract_none_when_invalid():
    # Greedy first-{-to-last-} produces invalid JSON -> None.
    assert _extract_json("{not valid json}") is None


def test_extract_prefers_object_over_array():
    # The object pair is tried first.
    assert _extract_json("{} []") == {}


# ---------------------------------------------------------------------------
# _dig -- dot-path extraction from nested dict/list
# ---------------------------------------------------------------------------


def test_dig_nested_dict_path():
    assert _dig({"data": {"items": [1, 2]}}, "data.items") == [1, 2]


def test_dig_list_index():
    assert _dig({"list": [10, 20, 30]}, "list.1") == 20


def test_dig_dict_then_list():
    assert _dig({"rows": [{"id": 7}]}, "rows.0.id") == 7


def test_dig_missing_key_returns_none():
    assert _dig({"a": 1}, "b.c") is None


def test_dig_missing_index_returns_none():
    assert _dig({"l": [1]}, "l.9") is None


def test_dig_into_scalar_returns_none():
    assert _dig({"a": 5}, "a.b") is None  # can't dig into an int


def test_dig_empty_path_returns_none():
    # An empty path splits to [""] -> looks up an empty key -> None.
    assert _dig({"x": 1}, "") is None


# ---------------------------------------------------------------------------
# _to_sources -- flatten RAG query_collection result into source dicts (rag_search)
# ---------------------------------------------------------------------------


def test_to_sources_single_query():
    result = {
        "documents": [["doc A", "doc B"]],
        "metadatas": [[{"src": "s1"}, {"src": "s2"}]],
        "distances": [[0.1, 0.5]],
    }
    sources = _to_sources(result)
    assert len(sources) == 2
    assert sources[0] == {
        "document": "doc A",
        "metadata": {"src": "s1"},
        "distance": 0.1,
        "source_type": "rag",
    }
    assert sources[1]["document"] == "doc B"


def test_to_sources_multiple_queries():
    result = {
        "documents": [["a"], ["b", "c"]],
        "metadatas": [[{}], [{}, {}]],
        "distances": [[0.1], [0.2, 0.3]],
    }
    assert len(_to_sources(result)) == 3


def test_to_sources_missing_metadata_defaults():
    result = {"documents": [["doc"]], "metadatas": [], "distances": []}
    sources = _to_sources(result)
    assert sources[0]["metadata"] == {}
    assert sources[0]["distance"] is None


def test_to_sources_ragged_no_crash():
    # Mismatched lengths must not raise (bounded indexing).
    result = {
        "documents": [["a", "b", "c"]],
        "metadatas": [[{"x": 1}]],
        "distances": [[0.5]],
    }
    sources = _to_sources(result)
    assert len(sources) == 3
    assert sources[0]["metadata"] == {"x": 1}
    assert sources[1]["metadata"] == {}  # missing -> default
    assert sources[2]["distance"] is None


def test_to_sources_non_dict_returns_empty():
    assert _to_sources("not a dict") == []
    assert _to_sources(None) == []


def test_to_sources_empty_result():
    assert _to_sources({}) == []
    assert _to_sources({"documents": [[]]}) == []  # one query, zero docs


# ---------------------------------------------------------------------------
# _build_messages -- LLM_CALL system-prompt + context assembly (llm_call)
# ---------------------------------------------------------------------------


def _node(config=None):
    return WorkflowNode(id="llm", type="llm_call", config=config or {}, next_nodes=[])


def test_build_messages_system_prompt_and_context():
    node = _node({"system_prompt": "Be brief", "use_context": True})
    state = WorkflowState(merged_context="RAG data")
    msgs = _build_messages(node, state)
    assert msgs[0]["role"] == "system"
    assert "Be brief" in msgs[0]["content"]
    assert "<context>" in msgs[0]["content"]


def test_build_messages_strips_old_system_from_state():
    node = _node({"system_prompt": "new system"})
    state = WorkflowState(
        messages=[
            {"role": "system", "content": "old"},
            {"role": "user", "content": "hi"},
        ]
    )
    msgs = _build_messages(node, state)
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user"]
    assert msgs[0]["content"] == "new system"  # not "old"


def test_build_messages_fallback_user_input_when_no_messages():
    node = _node()
    state = WorkflowState(user_input="fallback question")
    msgs = _build_messages(node, state)
    assert msgs == [{"role": "user", "content": "fallback question"}]


def test_build_messages_no_system_prompt_no_context():
    node = _node()
    state = WorkflowState(messages=[{"role": "user", "content": "hi"}])
    msgs = _build_messages(node, state)
    assert msgs == [{"role": "user", "content": "hi"}]  # no system injected
