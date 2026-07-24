"""Unit tests for file access via KB inheritance (P2.2)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import bcgpt.routers.files as files_mod


def _patch(monkeypatch, file_kb_ids, user_kb_ids):
    monkeypatch.setattr(
        files_mod.KnowledgeFiles,
        "knowledges_for_file",
        lambda file_id: list(file_kb_ids),
    )
    monkeypatch.setattr(
        files_mod.Knowledges,
        "get_knowledge_bases_by_user_id",
        lambda user_id, access_type: [SimpleNamespace(id=k) for k in user_kb_ids],
    )


def test_access_granted_via_any_member_kb(monkeypatch):
    # file in kb-a + kb-b; user can access kb-b → granted
    _patch(monkeypatch, ["kb-a", "kb-b"], ["kb-b"])
    file = SimpleNamespace(id="f1", meta={"collection_name": "kb-x"})
    user = SimpleNamespace(id="u1")
    assert asyncio.run(files_mod._can_access_via_knowledge(file, user, "read"))


def test_access_denied_when_no_member_kb_accessible(monkeypatch):
    _patch(monkeypatch, ["kb-a"], ["kb-z"])
    file = SimpleNamespace(id="f1", meta={"collection_name": "kb-a"})
    user = SimpleNamespace(id="u1")
    assert not asyncio.run(files_mod._can_access_via_knowledge(file, user, "read"))


def test_access_falls_back_to_collection_name(monkeypatch):
    # junction empty → fall back to meta.collection_name
    _patch(monkeypatch, [], ["kb-c"])
    file = SimpleNamespace(id="f1", meta={"collection_name": "kb-c"})
    user = SimpleNamespace(id="u1")
    assert asyncio.run(files_mod._can_access_via_knowledge(file, user, "read"))


def test_access_denied_when_no_kb_and_no_collection_name(monkeypatch):
    _patch(monkeypatch, [], ["kb-c"])
    file = SimpleNamespace(id="f1", meta=None)
    user = SimpleNamespace(id="u1")
    assert not asyncio.run(files_mod._can_access_via_knowledge(file, user, "read"))


def test_access_granted_for_multi_kb_owner(monkeypatch):
    # file in several KBs, user owns all of them
    _patch(monkeypatch, ["kb-1", "kb-2", "kb-3"], ["kb-1", "kb-2", "kb-3"])
    file = SimpleNamespace(id="f1", meta={"collection_name": "kb-1"})
    user = SimpleNamespace(id="u1")
    assert asyncio.run(files_mod._can_access_via_knowledge(file, user, "write"))
