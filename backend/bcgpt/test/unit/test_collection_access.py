"""Unit tests for collection-access enforcement on the chat retrieval path (P0.4)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from bcgpt.retrieval import lifecycle, source_resolution


def _user(uid, role="user"):
    return SimpleNamespace(id=uid, role=role)


def _kb(user_id="other", access_control=None):
    return SimpleNamespace(user_id=user_id, access_control=access_control)


def _no_kb(*a, **k):
    return None


# --------------------------------------------------------------------------
# check_collection_access (the canonical helper in lifecycle.py)
# --------------------------------------------------------------------------


def test_user_collection_owner_allowed(monkeypatch):
    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=_no_kb)
    )
    lifecycle.check_collection_access("user-u1", _user("u1"))  # no raise


def test_user_collection_other_user_forbidden(monkeypatch):
    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=_no_kb)
    )
    with pytest.raises(HTTPException) as ei:
        lifecycle.check_collection_access("user-other", _user("u1"))
    assert ei.value.status_code == 403


def test_user_collection_admin_override(monkeypatch):
    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=_no_kb)
    )
    lifecycle.check_collection_access(
        "user-other", _user("u1", role="admin")
    )  # no raise


def test_kb_owner_allowed(monkeypatch):
    monkeypatch.setattr(
        lifecycle,
        "Knowledges",
        SimpleNamespace(get_knowledge_by_id=lambda *a, **k: _kb("u1")),
    )
    lifecycle.check_collection_access("kb-1", _user("u1"))  # no raise


def test_kb_non_owner_without_acl_forbidden(monkeypatch):
    monkeypatch.setattr(
        lifecycle,
        "Knowledges",
        SimpleNamespace(get_knowledge_by_id=lambda *a, **k: _kb("other")),
    )
    monkeypatch.setattr(lifecycle, "has_access", lambda *a, **k: False)
    with pytest.raises(HTTPException) as ei:
        lifecycle.check_collection_access("kb-1", _user("u1"))
    assert ei.value.status_code == 403


def test_kb_non_owner_with_acl_allowed(monkeypatch):
    monkeypatch.setattr(
        lifecycle,
        "Knowledges",
        SimpleNamespace(get_knowledge_by_id=lambda *a, **k: _kb("other")),
    )
    monkeypatch.setattr(lifecycle, "has_access", lambda *a, **k: True)
    lifecycle.check_collection_access("kb-1", _user("u1"))  # no raise


def test_bare_collection_without_kb_row_passes(monkeypatch):
    # file-{id} / bare collection names have no KB row → not gated here
    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=_no_kb)
    )
    lifecycle.check_collection_access("file-f1", _user("u1"))  # no raise


# --------------------------------------------------------------------------
# assert_files_access (the chat-path entry point in source_resolution.py)
# --------------------------------------------------------------------------


def test_assert_blocks_client_supplied_kb_ref(monkeypatch):
    """A client injecting another user's KB id must get 403."""
    monkeypatch.setattr(
        lifecycle,
        "Knowledges",
        SimpleNamespace(get_knowledge_by_id=lambda *a, **k: _kb("other")),
    )
    monkeypatch.setattr(lifecycle, "has_access", lambda *a, **k: False)
    files = [{"id": "kb-1", "type": "collection"}]  # client-supplied, NOT trusted
    with pytest.raises(HTTPException) as ei:
        asyncio.run(source_resolution.assert_files_access(files, _user("u1")))
    assert ei.value.status_code == 403


def test_assert_skips_model_knowledge_refs(monkeypatch):
    """Model-attached KB refs are trusted and must bypass the per-user check."""

    def boom(**_):
        raise AssertionError("should not consult KB ACL for model knowledge")

    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=boom)
    )
    files = [{"id": "kb-1", "type": "collection", "__model_knowledge__": True}]
    asyncio.run(source_resolution.assert_files_access(files, _user("u1")))  # no raise


def test_assert_allows_owned_client_kb(monkeypatch):
    monkeypatch.setattr(
        lifecycle,
        "Knowledges",
        SimpleNamespace(get_knowledge_by_id=lambda *a, **k: _kb("u1")),
    )
    files = [{"id": "kb-1", "type": "collection"}]
    asyncio.run(source_resolution.assert_files_access(files, _user("u1")))  # no raise


def test_assert_user_memory_client_ref_blocked_for_other_user(monkeypatch):
    monkeypatch.setattr(
        lifecycle, "Knowledges", SimpleNamespace(get_knowledge_by_id=_no_kb)
    )
    files = [{"id": "user-other", "type": "collection"}]
    with pytest.raises(HTTPException) as ei:
        asyncio.run(source_resolution.assert_files_access(files, _user("u1")))
    assert ei.value.status_code == 403
