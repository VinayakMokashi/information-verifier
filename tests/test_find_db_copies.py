"""Copies of the database are found by what they ARE, never by name. Free.

Review S5-10 found three full copies of the real database in Claude's
scratch folders; the search that deleted them went by name and folder, and
the re-check (F-1) found two more it could not have found — one in %TEMP%
itself, one named *.before-upgrade. A copy of the database is people's
messages, so the search reads each file's header and, for a SQLite file,
only its table names — never a row — and deletes nothing.
"""
import sqlite3

from app.config import settings
from scripts import find_db_copies as F


def _lines(out: str, needle: str) -> list[str]:
    return [line for line in out.splitlines() if needle in line]


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
