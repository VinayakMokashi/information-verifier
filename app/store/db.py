"""SQLite bootstrap.

A fresh connection per operation keeps things thread-safe under FastAPI's
BackgroundTasks (which may run on worker threads) without connection-sharing
headaches. Fine at current volumes; the repository layer hides it so a
Postgres swap at deployment touches nothing above this file.

sqlite-vec and the local embedding model went with the chat pivot: the
semantic cache tier they existed for was calibrated on atomic claims, which
nothing produces any more. Startup no longer imports torch.
"""
import os
import sqlite3

from app.config import settings

_BUSY_TIMEOUT_S = 30.0

_SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    job_id       TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    payload      TEXT NOT NULL,          -- full Answer as JSON
    created_at   TEXT NOT NULL
);

-- Exact-match answer cache. `key` is a digest over everything that decides
-- the answer: prompt fingerprint, model, effort, the whitelist, and the
-- normalized input. `tier` is stored OUT of the payload so the TTL can be
-- applied without deserializing every row.
CREATE TABLE IF NOT EXISTS answer_cache (
    key          TEXT PRIMARY KEY,
    tier         TEXT NOT NULL,
    payload      TEXT NOT NULL,          -- full Answer as JSON
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key          TEXT PRIMARY KEY,
    value        TEXT NOT NULL
);
"""

# Bumped when the stored shape changes incompatibly. The DB is local and
# disposable — a mismatch drops everything rather than shipping a migration
# for data nobody needs to keep.
_SCHEMA_VERSION = "2-chat"
_LEGACY_TABLES = ("reports", "claim_cache", "claim_vecs", "translation_cache",
                  "cache_meta")


def get_conn() -> sqlite3.Connection:
    # Work runs concurrently in worker threads, so several connections write
    # at once: WAL lets readers run during a write, and a generous busy
    # timeout absorbs the rest instead of raising "database is locked".
    conn = sqlite3.connect(settings.db_path, timeout=_BUSY_TIMEOUT_S)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={int(_BUSY_TIMEOUT_S * 1000)}")
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None or row["value"] != _SCHEMA_VERSION:
            # Old rows hold TruthReport JSON that no longer validates, and the
            # old caches are keyed on shapes that no longer exist.
            for table in _LEGACY_TABLES:
                conn.execute(f"DROP TABLE IF EXISTS {table}")
            conn.execute("DELETE FROM answer_cache")
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (_SCHEMA_VERSION,),
            )
