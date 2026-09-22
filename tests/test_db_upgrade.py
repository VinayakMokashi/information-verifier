"""Opening a database written by an OLDER version of this app.

Every other test starts from an empty temp file, which is why none of them saw
this: the first real run of the new engine died inside `init_db()` on the
REAL database with `sqlite3.OperationalError: no such module: vec0`. The old
semantic cache made `claim_vecs` a sqlite-vec VIRTUAL table, and SQLite cannot
drop a virtual table once the extension that defines it is gone — which the
pivot deliberately uninstalled. The server could not have started on the one
machine that had ever used it.

The fixture below rebuilds that exact on-disk state without needing sqlite-vec
installed: a virtual-table row in sqlite_master (rootpage 0 — a vtab owns no
b-tree, so this is a faithful copy, not corruption) plus vec0's shadow tables.
"""
import sqlite3

import pytest

from app.config import settings


@pytest.fixture()
def legacy_db(tmp_path, monkeypatch):
    path = tmp_path / "verifier.db"
    conn = sqlite3.connect(path)
    # What the pre-pivot app left behind (measured on the real file).
    conn.executescript("""
        CREATE TABLE reports (job_id TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE claim_cache (key TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE translation_cache (key TEXT PRIMARY KEY, payload TEXT);
        CREATE TABLE cache_meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE claim_vecs_info (key TEXT PRIMARY KEY, value ANY);
        CREATE TABLE claim_vecs_chunks (chunk_id INTEGER PRIMARY KEY, size INTEGER);
        CREATE TABLE claim_vecs_rowids (rowid INTEGER PRIMARY KEY, id, chunk_id);
        CREATE TABLE claim_vecs_vector_chunks00 (rowid PRIMARY KEY, vectors BLOB);
        INSERT INTO reports VALUES ('old', '{}');
        INSERT INTO translation_cache VALUES ('k', '{}');
    """)
    conn.execute("PRAGMA writable_schema=ON")
    conn.execute(
        "INSERT INTO sqlite_master (type, name, tbl_name, rootpage, sql) VALUES "
        "('table', 'claim_vecs', 'claim_vecs', 0, "
        "'CREATE VIRTUAL TABLE claim_vecs USING vec0(embedding float[256])')")
    conn.execute("PRAGMA writable_schema=OFF")
    conn.commit()
    conn.close()
    monkeypatch.setattr(settings, "db_path", str(path))
    return path


def _tables(path):
    conn = sqlite3.connect(path)
    try:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()


def test_the_fixture_reproduces_the_real_failure(legacy_db):
    """Guard on the guard: if this ever stops raising, the fixture no longer
    models the state the real database was in."""
    conn = sqlite3.connect(legacy_db)
    with pytest.raises(sqlite3.OperationalError, match="no such module: vec0"):
        conn.execute("DROP TABLE IF EXISTS claim_vecs")
    conn.close()


def test_an_old_database_opens(legacy_db):
    from app.store.db import init_db

    init_db()                                   # must not raise

    tables = _tables(legacy_db)
    assert {"answers", "answer_cache", "daily_checks", "meta"} <= tables
    # Every droppable legacy table is gone, shadow tables included...
    for gone in ("reports", "claim_cache", "translation_cache", "cache_meta",
                 "claim_vecs_info", "claim_vecs_chunks", "claim_vecs_rowids",
                 "claim_vecs_vector_chunks00"):
        assert gone not in tables, f"{gone} survived the upgrade"


def test_the_app_works_on_it_afterwards(legacy_db):
    """Opening is not enough — the new tables must be fully usable, and the
    upgrade must be recorded so it is not re-attempted on every start."""
    import uuid
    from datetime import datetime, timezone

    from app.models.answer import Answer, JobStatus
    from app.store.db import get_conn, init_db
    from app.store.repository import AnswerRepository, DailyQuota

    init_db()
    init_db()                                   # a second start is a no-op

    repo = AnswerRepository()
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.COMPLETE,
                    created_at=datetime.now(timezone.utc))
    repo.save(answer)
    assert repo.get(answer.job_id) is not None
    assert DailyQuota().take("2026-09-22", 2) is True
    with get_conn() as conn:
        version = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    assert version is not None
