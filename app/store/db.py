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
_vec_broken = False  # set if loading the extension ever fails at runtime


def vec_enabled() -> bool:
    """Whether the semantic tier can actually be used right now."""
    return VEC_AVAILABLE and settings.semantic_cache_enabled and not _vec_broken


def _load_vec(conn: sqlite3.Connection) -> None:
    """Load sqlite-vec, degrading the semantic tier rather than the whole app.

    get_conn() is the only door to the database, so an exception here would
    500 every request — including reading a finished report. Extension
    loading is absent on some CPython builds (SQLITE_OMIT_LOAD_EXTENSION)
    and can fail on a wheel mismatch, so it must never be fatal.
    """
    global _vec_broken
    if not vec_enabled():
        return
    try:
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
    except Exception as exc:  # noqa: BLE001 — see docstring
        _vec_broken = True
        print(f"[db] sqlite-vec unavailable, semantic cache off: "
              f"{type(exc).__name__}: {exc}")

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

-- Content-addressed: source_hash is a digest of the exact English text a
-- translation was made from, so a re-adjudicated claim simply misses rather
-- than needing invalidation. Independent of claim_cache on purpose — the
-- summary is translated too, and it belongs to no single claim.
CREATE TABLE IF NOT EXISTS translation_cache (
    source_hash  TEXT NOT NULL,
    language     TEXT NOT NULL,
    payload      TEXT NOT NULL,          -- LocalizedClaim as JSON, or raw text
    created_at   TEXT NOT NULL,
    PRIMARY KEY (source_hash, language)
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
    _load_vec(conn)
    return conn


def _embedding_signature() -> str:
    return f"{settings.embedding_model}|{settings.embedding_dim}"


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        if not vec_enabled():
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
