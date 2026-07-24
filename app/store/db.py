"""SQLite bootstrap.

A fresh connection per operation keeps things thread-safe under FastAPI's
BackgroundTasks (which may run on worker threads) without connection-sharing
headaches. Fine at Phase 1 volumes; the repository layer hides it so the
Postgres/pgvector swap in Phase 2 touches nothing above this file.
"""
import os
import sqlite3

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    job_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    payload      TEXT NOT NULL,          -- full TruthReport as JSON
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS claim_cache (
    norm_key     TEXT PRIMARY KEY,       -- normalized claim text
    verdict      TEXT NOT NULL,          -- Verdict as JSON
    created_at   TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
