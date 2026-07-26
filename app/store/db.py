"""SQLite bootstrap.

A fresh connection per operation keeps things thread-safe under FastAPI's
BackgroundTasks (which may run on worker threads) without connection-sharing
headaches. Fine at current volumes; the repository layer hides it so a
Postgres/pgvector swap at deployment touches nothing above this file.

The semantic claim cache lives in a sqlite-vec `vec0` virtual table keyed by
claim_cache.rowid. Embeddings from different models are never comparable, so
init_db() wipes the vector table whenever the configured embedding model or
dimension changes (the exact-match cache is preserved — only vectors are
re-learned). If sqlite-vec isn't importable, everything still works without
the semantic path.
"""
import os
import sqlite3

from app.config import settings

try:
    import sqlite_vec

    VEC_AVAILABLE = True
except ImportError:  # semantic cache off; exact-match cache still works
    sqlite_vec = None
    VEC_AVAILABLE = False

_BUSY_TIMEOUT_S = 30.0

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

CREATE TABLE IF NOT EXISTS cache_meta (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL
);
"""


def get_conn() -> sqlite3.Connection:
    # Claims are processed concurrently in worker threads, so several
    # connections write at once: WAL lets readers run during a write, and a
    # generous busy timeout absorbs the remaining contention instead of
    # raising "database is locked" mid-pipeline.
    conn = sqlite3.connect(settings.db_path, timeout=_BUSY_TIMEOUT_S)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={int(_BUSY_TIMEOUT_S * 1000)}")
    if VEC_AVAILABLE:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    return conn


def _embedding_signature() -> str:
    return f"{settings.embedding_model}|{settings.embedding_dim}"


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        if not VEC_AVAILABLE:
            return

        sig = _embedding_signature()
        row = conn.execute(
            "SELECT value FROM cache_meta WHERE key = 'embedding_signature'"
        ).fetchone()
        if row is not None and row["value"] != sig:
            # Model or dimension changed -> stored vectors are meaningless.
            conn.execute("DROP TABLE IF EXISTS claim_vecs")
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS claim_vecs USING vec0("
            f"embedding float[{settings.embedding_dim}] distance_metric=cosine)"
        )
        conn.execute(
            "INSERT INTO cache_meta (key, value) VALUES ('embedding_signature', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (sig,),
        )
