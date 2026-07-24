"""Import-safety tests for Phase 1 of ADR Option D.

Verifies that ``BCGPT_SKIP_IMPORT_TIME_MIGRATIONS`` suppresses all import-time
DB writes in ``bcgpt.config`` and ``bcgpt.internal.db``.

Each test runs in an isolated subprocess so module-level side effects are
re-evaluated from scratch (no ``sys.modules`` caching interference).

See ``BACKEND_ARCHITECTURE_TESTABILITY_PLAN_2026-06-23.md`` §5 Phase 1.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]

_REQUIRED_ENV = {
    "BCGPT_SECRET_KEY": "test-secret-key-at-least-32-bytes-long-xxxx",
}


def _run_subprocess(
    script: str,
    extra_env: dict[str, str] | None = None,
    *,
    unset: set[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Execute *script* in a clean Python process with env vars merged."""
    env = {**os.environ, **_REQUIRED_ENV, **(extra_env or {})}
    for key in unset or set():
        env.pop(key, None)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_import_config_skips_migrations_when_env_set() -> None:
    """BCGPT_SKIP_IMPORT_TIME_MIGRATIONS set → ``import bcgpt.config`` does not
    run migrations; ``CONFIG_DATA`` falls back to ``DEFAULT_CONFIG``."""
    script = (
        "import sys; sys.path.insert(0, 'backend'); "
        "import bcgpt.config; "
        "from bcgpt.config import CONFIG_DATA, DEFAULT_CONFIG; "
        "assert CONFIG_DATA is DEFAULT_CONFIG, "
        "'CONFIG_DATA should be DEFAULT_CONFIG when migrations are skipped'; "
        "print('CONFIG_IMPORT_SAFE_OK')"
    )
    result = _run_subprocess(
        script,
        {
            "BCGPT_SKIP_IMPORT_TIME_MIGRATIONS": "1",
            "DATABASE_URL": "sqlite:///:memory:",
        },
    )
    assert result.returncode == 0, (
        f"Import-safety check failed (exit {result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "CONFIG_IMPORT_SAFE_OK" in result.stdout


def test_import_db_skips_peewee_migration_when_env_set(tmp_path: Path) -> None:
    """BCGPT_SKIP_IMPORT_TIME_MIGRATIONS set → ``import bcgpt.internal.db``
    does not run Peewee migrations (file-based SQLite stays empty)."""
    db_file = tmp_path / "peewee_skip_check.db"
    script = (
        "import sys; sys.path.insert(0, 'backend'); "
        "import bcgpt.internal.db; "
        "import sqlite3; "
        f"conn = sqlite3.connect('{db_file}'); "
        "tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall(); "
        "conn.close(); "
        "assert len(tables) == 0, f'Peewee migration ran despite skip flag: {tables}'; "
        "print('PEEWEE_SKIP_OK')"
    )
    result = _run_subprocess(
        script,
        {
            "BCGPT_SKIP_IMPORT_TIME_MIGRATIONS": "1",
            "DATABASE_URL": f"sqlite:///{db_file}",
        },
    )
    assert result.returncode == 0, (
        f"Peewee skip check failed (exit {result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "PEEWEE_SKIP_OK" in result.stdout


def test_import_config_runs_migrations_when_env_unset(tmp_path: Path) -> None:
    """Baseline: without the env var, Alembic migrations run and create tables
    (backward compat).  ``CONFIG_DATA`` still equals ``DEFAULT_CONFIG`` because
    the freshly migrated ``config`` table has zero rows — the proof is that
    tables exist at all."""
    db_file = tmp_path / "backward_compat.db"
    script = (
        "import sys; sys.path.insert(0, 'backend'); "
        "import bcgpt.config; "
        "import sqlite3; "
        f"conn = sqlite3.connect('{db_file}'); "
        "tables = conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall(); "
        "conn.close(); "
        "assert len(tables) > 0, 'Migrations should have created tables (backward compat)'; "
        "print('CONFIG_MIGRATION_OK')"
    )
    result = _run_subprocess(
        script,
        {"DATABASE_URL": f"sqlite:///{db_file}"},
        unset={"BCGPT_SKIP_IMPORT_TIME_MIGRATIONS"},
    )
    assert result.returncode == 0, (
        f"Backward-compat check failed (exit {result.returncode}):\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "CONFIG_MIGRATION_OK" in result.stdout
