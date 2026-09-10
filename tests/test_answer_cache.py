"""The answer cache and the job runner. Free — the engine is stubbed.

The semantic tier is gone with the old pipeline, so this is exact-match only.
That makes two things load-bearing: normalization has to survive the
invisible junk real forwards carry, and a TTL is mandatory because "no
fact-checker has covered this" is wrong the day one does.
"""
import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.config import settings
from app.engine import job as J
from app.engine.chat import ChatAnswer
from app.models.answer import Answer, AnswerSection, JobStatus, Source
from app.store.db import get_conn, init_db
from app.store.repository import AnswerRepository, _normalize_input


@pytest.fixture()
def repo(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "a.db"))
    init_db()
    return AnswerRepository()


def _new(repo, text="WHO ne kaha 5G se corona") -> Answer:
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                    created_at=datetime.now(timezone.utc), input_text=text)
    repo.save(answer)
    return answer


def _chat_answer(tier="trusted", md="It is false."):
    return ChatAnswer(
        sections=[AnswerSection(tier=tier, markdown=md)],
        sources=[Source(url="https://www.altnews.in/x", title="t", tier=tier)],
        confidence=90, tier=tier,
    )


# -- normalization -------------------------------------------------------------

def test_invisible_junk_does_not_cause_a_re_bill():
    """Indic keyboards emit ZWJ/ZWNJ and a copy-paste can carry a BOM. Each
    would be a full miss and a full re-bill of an identical forward."""
    plain = "WHO ne kaha 5G se corona"
    messy = "﻿WHO ne​ kaha  5G‍ se corona  "
    assert _normalize_input(plain) == _normalize_input(messy)


def test_case_and_unicode_forms_fold_together():
    assert _normalize_input("5G SE CORONA") == _normalize_input("5g se corona")
    # NFKC: a decomposed and a composed Devanagari form are the same message.
    assert _normalize_input("क्ष") == _normalize_input("क्ष")


@pytest.mark.parametrize("a,b", [
    ("5G is safe", "5G is not safe"),
    ("He died in 2019", "He died in 2020"),
    ("Modi said X", "Modi said Y"),
])
def test_genuinely_different_messages_never_merge(a, b):
    """Serving a stranger's answer for your message is the worst failure this
    cache can have — worse than missing."""
    assert _normalize_input(a) != _normalize_input(b)


# -- the key covers everything that decides the answer -------------------------

def test_the_key_covers_model_effort_and_the_whitelist(monkeypatch):
    text = "some claim"
    base = J.cache_key(text)

    monkeypatch.setattr(settings, "chat_model", "claude-opus-5")
    assert J.cache_key(text) != base
    monkeypatch.setattr(settings, "chat_model", "claude-sonnet-5")

    monkeypatch.setattr(settings, "chat_effort", "high")
    assert J.cache_key(text) != base
    monkeypatch.setattr(settings, "chat_effort", "medium")

    monkeypatch.setattr(settings, "web_tier_enabled", False)
    assert J.cache_key(text) != base
    monkeypatch.setattr(settings, "web_tier_enabled", True)

    import app.trusted_sources as TS
    monkeypatch.setattr(TS, "SEARCH_DOMAINS", TS.SEARCH_DOMAINS + ["new.example"])
    monkeypatch.setattr(J, "SEARCH_DOMAINS", TS.SEARCH_DOMAINS)
    assert J.cache_key(text) != base


def test_editing_the_prompt_invalidates_every_cached_answer(monkeypatch):
    """Otherwise a prompt fix does nothing for exactly the messages already
    seen — the ones that matter most."""
    base = J.cache_key("some claim")
    monkeypatch.setattr(J, "PROMPT_FINGERPRINT", "different")
    assert J.cache_key("some claim") != base


# -- TTL by tier ---------------------------------------------------------------

def _age_entry(key: str, hours: float) -> None:
    stamp = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with get_conn() as conn:
        conn.execute("UPDATE answer_cache SET created_at = ? WHERE key = ?",
                     (stamp, key))


def test_a_web_answer_expires_in_a_day_but_a_trusted_one_lasts_a_week(repo):
    repo.cache.put("web-key", "web", '{"x": 1}')
    repo.cache.put("trusted-key", "trusted", '{"x": 1}')
    _age_entry("web-key", 30)          # > 24h
    _age_entry("trusted-key", 30)      # < 168h

    assert repo.cache.get("web-key") is None
    assert repo.cache.get("trusted-key") is not None


def test_even_a_trusted_answer_expires_eventually(repo):
    repo.cache.put("k", "trusted", '{"x": 1}')
    _age_entry("k", 200)               # > 168h
    assert repo.cache.get("k") is None


def test_an_unparseable_timestamp_is_treated_as_stale(repo):
    repo.cache.put("k", "trusted", '{"x": 1}')
    with get_conn() as conn:
        conn.execute("UPDATE answer_cache SET created_at = 'garbage' WHERE key = 'k'")
    assert repo.cache.get("k") is None


def test_prune_drops_only_what_is_past_every_ttl(repo):
    repo.cache.put("old", "trusted", "{}")
    repo.cache.put("fresh", "trusted", "{}")
    _age_entry("old", 300)
    assert repo.cache.prune() == 1
    assert repo.cache.get("fresh") is not None


# -- the job runner ------------------------------------------------------------

def _run(repo, answer, chat_answer=None, boom=None, monkeypatch=None, **kw):
    async def fake_answer(text, *, heard=None, emit=None):
        if boom:
            raise boom
        if emit:
            await emit("text", {"text": "streamed", "tier": "trusted"})
        return chat_answer or _chat_answer()

    monkeypatch.setattr(J.chat, "answer", fake_answer)
    asyncio.run(J.run_check(answer.job_id, answer.input_text, repo, **kw))
    return repo.get(answer.job_id)


def test_a_completed_check_is_stored_and_cached(repo, monkeypatch):
    answer = _new(repo)
    stored = _run(repo, answer, monkeypatch=monkeypatch)

    assert stored.status is JobStatus.COMPLETE
    assert stored.markdown == "It is false."
    assert stored.tier == "trusted" and stored.confidence == 90
    assert stored.cached is False
    assert repo.cache.get(J.cache_key(answer.input_text)) is not None


def test_a_repeat_forward_is_served_free(repo, monkeypatch):
    first = _new(repo)
    _run(repo, first, monkeypatch=monkeypatch)

    calls = {"n": 0}

    async def must_not_run(text, *, heard=None, emit=None):
        calls["n"] += 1
        raise AssertionError("a cached answer must not reach the engine")

    second = _new(repo)
    monkeypatch.setattr(J.chat, "answer", must_not_run)
    asyncio.run(J.run_check(second.job_id, second.input_text, repo))

    stored = repo.get(second.job_id)
    assert stored.status is JobStatus.COMPLETE
    assert stored.cached is True
    assert stored.markdown == "It is false."
    assert calls["n"] == 0
    assert stored.usage.estimated_usd == 0.0      # honestly free


def test_a_failure_becomes_a_readable_failed_answer(repo, monkeypatch):
    answer = _new(repo)
    stored = _run(repo, answer, boom=RuntimeError("network died"),
                  monkeypatch=monkeypatch)

    assert stored.status is JobStatus.FAILED
    assert "Something went wrong" in stored.error
    assert "RuntimeError" not in stored.error      # no internals to the reader
    assert stored.usage is not None                # failures cost money too


def test_a_refusal_says_so_plainly(repo, monkeypatch):
    from app.engine.chat import AnswerRefused

    answer = _new(repo)
    stored = _run(repo, answer, boom=AnswerRefused("cyber"),
                  monkeypatch=monkeypatch)
    assert stored.status is JobStatus.FAILED
    assert "declined for safety" in stored.error


def test_a_broken_cache_still_produces_an_answer(repo, monkeypatch):
    """Invariant 6 survives the pivot: a cache fault costs time, not answers."""
    import sqlite3

    def boom(*a, **kw):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(repo.cache, "get", boom)
    monkeypatch.setattr(repo.cache, "put", boom)

    answer = _new(repo)
    stored = _run(repo, answer, monkeypatch=monkeypatch)
    assert stored.status is JobStatus.COMPLETE
    assert stored.markdown == "It is false."


def test_a_corrupt_cached_row_costs_one_recheck_not_the_answer(repo, monkeypatch):
    answer = _new(repo)
    repo.cache.put(J.cache_key(answer.input_text), "trusted", "{not json")

    stored = _run(repo, answer, monkeypatch=monkeypatch)
    assert stored.status is JobStatus.COMPLETE
    assert stored.cached is False


def test_an_empty_answer_is_not_cached(repo, monkeypatch):
    """Caching "the model said nothing" would serve silence for a week."""
    answer = _new(repo)
    _run(repo, answer, chat_answer=ChatAnswer(), monkeypatch=monkeypatch)
    assert repo.cache.get(J.cache_key(answer.input_text)) is None


def test_machine_read_text_is_stored_for_display(repo, monkeypatch):
    answer = _new(repo)
    stored = _run(repo, answer, monkeypatch=monkeypatch,
                  derived_text="what the ASR heard")
    assert stored.source_text == "what the ASR heard"


# -- restart recovery ----------------------------------------------------------

def test_orphaned_jobs_are_failed_at_startup(repo):
    """BackgroundTasks die with the process, so a PROCESSING row at startup is
    dead by definition — it would otherwise be polled forever."""
    stuck = _new(repo)
    stuck.status = JobStatus.PROCESSING
    repo.save(stuck)
    done = _new(repo)
    done.status = JobStatus.COMPLETE
    repo.save(done)

    assert repo.sweep_orphans() == 1
    assert repo.get(stuck.job_id).status is JobStatus.FAILED
    assert "restarted" in repo.get(stuck.job_id).error
    assert repo.get(done.job_id).status is JobStatus.COMPLETE
