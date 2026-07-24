"""Tests for the agent tool-loop's tool-call parsing (``agent/tool_loop/react_loop.py``).

The loop itself is bounded by ``max_iterations`` and reviewed as sound; these tests
lock the PURE parsing layer -- ``_parse_tool_calls`` (native OpenAI ``tool_calls`` and
the prompt-protocol fenced-block form) and ``_strip_tool_blocks`` -- because that
parsing drives which tool gets executed with which arguments. A regression here means
either a wrong/missed tool call or leaked tool-call markup into the user-visible
answer. The functions are pure (``re`` + ``json``), no DB/config.

Notable cases locked: native args as dict vs JSON-string vs None; nested-JSON
arguments inside a fenced block (the fence anchor lets the non-greedy regex match the
full object); malformed JSON is skipped, not raised; the ``name``/``tool`` and
``arguments``/``args`` aliases; stripping leaves non-tool content intact.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_tool_loop.py -q
"""

from __future__ import annotations

from bcgpt.agent.tool_loop.react_loop import _parse_tool_calls, _strip_tool_blocks

# ---------------------------------------------------------------------------
# native OpenAI tool_calls
# ---------------------------------------------------------------------------


def test_native_dict_arguments_kept():
    msg = {
        "tool_calls": [
            {"id": "1", "function": {"name": "search", "arguments": {"q": "x"}}}
        ]
    }
    out = _parse_tool_calls(msg, "")
    assert out == [{"name": "search", "arguments": {"q": "x"}, "id": "1"}]


def test_native_string_arguments_parsed():
    msg = {
        "tool_calls": [
            {"id": "2", "function": {"name": "run", "arguments": '{"a": 1}'}}
        ]
    }
    out = _parse_tool_calls(msg, "")
    assert out[0]["arguments"] == {"a": 1}


def test_native_malformed_string_arguments_become_empty():
    msg = {
        "tool_calls": [
            {"id": "3", "function": {"name": "run", "arguments": "not-json"}}
        ]
    }
    out = _parse_tool_calls(msg, "")
    assert out[0]["arguments"] == {}


def test_native_none_arguments_become_empty():
    msg = {"tool_calls": [{"id": "4", "function": {"name": "run", "arguments": None}}]}
    out = _parse_tool_calls(msg, "")
    assert out[0]["arguments"] == {}


def test_native_call_without_name_is_dropped():
    msg = {
        "tool_calls": [
            {"id": "5", "function": {"name": "", "arguments": {}}},
            {"id": "6", "function": {"name": "ok", "arguments": {}}},
        ]
    }
    out = _parse_tool_calls(msg, "")
    assert [c["name"] for c in out] == ["ok"]


def test_native_empty_when_no_tool_calls():
    assert _parse_tool_calls({"tool_calls": []}, "") == []
    assert _parse_tool_calls({}, "") == []
    assert _parse_tool_calls(None, "") == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# prompt-protocol fenced blocks
# ---------------------------------------------------------------------------


def test_fenced_block_with_nested_json_arguments():
    # Non-greedy regex + the closing-fence anchor must capture the FULL object,
    # including nested arguments (not truncate at the inner '}').
    content = '```tool_call\n{"name": "search", "arguments": {"query": "hi", "opts": {"k": 1}}}\n```'
    out = _parse_tool_calls({}, content)
    assert len(out) == 1
    assert out[0]["name"] == "search"
    assert out[0]["arguments"] == {"query": "hi", "opts": {"k": 1}}


def test_fenced_block_aliases_tool_and_args():
    content = '```json\n{"tool": "t", "args": {"x": 2}}\n```'
    out = _parse_tool_calls({}, content)
    assert out == [{"name": "t", "arguments": {"x": 2}, "id": "call_0"}]


def test_fenced_block_malformed_json_skipped():
    content = "```tool_call\n{not valid json}\n```"
    assert _parse_tool_calls({}, content) == []


def test_fenced_block_without_name_skipped():
    content = '```tool_call\n{"arguments": {"x": 1}}\n```'
    assert _parse_tool_calls({}, content) == []


def test_fenced_block_non_dict_arguments_coerced():
    content = '```tool_call\n{"name": "t", "arguments": ["a", "b"]}\n```'
    out = _parse_tool_calls({}, content)
    assert out == [{"name": "t", "arguments": {}, "id": "call_0"}]


def test_multiple_fenced_blocks_all_parsed():
    content = (
        '```tool_call\n{"name": "a", "arguments": {}}\n```\n'
        '```tool_call\n{"name": "b", "arguments": {}}\n```'
    )
    out = _parse_tool_calls({}, content)
    assert [c["name"] for c in out] == ["a", "b"]
    assert {c["id"] for c in out} == {"call_0", "call_1"}


# ---------------------------------------------------------------------------
# _strip_tool_blocks
# ---------------------------------------------------------------------------


def test_strip_removes_tool_blocks_keeps_rest():
    # The fenced block is removed; the newlines that surrounded it remain.
    content = 'Before.\n```tool_call\n{"name": "a", "arguments": {}}\n```\nAfter.'
    assert _strip_tool_blocks(content) == "Before.\n\nAfter."


def test_strip_no_blocks_unchanged():
    assert _strip_tool_blocks("plain text") == "plain text"


def test_strip_empty():
    assert _strip_tool_blocks("") == ""
    assert _strip_tool_blocks(None) == ""  # type: ignore[arg-type]
