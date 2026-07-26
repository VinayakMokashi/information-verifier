"""The nominate->confirm cache flow inside the pipeline. Free (all fakes).

The candidate verdict may only be served when claims_equivalent says yes;
a no or a failure must fall through to the full check.
"""
import asyncio

import pytest

import scripts.fake_stages as F
from app.engine import pipeline as P
from app.models.claim import Claim
from app.models.verdict import Rating, Verdict
from app.store.repository import CacheCandidate

CLAIM = Claim(text="WHO declared COVID-19 a pandemic in 2020.",
              subject="WHO", claim_type="event", checkworthy=True)
CACHED = Verdict(rating=Rating.TRUE, confidence=99, reasoning="cached",
                 correction="", citations=[])


class StubCache:
    def __init__(self, candidate):
        self.candidate = candidate
        self.puts = []

    def get(self, text):
        return None

    def nearest(self, text):
        return self.candidate

    def put(self, text, verdict, index=True):
        self.puts.append((text, verdict, index))


class StubRepo:
    def __init__(self, candidate):
        self.cache = StubCache(candidate)


@pytest.fixture()
def full_check_stages(monkeypatch):
    monkeypatch.setattr(P, "gather_evidence", F.fake_gather)
    monkeypatch.setattr(P, "adjudicate", F.fake_adjudicate)
    F.CALLS["adjudicate"] = 0


def _run(repo):
    return asyncio.run(P._process_claim(CLAIM, repo))


def test_confirmed_candidate_is_served_and_learned(full_check_stages, monkeypatch):
    async def yes(a, b):
        return True

    monkeypatch.setattr(P, "claims_equivalent", yes)
    repo = StubRepo(CacheCandidate("who declared covid-19 a pandemic in 2020", CACHED, 0.03))

    result = _run(repo)
    assert result.cache_hit is True
    assert result.verdict == CACHED
    # Phrasing learned as an alias — and NOT indexed, so it can never become
    # the anchor for a further hop away from the adjudicated claim.
    assert repo.cache.puts == [(CLAIM.text, CACHED, False)]
    assert F.CALLS["adjudicate"] == 0                 # full check never ran


def test_rejected_candidate_falls_through_to_full_check(full_check_stages, monkeypatch):
    async def no(a, b):
        return False

    monkeypatch.setattr(P, "claims_equivalent", no)
    repo = StubRepo(CacheCandidate("who declared covid-19 a pandemic in 2019", CACHED, 0.03))

    result = _run(repo)
    assert result.cache_hit is False
    assert result.verdict.rating == Rating.FALSE      # from the fake full check
    assert F.CALLS["adjudicate"] == 1


def test_equivalence_failure_falls_through_to_full_check(full_check_stages, monkeypatch):
    async def boom(a, b):
        raise RuntimeError("api down")

    monkeypatch.setattr(P, "claims_equivalent", boom)
    repo = StubRepo(CacheCandidate("anything", CACHED, 0.03))

    result = _run(repo)
    assert result.cache_hit is False
    assert F.CALLS["adjudicate"] == 1


def test_no_candidate_goes_straight_to_full_check(full_check_stages, monkeypatch):
    called = {"n": 0}

    async def counter(a, b):
        called["n"] += 1
        return True

    monkeypatch.setattr(P, "claims_equivalent", counter)
    repo = StubRepo(candidate=None)

    result = _run(repo)
    assert result.cache_hit is False
    assert called["n"] == 0
    assert F.CALLS["adjudicate"] == 1
