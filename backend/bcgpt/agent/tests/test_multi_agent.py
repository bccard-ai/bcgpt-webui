"""Unit tests for multi-agent coordination (fake LLM via base.llm_complete)."""

from __future__ import annotations

import asyncio

from bcgpt.agent.multi_agent import MultiAgentExecutor
import bcgpt.agent.multi_agent.base as ma_base

run = asyncio.run


def _resp(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def _patch_llm(monkeypatch, fn):
    """Patch the llm_complete used by ask_agent (defined in base)."""
    monkeypatch.setattr(ma_base, "llm_complete", fn)


AGENTS = [
    {"model_id": "m1", "role": "alpha"},
    {"model_id": "m2", "role": "beta"},
]


def test_patterns_list():
    pats = MultiAgentExecutor.patterns()
    assert set(pats) == {
        "sequential",
        "parallel",
        "debate",
        "consensus",
        "voting",
        "moa",
    }


def test_sequential_pipes_output(monkeypatch):
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
        # echo which model + last user content length marker
        return _resp(f"out-of-{model_id}")

    _patch_llm(monkeypatch, fake)
    ex = MultiAgentExecutor()
    res = run(ex.execute(object(), object(), "sequential", AGENTS, "task", {}))
    assert res["pattern"] == "sequential"
    assert res["output"] == "out-of-m2"  # last agent's output
    assert len(res["steps"]) == 2


def test_parallel_collects_all(monkeypatch):
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
        return _resp(f"answer-{model_id}")

    _patch_llm(monkeypatch, fake)
    ex = MultiAgentExecutor()
    res = run(ex.execute(object(), object(), "parallel", AGENTS, "task", {}))
    assert res["pattern"] == "parallel"
    assert len(res["responses"]) == 2
    assert "answer-m1" in res["output"] and "answer-m2" in res["output"]


def test_parallel_with_aggregator(monkeypatch):
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
        if model_id == "agg":
            return _resp("AGGREGATED")
        return _resp(f"answer-{model_id}")

    _patch_llm(monkeypatch, fake)
    ex = MultiAgentExecutor()
    res = run(
        ex.execute(
            object(),
            object(),
            "parallel",
            AGENTS,
            "task",
            {"aggregator_model_id": "agg"},
        )
    )
    assert res["output"] == "AGGREGATED"


def test_moa_proposers_and_aggregator(monkeypatch):
    seen = []

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
        seen.append(model_id)
        return _resp(f"r-{model_id}")

    _patch_llm(monkeypatch, fake)
    ex = MultiAgentExecutor()
    res = run(
        ex.execute(
            object(), object(), "moa", AGENTS, "task", {"aggregator_model_id": "agg"}
        )
    )
    assert res["pattern"] == "moa"
    assert res["aggregator_model_id"] == "agg"
    assert res["output"] == "r-agg"
    assert len(res["proposals"]) == 2


def test_unknown_pattern_raises():
    ex = MultiAgentExecutor()
    try:
        run(ex.execute(object(), object(), "telepathy", AGENTS, "task", {}))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_empty_agents_raises(monkeypatch):
    _patch_llm(monkeypatch, lambda *a, **k: _resp("x"))
    ex = MultiAgentExecutor()
    try:
        run(ex.execute(object(), object(), "parallel", [], "task", {}))
        assert False, "expected ValueError"
    except ValueError:
        pass
