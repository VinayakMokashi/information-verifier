"""Messages are forgotten on schedule; what they cost is not. Free.

To-do 7 (2026-09-22): every stranger's message was kept forever — the
answers table held the forward, what a machine read from it, and the reply,
and nothing ever deleted a row. Now answers go after answer_retention_days,
and the spend ledger keeps the costs with none of the content, so the
spending dashboard still has its history.
"""
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.models.answer import Answer, AnswerSection, JobStatus, ModelUsage, ReportUsage


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    from app.store.db import init_db
    from app.store.repository import AnswerRepository

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "retention.db"))
    init_db()
    return AnswerRepository()


def _answer(days_old: float, status=JobStatus.COMPLETE, text="a private forward"):
    when = datetime.now(timezone.utc) - timedelta(days=days_old)
    return Answer(
        job_id=uuid.uuid4().hex, status=status, created_at=when, completed_at=when,
        input_text=text, source_text="what the machine heard",
        sections=[AnswerSection(tier="trusted", markdown="It is false.")],
        tier="trusted",
        usage=ReportUsage(
            models={"claude-sonnet-5": ModelUsage(calls=1, input_tokens=100,
                                                  output_tokens=900)},
            web_searches=2, estimated_usd=0.0483, llm_usd=0.0283, search_usd=0.02),
    )


def test_a_deleted_message_leaves_no_bytes_in_the_database_files(repo, monkeypatch):
    """REPRODUCED by review S5-11: secure_delete was off, so forget() and the
    30-day prune made a message unreadable through the app while its bytes
    stayed in the database file (twice: the row and its cached copy) until
    SQLite happened to reuse those pages — and in every copy of the file."""
    from pathlib import Path

    from app.store.repository import housekeeping

    monkeypatch.setattr(settings, "answer_retention_days", 30)
    fresh = _answer(1, text="Mera number 98200 11111 hai, REMNANT-ONE")
    old = _answer(45, text="Purana forward, REMNANT-TWO")
    repo.save(fresh)
    repo.cache.put("k1", "trusted", fresh.model_dump_json())
    repo.save(old)
    repo.forget([fresh])                      # a deletion request
    housekeeping()                            # the 30-day prune takes `old`
    files = [Path(settings.db_path), Path(settings.db_path + "-wal")]
    data = b"".join(p.read_bytes() for p in files if p.exists())
    assert b"REMNANT-ONE" not in data and b"REMNANT-TWO" not in data


def _reader_holding_a_snapshot():
    """Another program reading the database — a DB browser left open on it."""
    reader = sqlite3.connect(settings.db_path)
    reader.execute("BEGIN")
    reader.execute("SELECT COUNT(*) FROM answers").fetchall()
    return reader


def test_the_wal_truncate_never_holds_writers_long_and_says_when_it_could_not(repo):
    """REPRODUCED by re-check F-7: with a reader open, TRUNCATE took the
    writer lock and waited out the 30 s busy timeout — every save, claim and
    ledger write in the app waited with it — then gave up without a word,
    the deleted message still in the WAL."""
    import time

    from app.store.db import truncate_wal

    repo.save(_answer(1))                     # something in the WAL
    reader = _reader_holding_a_snapshot()
    try:
        started = time.monotonic()
        clean = truncate_wal()
        took = time.monotonic() - started
    finally:
        reader.rollback()
        reader.close()
    assert clean is False and took < 5, (clean, took)
    assert truncate_wal() is True             # once nobody is reading


def test_forget_says_when_the_file_still_holds_the_old_copy(repo, monkeypatch, capsys):
    from app.store import repository
    from scripts import forget

    answer = _answer(1, text="a forward to delete")
    repo.save(answer)
    monkeypatch.setattr(repository, "truncate_wal", lambda: False)
    assert forget.main(["--job", answer.job_id, "--yes"]) == 0
    out = capsys.readouterr().out
    assert "still" in out and "close any program" in out


def test_a_start_survives_a_rewrite_that_cannot_run(repo, monkeypatch, capsys):
    """REPRODUCED by re-check F-11: the one-time VACUUM was the only
    unguarded write at startup, so an open write transaction on the file
    failed the start — where before it only slowed it."""
    from fastapi.testclient import TestClient

    import app.store.db as D
    from app.main import app

    def locked():
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(D, "vacuum_once", locked)
    with TestClient(app):
        pass
    assert "next start" in capsys.readouterr().out


def test_the_rewrite_is_marked_done_only_once_it_reached_the_file(repo):
    """Re-check F-11's other half: a reader held at that moment let the
    VACUUM land only in the WAL, yet the flag already said done — so the
    old free pages stayed until some later checkpoint."""
    from app.store.db import vacuum_once

    repo.save(_answer(1))
    reader = _reader_holding_a_snapshot()
    try:
        assert vacuum_once() is False         # could not finish: not marked
    finally:
        reader.rollback()
        reader.close()
    assert vacuum_once() is True              # tried again, finished
    assert vacuum_once() is False             # and never again


def test_what_was_deleted_before_secure_delete_is_gone_after_one_start(repo):
    """secure_delete covers deletions from now on. The real database already
    held earlier ones' bytes in its free pages (the answer cache had been
    pruning messages for weeks), so the first start rewrites the file once."""
    from pathlib import Path

    from fastapi.testclient import TestClient

    from app.main import app

    raw = sqlite3.connect(settings.db_path)          # the old way: no secure_delete
    raw.execute("PRAGMA secure_delete = OFF")
    raw.execute("INSERT INTO answer_cache (key, tier, payload, created_at) "
                "VALUES ('k', 'trusted', 'OLD-REMNANT ' || hex(randomblob(2000)), '2026-01-01')")
    raw.commit()
    raw.execute("DELETE FROM answer_cache")
    raw.commit()
    raw.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    raw.close()
    assert b"OLD-REMNANT" in Path(settings.db_path).read_bytes(), "nothing to remove"
    with TestClient(app):
        pass
    files = [Path(settings.db_path), Path(settings.db_path + "-wal")]
    assert b"OLD-REMNANT" not in b"".join(p.read_bytes() for p in files if p.exists())


def test_old_answers_are_deleted_and_recent_ones_kept(repo, monkeypatch):
    monkeypatch.setattr(settings, "answer_retention_days", 30)
    old, recent = _answer(45), _answer(2)
    for a in (old, recent):
        repo.save(a)
    assert repo.prune() == 1
    assert repo.get(old.job_id) is None
    assert repo.get(recent.job_id) is not None


def test_an_in_flight_job_is_never_deleted(repo, monkeypatch):
    """Only finished answers go; sweep_orphans owns abandoned ones."""
    monkeypatch.setattr(settings, "answer_retention_days", 30)
    running = _answer(45, status=JobStatus.PROCESSING)
    repo.save(running)
    assert repo.prune() == 0
    assert repo.get(running.job_id) is not None


def test_the_cost_survives_the_message(repo, monkeypatch):
    """The whole point of the ledger: delete the forward, keep the bill."""
    monkeypatch.setattr(settings, "answer_retention_days", 30)
    old = _answer(45)
    repo.save(old)
    repo.ledger.record(old, "text")
    repo.prune()

    assert repo.get(old.job_id) is None
    totals = repo.ledger.totals()
    assert totals["checks"] == 1
    assert totals["usd"] == pytest.approx(0.0483)
    assert totals["search_usd"] == pytest.approx(0.02)


def test_the_ledger_holds_no_message_content(repo):
    """Checked against the schema itself, not just what we happen to write."""
    a = _answer(1, text="SECRET forwarded words")
    # Even a bill whose error map was built by hand, bypassing the meter's
    # sanitising: the ledger keeps code-shaped names only.
    a.usage.search_errors = {"SECRET forwarded words": 1, "unavailable": 1}
    repo.ledger.record(a, "text")
    conn = sqlite3.connect(settings.db_path)
    columns = [r[1] for r in conn.execute("PRAGMA table_info(spend_ledger)")]
    everything = " ".join(str(v) for v in conn.execute(
        "SELECT * FROM spend_ledger").fetchone())
    conn.close()
    for forbidden in ("input_text", "source_text", "payload", "markdown", "sections"):
        assert forbidden not in columns
    assert "SECRET" not in everything and "machine heard" not in everything


def test_failed_searches_reach_the_ledger_and_the_dashboard_rows(repo):
    """So a check that paid for searches and kept nothing says why, after
    the console is gone and after the answer itself is deleted."""
    a = _answer(1)
    a.usage.search_errors = {"too_many_requests": 2, "max_uses_exceeded": 3}
    repo.ledger.record(a, "link")
    (row,) = repo.ledger.recent(5)
    assert row["search_errors"] == "max_uses_exceeded:3,too_many_requests:2"


def test_a_clean_check_records_no_search_errors(repo):
    repo.ledger.record(_answer(1), "text")
    (row,) = repo.ledger.recent(5)
    assert row["search_errors"] == ""


def test_an_existing_ledger_gains_the_column_and_keeps_its_rows(tmp_path, monkeypatch):
    """The real database already has a spend ledger. MEASURED 2026-09-22: a
    server that could not start on the one real database is the failure a
    schema change must not repeat — and the rows are the spending history."""
    from app.store.db import init_db
    from app.store.repository import AnswerRepository

    path = tmp_path / "old.db"
    monkeypatch.setattr(settings, "db_path", str(path))
    init_db()
    conn = sqlite3.connect(path)
    conn.execute("ALTER TABLE spend_ledger DROP COLUMN search_errors")
    conn.execute(
        "INSERT INTO spend_ledger VALUES ('old', '2026-09-23', "
        "'2026-09-22T22:49:59+00:00', 'link', 'COMPLETE', 'none', 0, 0.2559, "
        "0.19, 0.05, 0.012, 1, 1, 1, 1, 5, 127.9, 'claude-sonnet-5')")
    conn.commit()
    conn.close()

    init_db()
    init_db()                                     # and idempotently
    ledger = AnswerRepository().ledger
    assert ledger.totals()["usd"] == pytest.approx(0.2559)
    (row,) = ledger.recent(5)
    assert row["search_errors"] == ""


def test_recording_is_idempotent(repo):
    a = _answer(1)
    repo.ledger.record(a, "text")
    repo.ledger.record(a, "text")
    assert repo.ledger.totals()["checks"] == 1


def test_checks_that_predate_the_ledger_are_backfilled(repo):
    """So the first paid runs appear on the dashboard the first time it
    opens, not only checks made after it existed."""
    a = _answer(1)
    repo.save(a)
    assert repo.ledger.totals()["checks"] == 0
    assert repo.ledger.backfill_from_answers() == 1
    assert repo.ledger.backfill_from_answers() == 0          # once only
    assert repo.ledger.totals()["usd"] == pytest.approx(0.0483)


@pytest.mark.parametrize("input_text, source_text, kind", [
    ("Drinking hot water kills the coronavirus", None, "text"),
    # A failed link check keeps its URL — and so does a text check on a
    # pasted news URL, which is not a platform link and goes to /verify/text.
    # The row cannot tell them apart (found by review of the first guess).
    ("https://www.instagram.com/reel/DbsVyqLpbRa/", None, "unknown"),
    ("https://www.bbc.com/news/world-asia-india-123", None, "unknown"),
    ("Https://www.instagram.com/reel/DbsVyqLpbRa/", None, "unknown"),
    ("", None, "media"),                               # its transcription failed
    # Finished with machine-read text: a link, a screenshot or a voice note —
    # the stored row cannot say which, so the ledger does not pretend to.
    ("WHO ne kaha 5G se corona", "WHO ne kaha 5G se corona", "unknown"),
])
def test_a_backfilled_kind_is_only_what_the_row_can_prove(repo, input_text,
                                                          source_text, kind):
    """Found by review, reproduced: run_check overwrites input_text with the
    text it gathered, so the "starts with https://" test never fired for a
    finished link check, and every link and screenshot check was backfilled
    as "media" — "Voice / video" on the dashboard — while a voice note whose
    transcription failed (input_text "") was backfilled as "text"."""
    a = _answer(1, text=input_text)
    a.source_text = source_text
    repo.save(a)
    repo.ledger.backfill_from_answers()
    assert [r["kind"] for r in repo.ledger.recent(5)] == [kind]


def test_a_backfill_never_overwrites_a_kind_the_live_path_knew(repo):
    """Found by review, reproduced: the backfill SELECTs rows with no ledger
    entry, but a live record — which KNOWS the kind — can land between that
    SELECT and its write, and INSERT OR REPLACE clobbered it with a guess."""
    a = _answer(1, text="https://www.instagram.com/reel/DbsVyqLpbRa/")
    a.source_text = "what the reel said"
    repo.save(a)
    repo.ledger.record(a, "link")                     # the live path, first
    repo.ledger.backfill_from_answers()               # the guess, after
    rows = repo.ledger.recent(5)
    assert [r["kind"] for r in rows] == ["link"]
    assert len(rows) == 1


def test_the_dashboard_names_every_kind_the_ledger_can_hold():
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "app" / "api" / "dashboard.html"
            ).read_text(encoding="utf-8")
    table = page[page.index("const KIND = {"):page.index("};", page.index("const KIND = {"))]
    for kind in ("text", "link", "image", "media", "unknown", '"ab-test"', "probe"):
        assert f"{kind}:" in table, f"no label for {kind}"


def test_a_failing_housekeeping_step_does_not_stop_the_others(repo, monkeypatch):
    from app.store import repository as R

    monkeypatch.setattr(settings, "answer_retention_days", 30)
    old = _answer(45)
    repo.save(old)

    def broken(self):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(R.SpendLedger, "backfill_from_answers", broken)
    done = R.housekeeping()
    assert done["ledger_backfilled"] == -1
    assert done["answers_deleted"] == 1          # still ran


def test_the_bill_breakdown_adds_up():
    from app.providers.usage import UsageMeter

    meter = UsageMeter()
    meter.note_llm("claude-sonnet-5", type("U", (), {
        "input_tokens": 122, "output_tokens": 901,
        "cache_creation_input_tokens": 9705, "cache_read_input_tokens": 24002,
        "server_tool_use": type("S", (), {"web_search_requests": 1})()})())
    meter.note_asr(70.1)
    bill = meter.snapshot()
    assert bill.search_usd == pytest.approx(0.01)
    assert bill.asr_usd > 0
    assert bill.llm_usd + bill.search_usd + bill.asr_usd == pytest.approx(
        bill.estimated_usd, abs=1e-4)
    # The first real check's measured tokens reproduce its measured bill.
    assert bill.llm_usd + bill.search_usd == pytest.approx(0.0483, abs=1e-4)


def test_every_route_check_lands_in_the_ledger_with_its_kind(client):
    """End to end, through the real routes."""
    from app.api import routes as R

    client.post("/api/v1/verify/text", json={"text": "a claim"})
    client.post("/api/v1/verify/link",
                json={"url": "https://www.instagram.com/reel/DbsVyqLpbRa/"})
    kinds = sorted(r["kind"] for r in R._repo.ledger.recent(10))
    assert kinds == ["link", "text"]


def test_the_cap_and_the_dashboard_agree_on_what_today_is():
    from app.api import limits
    from app.store.repository import operator_day

    assert limits.today() == operator_day()


def test_a_bill_written_before_the_split_existed_is_split_correctly(repo):
    """MEASURED on the first live dashboard: three checks stored before bills
    carried llm/search/asr made the breakdown show $0.09 of searches where
    $0.15 had been bought. The split is recoverable from what was stored."""
    old = _answer(1)
    old.usage = ReportUsage(      # the pre-split shape: a total and the counts
        models={"claude-sonnet-5": ModelUsage(calls=1, input_tokens=122,
                                              output_tokens=901,
                                              cache_write_tokens=9705,
                                              cache_read_tokens=24002)},
        web_searches=1, estimated_usd=0.0483)
    repo.save(old)
    repo.ledger.backfill_from_answers()
    totals = repo.ledger.totals()
    assert totals["search_usd"] == pytest.approx(0.01)
    assert totals["llm_usd"] + totals["search_usd"] == pytest.approx(0.0483, abs=1e-4)
