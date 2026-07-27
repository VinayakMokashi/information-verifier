"""The translation cache keeps cost per-RUMOUR, not per-reader.

Without it the claim cache's economics invert: one viral Hindi forward is a
single $0.05 check and then a fresh ~$0.01 translation for every reader,
which is per-user pricing wearing a cache's clothes. Free — the Haiku calls
are stubbed and counted.
"""
import asyncio
import sqlite3
import uuid
from datetime import datetime, timezone

import pytest

from app.config import settings
from app.engine import translate as T
from app.models.claim import Claim
from app.models.report import ClaimVerdict, JobStatus, LocalizedClaim, TruthReport
from app.models.verdict import Rating, Verdict
from app.store.db import init_db
from app.store.repository import TranslationCache, _content_key

# The `stub` fixture lives in conftest.py; this mirrors what it answers with.
HINDI_CLAIM = "5जी से कोरोना वायरस फैलता है।"


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "tr.db"))
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    init_db()
    return TranslationCache()


def _report(language="hi", claim="5G spreads coronavirus.",
            reasoning="Trusted sources say this is false.",
            correction="Corona spreads by droplets.") -> TruthReport:
    return TruthReport(
        job_id=uuid.uuid4().hex, status=JobStatus.PROCESSING,
        created_at=datetime.now(timezone.utc), input_language=language,
        overall_rating=Rating.FALSE, summary="1 claim(s) checked.",
        claim_verdicts=[ClaimVerdict(
            claim=Claim(text=claim, subject="5G", claim_type="causal", checkworthy=True),
            verdict=Verdict(rating=Rating.FALSE, confidence=97, reasoning=reasoning,
                            correction=correction, citations=[]),
        )],
    )


# -- the store ---------------------------------------------------------------

def test_round_trips_indic_text(cache):
    cache.put("hi", ("a", "b"), HINDI_CLAIM)
    assert cache.get("hi", ("a", "b")) == HINDI_CLAIM


def test_a_different_language_is_a_different_entry(cache):
    cache.put("hi", ("a",), "हिंदी")
    cache.put("ta", ("a",), "தமிழ்")
    assert cache.get("hi", ("a",)) == "हिंदी"
    assert cache.get("ta", ("a",)) == "தமிழ்"
    assert cache.get("bn", ("a",)) is None


def test_field_boundaries_cannot_be_smudged(cache):
    """('ab','c') and ('a','bc') must not collide — a cache that can serve
    another claim's answer is the worst failure this system has."""
    assert _content_key(("ab", "c")) != _content_key(("a", "bc"))
    cache.put("hi", ("ab", "c"), "first")
    assert cache.get("hi", ("a", "bc")) is None


def test_changed_source_text_misses_instead_of_going_stale(cache):
    """Content-addressed, so a re-adjudicated verdict needs no invalidation."""
    cache.put("hi", ("claim", "old reasoning", ""), "पुराना")
    assert cache.get("hi", ("claim", "new reasoning", "")) is None
    assert cache.get("hi", ("claim", "old reasoning", "")) == "पुराना"


def test_put_overwrites_rather_than_erroring(cache):
    cache.put("hi", ("a",), "one")
    cache.put("hi", ("a",), "two")
    assert cache.get("hi", ("a",)) == "two"


# -- the stage uses it -------------------------------------------------------

def test_a_repeat_forward_costs_nothing(cache, stub):
    """The point of the whole exercise."""
    first = asyncio.run(T.localize(_report(), cache))
    calls_after_first = len(stub.messages.calls)
    assert calls_after_first == 2                 # one summary + one claim

    second = asyncio.run(T.localize(_report(), cache))

    assert len(stub.messages.calls) == calls_after_first   # no new spend
    assert second.summary == first.summary
    assert second.claims[0] == first.claims[0]


def test_the_same_rumour_in_another_language_still_pays(cache, stub):
    asyncio.run(T.localize(_report(language="hi"), cache))
    calls = len(stub.messages.calls)
    asyncio.run(T.localize(_report(language="ta"), cache))
    assert len(stub.messages.calls) > calls


def test_a_changed_verdict_is_retranslated(cache, stub):
    asyncio.run(T.localize(_report(reasoning="Old reasoning."), cache))
    calls = len(stub.messages.calls)
    asyncio.run(T.localize(_report(reasoning="Revised reasoning."), cache))
    assert len(stub.messages.calls) > calls


def test_a_broken_cache_still_produces_a_translation(stub):
    """A cache failure degrades to doing the real work (invariant 6)."""
    class Broken:
        def get(self, *a):
            raise sqlite3.OperationalError("database is locked")

        def put(self, *a):
            raise sqlite3.OperationalError("database is locked")

    localized = asyncio.run(T.localize(_report(), Broken()))
    assert localized.claims[0].claim == HINDI_CLAIM


def test_a_corrupt_cached_row_costs_one_retranslation_not_the_report(cache, stub):
    cache.put("hi", ("5G spreads coronavirus.", "Trusted sources say this is false.",
                     "Corona spreads by droplets."), "{not json at all")

    localized = asyncio.run(T.localize(_report(), cache))
    assert localized.claims[0].claim == HINDI_CLAIM


def test_a_cached_invented_correction_is_still_discarded(cache, stub):
    """The never-become-an-author rules apply to cached rows too, so a row
    written by an older ruleset cannot smuggle one past."""
    source = ("5G spreads coronavirus.", "Trusted sources say this is false.", "")
    cache.put("hi", source, LocalizedClaim(
        claim=HINDI_CLAIM, reasoning="कारण", correction="मनगढ़ंत सुधार",
    ).model_dump_json())

    localized = asyncio.run(T.localize(_report(correction=""), cache))
    assert localized.claims[0].correction == ""


def test_a_rejected_cached_row_is_replaced_not_obeyed_forever(cache, stub):
    """A row today's rules reject must cost one re-translation, not permanent
    English for that claim — otherwise one bad row is a silent, sticky
    downgrade nobody would ever notice."""
    source = ("5G spreads coronavirus.", "Trusted sources say this is false.",
              "Corona spreads by droplets.")
    cache.put("hi", source, LocalizedClaim(
        claim=HINDI_CLAIM, reasoning="कारण", correction="   ",   # dropped field
    ).model_dump_json())

    first = asyncio.run(T.localize(_report(), cache))
    assert first.claims[0] is not None            # re-translated on the spot

    stub.messages.calls.clear()
    second = asyncio.run(T.localize(_report(), cache))
    assert second.claims[0] == first.claims[0]
    assert stub.messages.calls == []              # and the bad row was overwritten


def test_no_cache_still_works(stub):
    """`cache=None` just means paying for every translation."""
    localized = asyncio.run(T.localize(_report(), None))
    assert localized.claims[0].claim == HINDI_CLAIM


def test_a_cache_hit_never_reaches_the_model(cache, stub):
    asyncio.run(T.localize(_report(), cache))
    stub.messages.calls.clear()

    def explode(kw):
        raise AssertionError("a cached translation must not call the model")

    stub.messages.handler = explode
    localized = asyncio.run(T.localize(_report(), cache))
    assert localized.claims[0].claim == HINDI_CLAIM
    assert stub.messages.calls == []
