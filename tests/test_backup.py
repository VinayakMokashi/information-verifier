"""The money record survives a lost disk; no message is ever copied. Free.

docs/research/2026-10-15/audit-ops.md OPS-10, reproduced there
(backup_copy.py): no backup existed, and the obvious one — copying
verifier.db while the app runs — misses what is still in verifier.db-wal: in
the test the copy did not even contain the ledger table, the spend truth.
A backup holds only the content-free tables (the ledger, the day's counter
and budget): a full copy would keep people's messages past the 30-day
promise for as long as the copy lived.
"""
import shutil
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models.answer import Answer, AnswerSection, JobStatus, ReportUsage
from app.store import backup
from app.store.db import get_conn, init_db
from app.store.repository import AnswerRepository, ledger_ref


@pytest.fixture()
def live(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "data" / "verifier.db"))
    (tmp_path / "data").mkdir()
    init_db()
    return tmp_path / "data"


def _paid_check(text="My sister says the new vaccine made her infertile"):
    now = datetime.now(timezone.utc)
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.COMPLETE, created_at=now,
                    completed_at=now, input_text=text, tier="trusted",
                    sections=[AnswerSection(tier="trusted", markdown="It is false.")],
                    usage=ReportUsage(estimated_usd=0.05, llm_usd=0.04, search_usd=0.01))
    repo = AnswerRepository()
    repo.save(answer)
    repo.ledger.record(answer, "text")
    return answer


def _rows(path, table="spend_ledger"):
    with sqlite3.connect(path) as conn:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_a_backup_taken_while_the_app_writes_is_complete(live):
    """A reader holds the database open, so the checks just recorded sit in
    the WAL, as they do while the app runs: a plain file copy misses them;
    the backup does not."""
    holder = sqlite3.connect(settings.db_path)
    holder.execute("SELECT 1 FROM spend_ledger").fetchall()
    for _ in range(3):
        _paid_check()
    plain = live / "plain-copy.db"
    shutil.copyfile(settings.db_path, plain)
    try:
        copied = _rows(plain)
    except sqlite3.OperationalError:
        copied = "no ledger table at all"
    made = backup.backup_ledger()
    holder.close()
    assert made is not None and _rows(made) == 3
    assert copied != 3, "the plain copy was complete after all: the WAL case is not shown"


def test_a_backup_holds_no_message(live):
    _paid_check("A SECRET forwarded message")
    made = backup.backup_ledger()
    with sqlite3.connect(made) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "answers" not in tables and "answer_cache" not in tables
    assert b"SECRET" not in made.read_bytes()


def test_one_a_day_and_only_the_last_fortnight(live):
    _paid_check()
    first = backup.backup_ledger()
    assert backup.backup_ledger() is None, "a second one the same day"
    folder = first.parent
    for days in range(1, 20):
        old = folder / f"ledger-{(datetime.now(timezone.utc) - timedelta(days=days)):%Y-%m-%d}.db"
        old.write_bytes(first.read_bytes())
    backup.prune_backups()
    kept = sorted(p.name for p in folder.glob("ledger-*.db"))
    assert len(kept) == backup.KEEP_DAYS and first.name in kept


def test_a_backup_cannot_open_anyones_message(live):
    """REPRODUCED by review S5-12: the content-free copy kept every job id,
    and /reports/{job_id} opens that person's message for 30 days — to
    whoever can read the synced folder the copies go to."""
    answer = _paid_check()
    made = backup.backup_ledger()
    with sqlite3.connect(made) as conn:
        ids = [r[0] for r in conn.execute("SELECT job_id FROM spend_ledger")]
    assert ids == [ledger_ref(answer.job_id)] and ids != [answer.job_id]
    assert answer.job_id.encode() not in made.read_bytes()


def test_a_restore_beside_surviving_answers_never_counts_twice(live):
    """Restored rows carry the one-way reference, not the id: the backfill
    must know them, or every check whose answer survived is counted twice."""
    for _ in range(2):
        _paid_check()
    made = backup.backup_ledger()
    with get_conn() as conn:                        # only the ledger was lost
        conn.execute("DELETE FROM spend_ledger")
    assert backup.restore_ledger(made) == 2
    assert AnswerRepository().ledger.backfill_from_answers() == 0
    assert _rows(settings.db_path) == 2


def test_a_restore_then_a_sweep_never_counts_a_check_twice(live):
    """REPRODUCED by re-check F-13: a check whose final save failed keeps
    its row PROCESSING while its ledger row is written (OPS-06). Restored
    from a backup, that ledger row carries ledger_ref(); the next start's
    sweep then failed the row and wrote ITS ledger row under the raw id —
    $0.16 counted as $0.32 in the spend truth. The one writer now knows."""
    now = datetime.now(timezone.utc)
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.PROCESSING, created_at=now,
                    input_text="a forward",
                    usage=ReportUsage(estimated_usd=0.16, llm_usd=0.16, search_usd=0.0))
    repo = AnswerRepository()
    repo.save(answer)
    repo.ledger.record(answer, "text")      # billed; the finished row never saved
    made = backup.backup_ledger()
    with get_conn() as conn:                # only the ledger was lost
        conn.execute("DELETE FROM spend_ledger")
    assert backup.restore_ledger(made) == 1
    repo.sweep_orphans()                    # the next start
    with get_conn() as conn:
        rows, usd = conn.execute("SELECT COUNT(*), SUM(usd) FROM spend_ledger").fetchone()
    assert (rows, round(usd, 2)) == (1, 0.16)


def test_a_restore_brings_the_ledger_back(live):
    for _ in range(2):
        _paid_check()
    made = backup.backup_ledger()
    with get_conn() as conn:                        # the disk "dies"
        conn.execute("DELETE FROM spend_ledger")
    assert backup.restore_ledger(made) == 2
    assert _rows(settings.db_path) == 2
    assert backup.restore_ledger(made) == 0, "a second restore doubled the money"
