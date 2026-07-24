#!/usr/bin/env python
"""Ensure the configured database exists before the backend starts.

Reads DATABASE_URL the same way the backend does (project-root .env), and:
  - sqlite: nothing to do (the file is created on demand)
  - postgres: if the server is reachable but the target database is missing,
    create it. If the server is unreachable, leave it for the backend to report.

Exit code is always 0 — this is a best-effort convenience step and must never
block the backend from starting (the backend surfaces real connection errors).
"""

import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

ROOT = Path(__file__).resolve().parent.parent


def load_database_url():
    try:
        from dotenv import find_dotenv, load_dotenv

        load_dotenv(find_dotenv(str(ROOT / ".env")))
    except ImportError:
        pass

    import os

    return os.environ.get("DATABASE_URL", "")


def ensure_postgres(url):
    try:
        import psycopg2
        from psycopg2 import sql
    except ImportError:
        # psycopg2 not installed yet — backend deps install will handle it.
        return

    parsed = urlparse(url)
    dbname = unquote(parsed.path.lstrip("/"))
    if not dbname:
        return

    conn_kwargs = dict(
        host=parsed.hostname or "localhost",
        port=parsed.port or 5432,
        user=unquote(parsed.username) if parsed.username else None,
        password=unquote(parsed.password) if parsed.password else None,
        dbname="postgres",  # connect to the default db to inspect/create
    )

    try:
        conn = psycopg2.connect(**conn_kwargs)
    except psycopg2.OperationalError as e:
        # Server unreachable / auth failed — let the backend report it.
        print(f"[ensure-db] postgres not reachable, skipping: {e}".strip())
        return

    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
        if cur.fetchone():
            print(f"[ensure-db] database '{dbname}' already exists")
        else:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(dbname)))
            print(f"[ensure-db] created database '{dbname}'")
        cur.close()
    finally:
        conn.close()


def main():
    url = load_database_url()
    if not url:
        # No DATABASE_URL configured -> backend defaults to sqlite.
        return
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        ensure_postgres(url)
    # sqlite and other backends: nothing to do.


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never block startup
        print(f"[ensure-db] skipped due to unexpected error: {e}")
    sys.exit(0)
