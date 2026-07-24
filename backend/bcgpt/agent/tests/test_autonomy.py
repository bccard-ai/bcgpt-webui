"""Unit tests for autonomy-level resolution (pure, no config/DB)."""

from __future__ import annotations

from bcgpt.agent.autonomy import (
    extract_meta,
    read_meta_autonomy,
    resolve_autonomy_level,
)
from bcgpt.agent.types import AgentAutonomyLevel

DEFAULT = AgentAutonomyLevel.ASSISTANT


def test_from_value_coercion():
    assert AgentAutonomyLevel.from_value("operator") is AgentAutonomyLevel.OPERATOR
    assert AgentAutonomyLevel.from_value("  Operator ") is AgentAutonomyLevel.OPERATOR
    assert AgentAutonomyLevel.from_value(None) is AgentAutonomyLevel.ASSISTANT
    assert AgentAutonomyLevel.from_value("nonsense") is AgentAutonomyLevel.ASSISTANT


def test_extract_meta_from_runtime_model_dict():
    model = {
        "id": "m",
        "owned_by": "openai",
        "info": {"meta": {"autonomy_level": "operator"}},
    }
    assert extract_meta(model) == {"autonomy_level": "operator"}


def test_extract_meta_from_plain_meta_dict():
    assert extract_meta({"autonomy_level": "suggest"}) == {"autonomy_level": "suggest"}


def test_read_meta_autonomy_legacy_capabilities_fallback():
    model = {"meta": {"capabilities": {"autonomy_level": "operator"}}}
    assert read_meta_autonomy(model) == "operator"


def test_resolve_uses_default_when_absent():
    assert resolve_autonomy_level({"meta": {}}, DEFAULT) is AgentAutonomyLevel.ASSISTANT
    assert resolve_autonomy_level(None, DEFAULT) is AgentAutonomyLevel.ASSISTANT


def test_resolve_reads_explicit_level():
    model = {"info": {"meta": {"autonomy_level": "operator"}}}
    assert resolve_autonomy_level(model, DEFAULT) is AgentAutonomyLevel.OPERATOR


class _MetaObj:
    def model_dump(self):
        return {"autonomy_level": "suggest"}


class _ModelObj:
    meta = _MetaObj()


def test_resolve_from_pydantic_like_object():
    assert resolve_autonomy_level(_ModelObj(), DEFAULT) is AgentAutonomyLevel.SUGGEST
