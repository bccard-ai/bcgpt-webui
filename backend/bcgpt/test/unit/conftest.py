"""Shared setup for the standalone unit suite.

Some modules (e.g. ``bcgpt.utils.auth``) transitively import the config/db
layer, which requires a few environment variables at import time. Provide safe
test values here so these unit tests can import without a real deployment env.
``setdefault`` is used so a real CI/dev environment is never overridden.
"""

import os
from contextlib import contextmanager

import pytest

# bcgpt/env.py raises if BCGPT_AUTH is on and BCGPT_SECRET_KEY is unset.
# Use a >=32-byte key to also avoid PyJWT's InsecureKeyLengthWarning.
os.environ.setdefault("BCGPT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long-xxxx")
# SQLAlchemy engine creation is lazy; an in-memory sqlite keeps import side-effect free.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


@pytest.fixture
def skills_db(monkeypatch):
    """Isolated SQLite engine + ``skill`` table for skills DB tests.

    The unit suite's default ``sqlite:///:memory:`` hands peewee and SQLAlchemy
    separate in-memory databases, so the ``skill`` table created by the peewee
    migrator is not visible to the ORM session. This fixture sidesteps that by
    building a private engine, creating only the ``skill`` table on it, and
    monkeypatching ``bcgpt.models.skills.get_db`` so every ``SkillsTable`` call
    (and everything that routes through it — ``resolve_effective_skills``, the
    ``read_skill`` callable, the skills router) hits this engine. Function-scoped,
    so each test starts with an empty table.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from bcgpt.internal import Base
    from bcgpt.models import Skill

    # StaticPool + check_same_thread=False: share one in-memory SQLite connection
    # across threads so the TestClient (anyio portal thread) and asyncio callables
    # see the same schema/data the test thread set up.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine, tables=[Skill.__table__])
    Session = sessionmaker(bind=engine)

    @contextmanager
    def get_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    import bcgpt.models.skills as skills_module

    monkeypatch.setattr(skills_module, "get_db", get_db)
    yield engine
    engine.dispose()
