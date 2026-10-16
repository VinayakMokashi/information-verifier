"""A check always ENDS — saved, billed, closed — whatever SQLite does at the end. Free.

docs/research/2026-10-15/audit-ops.md OPS-06, reproduced there (stuck_job.py):
run_check's final save was unguarded. One "database is locked" at that moment
(an owner's DB browser holding a lock past the 30 s busy timeout, a full disk)
lost the answer just paid for, skipped its ledger row, left the row PROCESSING
until a restart, and never closed the stream — so the page looped on "still
running", and the bot's chat answered every later message with "your last
check is still running", until a restart.
"""
import asyncio
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.api import stream as S
from app.config import settings
from app.engine import job as J
from app.engine.chat import ChatAnswer
from app.models.answer import Answer, AnswerSection, JobStatus, Source
from app.store.db import get_conn, init_db
from app.store.repository import AnswerRepository


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "f.db"))
    monkeypatch.setattr(J, "_SAVE_RETRY_S", (0.0, 0.0))     # no real waiting here
    init_db()
    return AnswerRepository()


@pytest.fixture(autouse=True)
def an_engine(monkeypatch):
    async def answer(text, *, heard=None, emit=None, language=None, mode="full"):
        return ChatAnswer(sections=[AnswerSection(tier="trusted", markdown="It is false.")],
                          sources=[Source(url="https://www.altnews.in/x", title="t",
                                          tier="trusted")],
                          confidence=90, tier="trusted")

    monkeypatch.setattr(J.chat, "answer", answer)


def _new(repo, status=JobStatus.QUEUED, age_s=0.0):
    answer = Answer(job_id=uuid.uuid4().hex, status=status,
                    created_at=datetime.now(timezone.utc) - timedelta(seconds=age_s),
                    input_text="5G spreads corona")
    repo.save(answer)
    return answer


def _final_save_fails(repo, monkeypatch, times):
    """Only the FINISHING save raises — `times` times, or forever with -1."""
    real, left = repo.save, [times]

    def save(answer):
        if answer.status in (JobStatus.COMPLETE, JobStatus.FAILED) and left[0] != 0:
            left[0] -= 1
            raise sqlite3.OperationalError("database is locked")
        return real(answer)

    monkeypatch.setattr(repo, "save", save)


def _run(repo, answer):
    stream = S.create(answer.job_id)
    asyncio.run(J.run_check(answer.job_id, answer.input_text, repo, stream))
    return stream


def _ledger_rows():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) FROM spend_ledger").fetchone()[0]


def test_a_repeat_from_the_cache_is_saved_once_so_a_deletion_stays_deleted(
        repo, monkeypatch):
    """REPRODUCED by review S5-8: a repeat served from the cache saved its
    finished row, and then the `finally` saved it AGAIN (INSERT OR REPLACE).
    A deletion in between (forget.py, run beside the app) was undone, and
    the person's message was back for 30 days."""
    _run(repo, _new(repo))                    # answered once, so cached
    repeat = _new(repo)
    real, finished_saves = repo.save, []

    def save(answer):
        real(answer)
        if answer.job_id == repeat.job_id and answer.status is JobStatus.COMPLETE:
            finished_saves.append(answer.job_id)
            repo.forget([answer])             # the owner deletes it right then

    monkeypatch.setattr(repo, "save", save)
    _run(repo, repeat)
    assert repo.get(repeat.job_id) is None, "the deletion was undone"
    assert finished_saves == [repeat.job_id]


def test_a_link_check_keeps_the_link_the_person_sent(repo):
    """REPRODUCED by review S5-7: the engine overwrote the stored message —
    the link — with the words it gathered, so "my check of <link>" could
    never be found to delete. What a machine read is source_text."""
    reel, heard = "https://www.instagram.com/reel/DAbCdEfGhIj/", "Sarkar har ghar ko 5000"
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                    created_at=datetime.now(timezone.utc), input_text=reel)
    repo.save(answer)
    asyncio.run(J.run_check(answer.job_id, heard, repo, S.create(answer.job_id),
                            derived_text=heard, kind="link"))
    stored = repo.get(answer.job_id)
    assert (stored.input_text, stored.source_text) == (reel, heard)


def test_a_save_that_fails_once_is_retried_and_the_answer_kept(repo, monkeypatch):
    _final_save_fails(repo, monkeypatch, times=1)
    answer = _new(repo)
    stream = _run(repo, answer)
    stored = repo.get(answer.job_id)
    assert stored.status is JobStatus.COMPLETE and stored.markdown == "It is false."
    assert stream.events[-1][1] == "done"
    assert _ledger_rows() == 1


def test_a_save_that_never_succeeds_still_bills_and_ends_the_stream(repo, monkeypatch):
    _final_save_fails(repo, monkeypatch, times=-1)
    answer = _new(repo)
    stream = _run(repo, answer)                    # and it did not raise
    assert stream.done and stream.finished_at is not None, "the stream never ended"
    kind, data = stream.events[-1][1:]
    assert kind == "error" and "send" in data["message"], "the reader was not told"
    assert _ledger_rows() == 1, "the spend never reached the ledger"


def test_a_row_that_cannot_be_read_still_ends_its_stream(repo, monkeypatch):
    def unreadable(job_id):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo, "get", unreadable)
    stream = S.create("j-unreadable")
    asyncio.run(J.run_check("j-unreadable", "5G spreads corona", repo, stream))
    assert stream.done and stream.events[-1][1] == "error"


def test_the_sweep_fails_only_what_nothing_here_is_running(repo):
    """Every few minutes, not only at a restart: a row stuck mid-flight is
    failed once it is old AND no job in this process is still on it — so a
    slow check can never be failed under its reader."""
    dead = _new(repo, JobStatus.PROCESSING, age_s=3600)
    alive = _new(repo, JobStatus.PROCESSING, age_s=3600)
    fresh = _new(repo, JobStatus.PROCESSING, age_s=60)
    done = _new(repo, JobStatus.COMPLETE, age_s=3600)

    healed = repo.sweep_stale(1800, running=lambda job_id: job_id == alive.job_id)

    assert healed == 1
    stored = repo.get(dead.job_id)
    assert stored.status is JobStatus.FAILED and "send" in stored.error
    assert repo.get(alive.job_id).status is JobStatus.PROCESSING
    assert repo.get(fresh.job_id).status is JobStatus.PROCESSING
    assert repo.get(done.job_id).status is JobStatus.COMPLETE


def test_the_server_runs_the_sweep_against_its_own_live_streams(repo):
    """The loop's one pass, with the real registry: a stuck row with no live
    stream is failed; one whose stream is still open is left alone."""
    import app.main as M

    stuck = _new(repo, JobStatus.PROCESSING, age_s=M._STUCK_AFTER_S + 60)
    slow = _new(repo, JobStatus.PROCESSING, age_s=M._STUCK_AFTER_S + 60)
    S.create(slow.job_id)                          # its job is still running
    assert asyncio.run(M._sweep_stale_once()) == 1
    assert repo.get(stuck.job_id).status is JobStatus.FAILED
    assert repo.get(slow.job_id).status is JobStatus.PROCESSING


def test_a_stream_that_never_finished_is_still_dropped_in_time(monkeypatch):
    stale = S.create("j-never-finished")
    stale.created_at = time.monotonic() - S._MAX_AGE_S - 1
    S.create("j-next")                             # creating one prunes the registry
    assert S.get("j-never-finished") is None
