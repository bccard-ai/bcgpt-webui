"""Unit tests for the ReAct tool loop (provider-agnostic, fake LLM)."""

from __future__ import annotations

import asyncio

from bcgpt.agent.tool_loop import ReactToolLoop, ToolDefinition
import bcgpt.agent.tool_loop.react_loop as react_loop

run = asyncio.run


def _msg(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _make_echo_tool(executed, sources):
    async def echo_exec(args, ctx):
        executed.append(args)
        ctx.sources.append({"document": f"echoed:{args.get('q')}", "metadata": {}})
        return f"echo result for {args.get('q')}"

    return ToolDefinition(
        name="echo",
        description="echo",
        parameters={
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
        executor=echo_exec,
    )


def test_loop_executes_tool_then_returns_final(monkeypatch):
    seq = [
        _msg('```tool_call\n{"name": "echo", "arguments": {"q": "hi"}}\n```'),
        _msg("Final answer: done."),
    ]
    calls = {"n": 0}

    async def fake(
        request,
        user,
        model_id,
        messages,
        *,
        params=None,
        tools=None,
        bypass_filter=True,
        extra=None,
    ):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]

    monkeypatch.setattr(react_loop, "llm_complete", fake)

    executed = []
    tool = _make_echo_tool(executed, None)
    loop = ReactToolLoop(
        request=object(), user=object(), model_id="m", tools=[tool], max_iterations=5
    )
    res = run(loop.run([{"role": "user", "content": "go"}]))

    assert executed == [{"q": "hi"}]
    assert res.content == "Final answer: done."
    assert res.iterations == 2
    assert res.stopped_reason == "completed"
    assert len(res.tool_call_log) == 1 and res.tool_call_log[0]["name"] == "echo"
    assert any("echoed:hi" in s["document"] for s in res.sources)


def test_loop_forces_final_after_max_iterations(monkeypatch):
    async def always_tool(
        request,
        user,
        model_id,
        messages,
        *,
        params=None,
        tools=None,
        bypass_filter=True,
        extra=None,
    ):
        if tools is None:  # the forced final call passes no tools
            return _msg("forced final")
        return _msg('```tool_call\n{"name":"echo","arguments":{"q":"x"}}\n```')

    monkeypatch.setattr(react_loop, "llm_complete", always_tool)

    executed = []
    tool = _make_echo_tool(executed, None)
    loop = ReactToolLoop(
        request=object(), user=object(), model_id="m", tools=[tool], max_iterations=3
    )
    res = run(loop.run([{"role": "user", "content": "go"}]))

    assert res.stopped_reason == "max_iterations"
    assert res.content == "forced final"
    assert res.iterations == 3


def test_native_tool_calls_are_parsed(monkeypatch):
    seq = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "c1",
                                "function": {
                                    "name": "echo",
                                    "arguments": '{"q": "native"}',
                                },
                            }
                        ],
                    }
                }
            ]
        },
        _msg("done natively"),
    ]
    calls = {"n": 0}

    async def fake(
        request,
        user,
        model_id,
        messages,
        *,
        params=None,
        tools=None,
        bypass_filter=True,
        extra=None,
    ):
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]

    monkeypatch.setattr(react_loop, "llm_complete", fake)
    executed = []
    tool = _make_echo_tool(executed, None)
    loop = ReactToolLoop(
        request=object(), user=object(), model_id="m", tools=[tool], max_iterations=5
    )
    res = run(loop.run([{"role": "user", "content": "go"}]))
    assert executed == [{"q": "native"}]
    assert res.content == "done natively"


def test_no_tools_returns_immediately(monkeypatch):
    async def fake(
        request,
        user,
        model_id,
        messages,
        *,
        params=None,
        tools=None,
        bypass_filter=True,
        extra=None,
    ):
        return _msg("direct answer")

    monkeypatch.setattr(react_loop, "llm_complete", fake)
    loop = ReactToolLoop(
        request=object(), user=object(), model_id="m", tools=[], max_iterations=5
    )
    res = run(loop.run([{"role": "user", "content": "hi"}]))
    assert res.content == "direct answer"
    assert res.iterations == 1
