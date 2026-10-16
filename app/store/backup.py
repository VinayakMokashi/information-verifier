"""A daily copy of the MONEY record — never of anyone's message.

REPRODUCED (docs/research/2026-10-15/audit-ops.md OPS-10): no backup existed,
and the obvious one — copying verifier.db while the app runs — misses what is
still in verifier.db-wal; the audit's copy had no ledger table at all. So the
copy is made by READING the live database (one snapshot, the WAL included)
into a new file.

Only the content-free tables — the spend ledger, the day's count and budget.
A full copy would keep people's messages past the 30-day promise for as long
as the copy lived (invariant 10: messages are forgotten, costs are not), and
the answers are worth nothing a month later anyway. The ledger is never
pruned, so every copy holds the whole spending history.

One a day (housekeeping runs at startup and every few hours), the last
KEEP_DAYS kept, in settings.backup_dir — by default beside the database. Point
BACKUP_DIR at a synced folder (OneDrive, a USB drive) and the copies leave
this machine with no more code: a backup on the same disk survives a deleted
file, not a dead disk.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.store.db import get_conn

KEEP_DAYS = 14
_TABLES = ("spend_ledger", "daily_checks", "daily_budget")


def _folder() -> Path:
    if settings.backup_dir:
        return Path(settings.backup_dir)
    return Path(os.path.abspath(settings.db_path)).parent / "backups"


def backup_ledger() -> Path | None:
    """Today's content-free copy, unless it exists. -> its path, or None."""
    folder = _folder()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"ledger-{datetime.now(timezone.utc):%Y-%m-%d}.db"
    if target.exists():
        return None
    temporary = target.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    live = get_conn()
    copy = sqlite3.connect(temporary)
    try:
        live.execute("BEGIN")                  # one snapshot for every table
        for table in _TABLES:
            schema = live.execute("SELECT sql FROM sqlite_master WHERE type = 'table' "
                                  "AND name = ?", (table,)).fetchone()
            if schema is None:
                continue
            copy.execute(schema[0])
            rows = [tuple(r) for r in live.execute(f"SELECT * FROM {table}")]
            if rows:
                marks = ", ".join("?" * len(rows[0]))
                copy.executemany(f"INSERT INTO {table} VALUES ({marks})", rows)
        copy.commit()
    finally:
        live.rollback()
        live.close()
        copy.close()
    os.replace(temporary, target)              # whole or not at all
    return target


def prune_backups() -> int:
    """Keep the newest KEEP_DAYS daily copies. -> how many were deleted."""
    copies = sorted(_folder().glob("ledger-*.db"), reverse=True)
    for old in copies[KEEP_DAYS:]:
        old.unlink(missing_ok=True)
    return max(0, len(copies) - KEEP_DAYS)


def restore_ledger(path) -> int:
    """Put back the ledger rows the live database lacks. INSERT OR IGNORE on
    the job id, so restoring twice never doubles the money. -> rows added."""
    source = sqlite3.connect(path)
    source.row_factory = sqlite3.Row
    try:
        rows = source.execute("SELECT * FROM spend_ledger").fetchall()
    finally:
        source.close()
    if not rows:
        return 0
    columns = rows[0].keys()
    with get_conn() as live:
        before = live.execute("SELECT COUNT(*) FROM spend_ledger").fetchone()[0]
        live.executemany(
            f"INSERT OR IGNORE INTO spend_ledger ({', '.join(columns)}) "
            f"VALUES ({', '.join('?' * len(columns))})",
            [tuple(r) for r in rows])
        after = live.execute("SELECT COUNT(*) FROM spend_ledger").fetchone()[0]
    return after - before
