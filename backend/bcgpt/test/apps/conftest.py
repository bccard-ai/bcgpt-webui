"""Shared setup for the integration / apps test suite.

Mirrors ``bcgpt/test/unit/conftest.py``: ``bcgpt.env`` raises at import time
when ``BCGPT_AUTH=True`` (its default) and ``BCGPT_SECRET_KEY`` is unset.
Without this file, merely collecting ``bcgpt/test/apps/api/storage/test_provider.py``
fails with ``ValueError: Required environment variable not found`` because
``bcgpt.storage.provider`` transitively imports ``bcgpt.config`` → ``bcgpt.env``.

``setdefault`` is used so a real CI/dev environment is never overridden.
"""

import os

# bcgpt/env.py raises if BCGPT_AUTH is on and BCGPT_SECRET_KEY is unset.
# Use a >=32-byte key to also avoid PyJWT's InsecureKeyLengthWarning.
os.environ.setdefault("BCGPT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long-xxxx")
# SQLAlchemy engine creation is lazy; an in-memory sqlite keeps import side-effect free.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
