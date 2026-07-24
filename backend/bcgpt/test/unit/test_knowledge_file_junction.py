"""Unit tests for the knowledge_file junction (P2.1).

The unit suite runs against ``sqlite:///:memory:`` which is connection-isolated,
so these tests stand up a shared in-memory engine (StaticPool) and monkeypatch
``get_db`` to point at it. This validates the KnowledgeFiles CRUD logic without
needing the full alembic bootstrap or a live Postgres.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import the models so File, Knowledge and KnowledgeFile are all registered in
# Base.metadata (the junction's FKs to file/knowledge must resolve at DDL time).
import bcgpt.models.files  # noqa: F401
import bcgpt.models.knowledge  # noqa: F401
import bcgpt.models.knowledge_file as kf_mod
from bcgpt.internal import Base
from bcgpt.models.knowledge_file import KnowledgeFiles


@pytest.fixture
def shared_db(monkeypatch):
    """A single shared in-memory sqlite DB for all get_db() calls in the test."""
    engine = create_engine(
        "sqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def fake_get_db():
        session = Session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    monkeypatch.setattr(kf_mod, "get_db", fake_get_db)
    yield


def test_add_and_lookup(shared_db):
    KnowledgeFiles.add("kb-j1", "f-j1", "u1")
    assert KnowledgeFiles.file_ids_for_knowledge("kb-j1") == ["f-j1"]
    assert KnowledgeFiles.knowledges_for_file("f-j1") == ["kb-j1"]


def test_add_is_idempotent(shared_db):
    KnowledgeFiles.add("kb-j2", "f-j2")
    KnowledgeFiles.add("kb-j2", "f-j2")
    assert KnowledgeFiles.file_ids_for_knowledge("kb-j2") == ["f-j2"]


def test_multiple_files_per_kb(shared_db):
    KnowledgeFiles.add("kb-j3", "f-a")
    KnowledgeFiles.add("kb-j3", "f-b")
    assert set(KnowledgeFiles.file_ids_for_knowledge("kb-j3")) == {"f-a", "f-b"}


def test_remove_single_membership(shared_db):
    KnowledgeFiles.add("kb-j4", "f-x")
    KnowledgeFiles.add("kb-j4", "f-y")
    KnowledgeFiles.remove("kb-j4", "f-x")
    assert KnowledgeFiles.file_ids_for_knowledge("kb-j4") == ["f-y"]


def test_remove_knowledge_clears_all(shared_db):
    KnowledgeFiles.add("kb-j5", "f-1")
    KnowledgeFiles.add("kb-j5", "f-2")
    KnowledgeFiles.remove_knowledge("kb-j5")
    assert KnowledgeFiles.file_ids_for_knowledge("kb-j5") == []


def test_lookup_empty_for_unknown(shared_db):
    assert KnowledgeFiles.file_ids_for_knowledge("nope") == []
    assert KnowledgeFiles.knowledges_for_file("nope") == []


def test_knowledge_for_file_multiple_kbs(shared_db):
    KnowledgeFiles.add("kb-a", "f-shared")
    KnowledgeFiles.add("kb-b", "f-shared")
    assert set(KnowledgeFiles.knowledges_for_file("f-shared")) == {"kb-a", "kb-b"}
