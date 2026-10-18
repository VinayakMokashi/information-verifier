"""Copies of the database are found by what they ARE, never by name. Free.

Review S5-10 found three full copies of the real database in Claude's
scratch folders; the search that deleted them went by name and folder, and
the re-check (F-1) found two more it could not have found — one in %TEMP%
itself, one named *.before-upgrade. A copy of the database is people's
messages, so the search reads each file's header and, for a SQLite file,
only its table names — never a row — and deletes nothing.
"""
import sqlite3

import pytest

from app.config import settings
from scripts import find_db_copies as F


@pytest.fixture(autouse=True)
def _temp_folder(tmp_path, monkeypatch):
    """This suite's own files live in pytest's folder under %TEMP%, which
    the search collapses; here a scratch "temp" stands in for %TEMP%."""
    monkeypatch.setattr(F, "_TEMP", (tmp_path / "temp").resolve())


def _lines(out: str, needle: str) -> list[str]:
    return [line for line in out.splitlines() if needle in line]


def _real_database(tmp_path, monkeypatch, padding_kb=0):
    from app.store.db import get_conn, init_db, truncate_wal

    real = tmp_path / "data" / "verifier.db"
    real.parent.mkdir()
    monkeypatch.setattr(settings, "db_path", str(real))
    init_db()
    if padding_kb:                      # a month of answers, say
        with get_conn() as conn:
            conn.execute("INSERT INTO answer_cache (key, tier, payload, created_at) "
                         "VALUES ('k', 'trusted', ?, '2026-10-18')", ("x" * 1024 * padding_kb,))
    truncate_wal()
    return real


def _small_copy(folder, name):
    """A copy of only part of the database: VACUUM INTO after a prune, or a
    copy taken weeks ago, before the real file grew (review G-1)."""
    from app.store.db import init_db

    folder.mkdir(parents=True, exist_ok=True)
    keep = settings.db_path
    try:
        settings.db_path = str(folder / name)
        init_db()
    finally:
        settings.db_path = keep
    return folder / name


def test_a_copy_is_found_by_its_contents_whatever_its_name(tmp_path, monkeypatch, capsys):
    from app.store.db import init_db, truncate_wal

    real = tmp_path / "data" / "verifier.db"
    real.parent.mkdir()
    monkeypatch.setattr(settings, "db_path", str(real))
    init_db()
    truncate_wal()                      # as a copy of a settled database would be
    disguised = tmp_path / "scratch" / "notes.before-upgrade"
    disguised.parent.mkdir()
    disguised.write_bytes(real.read_bytes())
    other = tmp_path / "scratch" / "music.db"             # someone else's SQLite
    with sqlite3.connect(other) as conn:
        conn.execute("CREATE TABLE songs (title TEXT)")
    (tmp_path / "scratch" / "readme.txt").write_text("not a database", encoding="utf-8")

    assert F.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "SAME SIZE AS THE REAL DATABASE" in _lines(out, "notes.before-upgrade")[0]
    assert "the real database" in _lines(out, "verifier.db")[0]
    assert not _lines(out, "music.db") and not _lines(out, "readme.txt")
    assert disguised.exists() and other.exists(), "it deleted something"


def test_a_fresh_database_whose_schema_is_still_in_its_wal_is_recognised(
        tmp_path, monkeypatch, capsys):
    from app.store.db import init_db

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "data" / "verifier.db"))
    (tmp_path / "data").mkdir()
    init_db()                           # nothing checkpointed yet
    assert F.main([str(tmp_path)]) == 0
    assert _lines(capsys.readouterr().out, "verifier.db")


def test_a_copy_much_smaller_than_the_real_database_is_still_shown(
        tmp_path, monkeypatch, capsys):
    """REPRODUCED by review G-1: under half the real file's size, a copy
    was counted as "what tests and reviews make" — a compacted copy at
    once, and every copy once the real database grows. The old copies,
    past the notice's 30 days, are the ones that matter most."""
    _real_database(tmp_path, monkeypatch, padding_kb=2048)
    copy = _small_copy(tmp_path / "scratch", "copy-weeks-ago.db")
    assert copy.stat().st_size * 2 < (tmp_path / "data" / "verifier.db").stat().st_size
    assert F.main([str(tmp_path)]) == 0
    line = _lines(capsys.readouterr().out, "copy-weeks-ago.db")
    assert line and "check before deleting" in line[0]


def test_only_what_the_test_suite_makes_is_collapsed(tmp_path, monkeypatch, capsys):
    _real_database(tmp_path, monkeypatch)
    _small_copy(F._TEMP / "pytest-of-someone" / "pytest-7" / "test_x0", "t.db")
    assert F.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert not _lines(out, "t.db") and "1 database(s) in pytest's own folders" in out
    assert F.main([str(tmp_path), "--all"]) == 0
    assert _lines(capsys.readouterr().out, "t.db")


def test_a_write_ahead_log_whose_database_is_gone_is_shown(tmp_path, monkeypatch, capsys):
    """Review G-1's notes: a -wal left after its database was deleted holds
    pages of the messages written last, and has no SQLite header to find."""
    _real_database(tmp_path, monkeypatch)
    lost = tmp_path / "scratch" / "demo.db-wal"
    lost.parent.mkdir()
    lost.write_bytes(b"\x37\x7f\x06\x82" + bytes(28) + b"pages of messages")
    kept = tmp_path / "scratch" / "notes.txt-wal"         # not a WAL by its header
    kept.write_bytes(b"just text")
    assert F.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "database is gone" in _lines(out, "demo.db-wal")[0]
    assert not _lines(out, "notes.txt-wal")
