"""A deletion request can be honoured — by the person who promised it. Free.

The privacy notice and the bot's /delete (step 5 of the launch, 2026-10-16)
promise that a check is deleted sooner on request: the person writes with
the answer page's address (it ends in #job=…) or with the message and the
day. scripts/forget.py is how the owner keeps that promise. Without it the
promise was to hand-write SQL against the live database.
"""
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.models.answer import Answer, AnswerSection, JobStatus, ModelUsage, ReportUsage
from scripts import forget

# 06:00 UTC is 11:30 in India: the day a person would name.
_MORNING = datetime(2026, 10, 16, 6, 0, tzinfo=timezone.utc)


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    from app.store.db import init_db
    from app.store.repository import AnswerRepository

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "forget.db"))
    init_db()
    return AnswerRepository()


def _check(repo, text, *, heard=None, when=_MORNING, status=JobStatus.COMPLETE):
    """One check as the app stores it: its row, its ledger line, and a cached
    copy of the answer to its message."""
    answer = Answer(
        job_id=uuid.uuid4().hex, status=status, created_at=when, completed_at=when,
        input_text=text, source_text=heard,
        sections=[AnswerSection(tier="trusted", markdown="It is false.")],
        tier="trusted",
        usage=ReportUsage(
            models={"claude-sonnet-5": ModelUsage(calls=1, input_tokens=100,
                                                  output_tokens=900)},
            web_searches=2, estimated_usd=0.0483, llm_usd=0.0283, search_usd=0.02),
    )
    repo.save(answer)
    if status == JobStatus.COMPLETE:
        repo.ledger.record(answer, "text")
        repo.cache.put(uuid.uuid4().hex, "trusted", answer.model_dump_json())
    return answer


def _cached_messages() -> list[str]:
    with sqlite3.connect(settings.db_path) as conn:
        return [row[0] for row in conn.execute("SELECT payload FROM answer_cache")]


def _ledger_rows(job_id: str) -> int:
    with sqlite3.connect(settings.db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM spend_ledger WHERE job_id = ?",
                            (job_id,)).fetchone()[0]


def test_it_lists_first_and_deletes_only_when_told(repo, capsys):
    mine = _check(repo, "Mera number 98200 00000 hai. WHO ne kaha 5G se corona")
    assert forget.main(["--job", mine.job_id]) == 0
    out = capsys.readouterr().out
    assert mine.job_id in out and "--yes" in out
    assert repo.get(mine.job_id) is not None, "a listing deleted something"


def test_a_job_id_deletes_that_check_and_every_cached_copy_of_its_message(repo, capsys):
    mine = _check(repo, "Mera number 98200 00000 hai. WHO ne kaha 5G se corona")
    other = _check(repo, "Hot water kills the coronavirus")
    assert forget.main(["--job", mine.job_id, "--yes"]) == 0
    assert repo.get(mine.job_id) is None
    assert not any("98200" in payload for payload in _cached_messages())
    # Someone else's check, and its cached answer, are untouched.
    assert repo.get(other.job_id) is not None
    assert any("Hot water" in payload for payload in _cached_messages())
    # Invariant 10: what a check cost is kept; it never held the message.
    assert _ledger_rows(mine.job_id) == 1


def test_words_and_a_day_find_it_even_in_what_a_machine_read(repo, capsys):
    """A voice note's words are only in its transcript (source_text)."""
    voice = _check(repo, "", heard="WHO ne kaha hai ki 5G se corona phailta hai")
    later = _check(repo, "WHO ne kaha 5G se corona",
                   when=datetime(2026, 10, 17, 6, 0, tzinfo=timezone.utc))
    assert forget.main(["--text", "who NE kaha", "--day", "2026-10-16", "--yes"]) == 0
    assert repo.get(voice.job_id) is None
    assert repo.get(later.job_id) is not None        # another day: not this request


def test_the_day_is_the_day_in_india(repo, capsys):
    """20:00 UTC on the 16th is 01:30 on the 17th in India — the day the
    person would give."""
    late = _check(repo, "a late-night forward",
                  when=datetime(2026, 10, 16, 20, 0, tzinfo=timezone.utc))
    assert forget.main(["--text", "late-night", "--day", "2026-10-16"]) == 1
    assert forget.main(["--text", "late-night", "--day", "2026-10-17"]) == 0
    assert late.job_id in capsys.readouterr().out


def test_a_running_check_is_left_and_the_owner_told_why(repo, capsys):
    """Deleting a running check's row is undone when it finishes and saves
    itself again: the owner must run this again afterwards."""
    running = _check(repo, "still being checked", status=JobStatus.PROCESSING)
    assert forget.main(["--job", running.job_id, "--yes"]) == 0
    assert repo.get(running.job_id) is not None
    assert "still running" in capsys.readouterr().out


def test_a_reel_check_is_found_by_its_link_and_what_the_post_said_goes_too(repo, capsys):
    """Review S5-7: for a reel, the link IS what the person sent — they never
    typed the words a machine heard. Its transcript is kept for the next
    person who sends the same reel; a deletion request takes it too."""
    reel = "https://www.instagram.com/reel/DAbCdEfGhIj/"
    heard = "Sarkar har ghar ko 5000 rupaye de rahi hai"
    mine = _check(repo, reel, heard=heard)
    repo.transcripts.put("v2:instagram:DAbCdEfGhIj", heard)
    assert forget.main(["--text", reel, "--day", "2026-10-16", "--yes"]) == 0
    assert repo.get(mine.job_id) is None
    assert repo.transcripts.get("v2:instagram:DAbCdEfGhIj") is None
    assert "1 transcript" in capsys.readouterr().out


def test_a_pasted_address_finds_its_check(repo, capsys):
    """Review S5-7: the person sends the page's whole address; pasted as it
    came, "No check matches" — "gone anyway?" — while the check stayed."""
    mine = _check(repo, "a forward")
    address = f"https://verifier.example.com/#job={mine.job_id}"
    assert forget.main(["--job", address, "--yes"]) == 0
    assert repo.get(mine.job_id) is None


def test_one_viral_message_from_several_people_is_not_deleted_wholesale(repo, capsys):
    """REPRODUCED by review S5-18: one forward, checked by three people in a
    day. --text --yes deleted all three — two strangers' answers gone with
    no request — and the listing showed no time to pick the right one by."""
    morning, afternoon, night = (datetime(2026, 10, 16, h, 0, tzinfo=timezone.utc)
                                 for h in (4, 9, 15))         # 09:30, 14:30, 20:30 India
    checks = [_check(repo, "Kal se 2000 ke note band", when=t)
              for t in (morning, afternoon, night)]
    assert forget.main(["--text", "2000 ke note", "--day", "2026-10-16", "--yes"]) == 0
    out = capsys.readouterr().out
    assert all(repo.get(c.job_id) for c in checks), "strangers' checks were deleted"
    assert "14:30" in out and "--job" in out
    assert forget.main(["--text", "2000 ke note", "--day", "2026-10-16", "--yes",
                        "--all"]) == 0
    assert not any(repo.get(c.job_id) for c in checks)


def test_nothing_found_says_so(repo, capsys):
    assert forget.main(["--job", "0" * 32]) == 1
    out = capsys.readouterr().out
    assert "No check matches" in out
    # Not "probably gone already" — say how each kind of check is found.
    assert "#job=" in out and "words read from it" in out


def test_it_needs_a_job_or_some_words(repo):
    with pytest.raises(SystemExit):
        forget.main([])


def test_it_never_creates_a_database_that_is_not_there(tmp_path, monkeypatch, capsys):
    """A mistyped DB_PATH must not leave an empty database behind."""
    missing = tmp_path / "nowhere" / "verifier.db"
    monkeypatch.setattr(settings, "db_path", str(missing))
    assert forget.main(["--job", "abc123"]) == 2
    assert not missing.exists()
