"""Find copies of this project's database, by what a file IS. Free, local.

    .venv\\Scripts\\python.exe scripts\\find_db_copies.py              # %TEMP% and this folder
    .venv\\Scripts\\python.exe scripts\\find_db_copies.py D:\\folder
    .venv\\Scripts\\python.exe scripts\\find_db_copies.py --all        # pytest's own too

A copy of the database is people's messages, and every deletion the privacy
notice promises misses a copy in a scratch folder (CLAUDE.md). A search by
name and folder missed two (review F-1, 2026-10-17: one in %TEMP% itself,
made by tempfile.mkdtemp's default; one named *.before-upgrade). So this
reads each file's first 16 bytes for SQLite's header, and for a SQLite file
only its table names (read-only and immutable; a WAL-only schema read-only)
— never a row — and deletes nothing: the owner decides.

What it shows: the real database and the app's own backups, marked; EVERY
other database of this project's schema, whatever its size — the real
file's exact size is only an extra mark. By size, a compacted copy hid at
once, and every copy would once the real file grew (review G-1). Also a
write-ahead log whose database is gone: it holds pages of whatever was
written last, and has no SQLite header to find. Only pytest's own folders
under %TEMP%, which the test suite alone writes, are counted rather than
listed, unless --all.
"""
import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402

_MAGIC = b"SQLite format 3\x00"
_WAL_MAGIC = (b"\x37\x7f\x06\x82", b"\x37\x7f\x06\x83")     # SQLite's WAL header
# Tables only this project's databases have, in any schema it ever used.
_OURS = {"answers", "answer_cache", "spend_ledger", "transcript_cache",
         "reports", "claim_cache", "claim_vecs"}
_SKIP = {".venv", ".git", "node_modules", "__pycache__", ".mypy_cache"}
_TEMP = Path(tempfile.gettempdir()).resolve()    # a seam: the tests move it


def _read_tables(uri: str) -> set[str]:
    conn = sqlite3.connect(uri, uri=True)
    try:
        return {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'")}
    finally:
        conn.close()


def _tables(path: Path) -> set[str]:
    base = path.resolve().as_uri()
    try:
        found = _read_tables(f"{base}?mode=ro&immutable=1")   # writes nothing beside it
        if not found and Path(f"{path}-wal").exists():
            # A fresh database's schema can still sit in its -wal, which an
            # immutable read ignores.
            found = _read_tables(f"{base}?mode=ro")
        return found
    except sqlite3.Error:
        return set()


def _starts_with(path: Path, magic: tuple[bytes, ...]) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(len(magic[0])) in magic
    except OSError:
        return False


def _orphaned_wal(path: Path) -> bool:
    """A -wal whose database is gone: nothing will ever fold it back in."""
    return (path.name.endswith("-wal") and not Path(str(path)[:-4]).exists()
            and _starts_with(path, _WAL_MAGIC))


def _made_by_the_suite(resolved: Path) -> bool:
    """Under %TEMP%\\pytest-of-<user>\\: where pytest puts each test's tmp_path."""
    try:
        return resolved.relative_to(_TEMP).parts[0].startswith("pytest-of-")
    except (ValueError, IndexError):
        return False


def main(argv: list[str] | None = None) -> int:
    force_utf8_stdout()
    args = list(sys.argv[1:] if argv is None else argv)
    show_all = "--all" in args
    roots = [a for a in args if a != "--all"] or [
        os.environ.get("TEMP", ""), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))]
    real = Path(os.path.abspath(settings.db_path)).resolve()
    real_size = real.stat().st_size if real.exists() else None
    backups = (Path(settings.backup_dir) if settings.backup_dir
               else real.parent / "backups").resolve()
    shown, suites = [], 0
    for root in filter(None, roots):
        for folder, dirs, files in os.walk(root):
            dirs[:] = [d for d in dirs if d not in _SKIP]
            for name in files:
                path = Path(folder) / name
                if _starts_with(path, (_MAGIC,)):
                    if not _tables(path) & _OURS:
                        continue
                    wal = False
                elif _orphaned_wal(path):
                    wal = True
                else:
                    continue
                try:
                    stat, resolved = path.stat(), path.resolve()
                except OSError:
                    continue                      # gone while the walk ran
                if resolved == real:
                    what = "the real database"
                elif backups in resolved.parents:
                    what = "the app's own backup"
                elif _made_by_the_suite(resolved) and not show_all:
                    suites += 1
                    continue
                elif wal:
                    what = ("a write-ahead log whose database is gone — it can hold pages "
                            "of messages: check what made it before deleting")
                elif real_size and stat.st_size == real_size:
                    what = "SAME SIZE AS THE REAL DATABASE — almost certainly a copy: delete it"
                else:
                    what = "this project's — a copy, or a test's? check before deleting"
                shown.append((stat.st_size, stat.st_mtime, path, what))
    for size, mtime, path, what in sorted(shown, key=lambda s: -s[0]):
        print(f"{size:>10}  {datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}  {path}  [{what}]")
    if suites:
        print(f"+ {suites} database(s) in pytest's own folders under %TEMP% — what the "
              "test suite makes; --all lists them.")
    print("Nothing was deleted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
