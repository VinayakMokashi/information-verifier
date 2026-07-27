"""A broken cache must cost time, never verdicts.

The failure this pins: a SQLite error inside a cache call used to escape
_process_claim, get swallowed by gather(return_exceptions=True), and drop the
claim — so a fully-paid verdict vanished and the report said "no claims
found" while reporting COMPLETE.
"""
import asyncio
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

import scripts.fake_stages as F
from app.config import settings
from app.engine import pipeline as P
from app.models.claim import Claim
from app.models.report import JobStatus, TruthReport
from app.models.verdict import Rating, Verdict
from app.store.db import init_db
from app.store.repository import CacheCandidate, ReportRepository

CLAIM = Claim(text="5G spreads coronavirus.", subject="5G",
              claim_type="causal", checkworthy=True)


class BrokenCache:
    """Every operation fails the way a locked database does."""

    def __init__(self, fail_on=("get", "nearest", "put")):
        self.fail_on = fail_on
        self.calls = []

    def _maybe(self, name):
        self.calls.append(name)
        if name in self.fail_on:
            raise sqlite3.OperationalError("database is locked")

    def get(self, text):
        self._maybe("get")
        return None

    def nearest(self, text):
        self._maybe("nearest")
        return None

    def put(self, text, verdict, index=True):
        self._maybe("put")


class BrokenRepo:
    def __init__(self, **kw):
        self.cache = BrokenCache(**kw)


@pytest.fixture(autouse=True)
def _fake_paid_stages(monkeypatch):
    monkeypatch.setattr(P, "gather_evidence", F.fake_gather)
    monkeypatch.setattr(P, "adjudicate", F.fake_adjudicate)
    # run_pipeline reaches the translation stage, and FakeNorm says Hindi.
    monkeypatch.setattr(P, "localize", F.fake_localize)
    F.CALLS["adjudicate"] = 0


def test_every_cache_failure_still_yields_a_verdict():
    repo = BrokenRepo()
    result = asyncio.run(P._process_claim(CLAIM, repo))
    assert result.verdict.rating == Rating.FALSE   # the paid work survived
    assert result.cache_hit is False
    assert repo.cache.calls == ["get", "nearest", "put"]  # all three attempted


def test_put_failure_does_not_discard_the_paid_verdict():
    repo = BrokenRepo(fail_on=("put",))
    result = asyncio.run(P._process_claim(CLAIM, repo))
    assert result.verdict.rating == Rating.FALSE
    assert F.CALLS["adjudicate"] == 1


def test_report_completes_with_verdicts_when_the_cache_is_down(tmp_path, monkeypatch):
    """End-to-end: the whole report must not collapse to 'no claims found'."""
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "report.db"))
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    monkeypatch.setattr(P, "normalize", F.fake_normalize)
    monkeypatch.setattr(P, "extract_claims", F.fake_extract)
    init_db()

    repo = ReportRepository()
    monkeypatch.setattr(repo, "cache", BrokenCache())
    report = TruthReport(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                         created_at=datetime.now(timezone.utc))
    repo.save(report)

    asyncio.run(P.run_pipeline(report.job_id, "kuch bhi", repo))

    saved = repo.get(report.job_id)
    assert saved.status == JobStatus.COMPLETE
    assert len(saved.claim_verdicts) == 2       # NOT silently dropped
    assert saved.overall_rating == Rating.FALSE
    assert "No checkworthy" not in (saved.summary or "")


def test_confirmed_alias_is_stored_unindexed_to_stop_chaining(monkeypatch):
    """An alias must never become a nomination anchor for the next hop."""
    puts = []

    class Cache:
        def get(self, text):
            return None

        def nearest(self, text):
            return CacheCandidate("cached claim", Verdict(
                rating=Rating.TRUE, confidence=90, reasoning="r",
                correction="", citations=[]), 0.05)

        def put(self, text, verdict, index=True):
            puts.append(index)

    async def yes(a, b):
        return True

    monkeypatch.setattr(P, "claims_equivalent", yes)

    class Repo:
        cache = Cache()

    result = asyncio.run(P._process_claim(CLAIM, Repo()))
    assert result.cache_hit is True
    assert puts == [False]  # learned as an alias, NOT indexed
