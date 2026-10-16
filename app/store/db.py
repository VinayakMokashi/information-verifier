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

-- The deployment-wide daily check counter. Persisted, not in memory: an
-- in-memory counter reset on every restart, and under `--reload` that is every
-- saved file — a "2 checks a day" cap that a restart quietly refills is not a
-- cap. `day` is the operator's calendar day (see day_boundary_utc_offset_min).
-- No personal data: one integer per day.
CREATE TABLE IF NOT EXISTS daily_checks (
    day          TEXT PRIMARY KEY,
    used         INTEGER NOT NULL
);

-- The deployment-wide daily DOLLAR budget (Vinayak, 2026-10-15: $1 a day).
-- What today's finished checks cost plus what the running ones reserved: a
-- check reserves its worst case before any spend and settles at its real
-- cost when it ends. Integer micro-dollars, so the conditional reservation
-- compares exactly. Persisted like daily_checks; no personal data.
CREATE TABLE IF NOT EXISTS daily_budget (
    day              TEXT PRIMARY KEY,
    committed_micro  INTEGER NOT NULL
);

-- One row /ready writes and reads back: a database that cannot take a
-- write is not ready, however fast a read answers (audit-ops OPS-18).
CREATE TABLE IF NOT EXISTS ready_probe (
    id  INTEGER PRIMARY KEY,
    at  TEXT NOT NULL
);

-- What a pasted link SAID (caption + subtitles or ASR transcript), keyed by
-- the platform's own video id — known for free at resolve time, before any
-- download or ASR is bought. One viral reel forwarded by fifty people used to
-- re-download and re-buy its transcription fifty times.
-- One row per finished check: what it cost and what kind it was, and NOTHING
-- the person sent. Answers (which hold messages) are deleted after
-- answer_retention_days; this ledger is what lets the spending dashboard keep
-- its history anyway. Written by run_check and fail_job.
CREATE TABLE IF NOT EXISTS spend_ledger (
    job_id              TEXT PRIMARY KEY,
    day                 TEXT NOT NULL,   -- the operator's day, as the cap counts
    finished_at         TEXT NOT NULL,   -- UTC ISO
    kind                TEXT NOT NULL,   -- text | image | media | link |
                                         -- unknown (a backfill could not
                                         -- tell) | ab-test | probe
    status              TEXT NOT NULL,   -- COMPLETE | FAILED
    tier                TEXT NOT NULL,
    cached              INTEGER NOT NULL,
    usd                 REAL NOT NULL,
    llm_usd             REAL NOT NULL,
    search_usd          REAL NOT NULL,
    asr_usd             REAL NOT NULL,
    input_tokens        INTEGER NOT NULL,
    output_tokens       INTEGER NOT NULL,
    cache_write_tokens  INTEGER NOT NULL,
    cache_read_tokens   INTEGER NOT NULL,
    web_searches        INTEGER NOT NULL,
    asr_seconds         REAL NOT NULL,
    models              TEXT NOT NULL,   -- comma-joined model ids
    search_errors       TEXT NOT NULL DEFAULT ''  -- "code:n,..." codes only
);
CREATE INDEX IF NOT EXISTS spend_ledger_day ON spend_ledger (day);

CREATE TABLE IF NOT EXISTS transcript_cache (
    key          TEXT PRIMARY KEY,       -- "v1:<platform>:<video id>"
    text         TEXT NOT NULL,
    created_at   TEXT NOT NULL
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


def _drop_legacy(conn: sqlite3.Connection) -> None:
    """Remove what the pre-pivot app left behind, including what can't be.

    MEASURED on the first real run of the new engine: `DROP TABLE claim_vecs`
    raised `no such module: vec0` and took `init_db()` — and so the server's
    startup — down with it. `claim_vecs` was a sqlite-vec VIRTUAL table, and
    SQLite cannot drop a virtual table once the extension that defines it is
    gone, which the pivot deliberately uninstalled.

    So: its shadow tables (plain tables, found by name because vec0 numbers
    them) are dropped, and the virtual table's own schema entry is left in
    place. That entry owns no storage (rootpage 0) and nothing reads it, so it
    is inert. Removing it would need PRAGMA writable_schema surgery on the
    user's own database at every startup — not a trade worth making to save
    one row of schema.
    """
    shadows = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' "
        "AND name LIKE 'claim\\_vecs\\_%' ESCAPE '\\'")]
    for table in (*_LEGACY_TABLES, *shadows):
        try:
            conn.execute(f'DROP TABLE IF EXISTS "{table}"')
        except sqlite3.OperationalError as exc:
            if "no such module" not in str(exc):
                raise
            print(f"[db] left legacy virtual table {table!r} in place "
                  f"(its extension is uninstalled; it is inert): {exc}")


def _add_missing_columns(conn: sqlite3.Connection) -> None:
    """Columns added to a table that already exists on a real database.

    CREATE TABLE IF NOT EXISTS leaves an existing table as it was, and
    bumping _SCHEMA_VERSION is no answer for the ledger: its rows are the
    spending history, which outlives every answer on purpose.
    """
    have = {r[1] for r in conn.execute("PRAGMA table_info(spend_ledger)")}
    if "search_errors" not in have:
        conn.execute("ALTER TABLE spend_ledger "
                     "ADD COLUMN search_errors TEXT NOT NULL DEFAULT ''")


def init_db() -> None:
    os.makedirs(os.path.dirname(settings.db_path) or ".", exist_ok=True)
    with get_conn() as conn:
        conn.executescript(_SCHEMA)
        _add_missing_columns(conn)
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
        if row is None or row["value"] != _SCHEMA_VERSION:
            # Old rows hold TruthReport JSON that no longer validates, and the
            # old caches are keyed on shapes that no longer exist.
            _drop_legacy(conn)
            conn.execute("DELETE FROM answer_cache")
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (_SCHEMA_VERSION,),
            )
