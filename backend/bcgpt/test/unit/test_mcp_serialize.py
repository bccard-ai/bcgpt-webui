"""Tests for the MCP result stringifier."""

from __future__ import annotations

from types import SimpleNamespace

from bcgpt.mcpbridge.serialize import stringify_call_result


def _r(blocks, is_error=False):
    return SimpleNamespace(content=blocks, isError=is_error)


def test_text():
    assert stringify_call_result(_r([SimpleNamespace(type="text", text="hi")])) == "hi"


def test_image():
    out = stringify_call_result(
        _r([SimpleNamespace(type="image", data="AAA", mimeType="image/png")])
    )
    assert "image/png" in out and "AAA" in out


def test_unknown_type_skipped():
    assert stringify_call_result(_r([SimpleNamespace(type="weird")])) == ""


def test_error_surfaces():
    out = stringify_call_result(
        _r([SimpleNamespace(type="text", text="boom")], is_error=True)
    )
    assert "boom" in out and "MCP tool error" in out


def test_truncates():
    out = stringify_call_result(_r([SimpleNamespace(type="text", text="x" * 20000)]))
    assert len(out) <= 8192 + 20
