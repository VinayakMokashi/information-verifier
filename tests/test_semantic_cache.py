"""Semantic claim cache — real sqlite-vec, fake embedder, zero cost.

Design under test: the vector index only NOMINATES (`nearest()` returns a
CacheCandidate); it never serves a verdict directly. Calibration on the real
model showed one-token-different claims (2020 vs 2019) embed CLOSER than
genuine paraphrases, so any serve-from-distance design is unsafe.
"""
import math

import pytest

from app.config import settings
from app.models.verdict import Rating, Verdict
from app.store.db import VEC_AVAILABLE, get_conn, init_db
from app.store.repository import ClaimCache

pytestmark = pytest.mark.skipif(not VEC_AVAILABLE, reason="sqlite-vec not installed")


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v]


# cosine distances from the first vector: ~0.005, ~0.15, ~1.0
VECS = {
    "5g spreads coronavirus.": _unit([1.0, 0.0, 0.0, 0.0]),
    "coronavirus is spread by 5g networks.": _unit([0.995, 0.0999, 0.0, 0.0]),
    "5g towers are somewhat related to illness.": _unit([0.85, 0.5268, 0.0, 0.0]),
    "the unesco anthem claim is false.": _unit([0.0, 0.0, 1.0, 0.0]),
}


class FakeEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        return VECS[" ".join(text.lower().split())]


class ExplodingEmbedder:
    def __init__(self) -> None:
        self.calls = 0

    def embed(self, text: str) -> list[float]:
        self.calls += 1
        raise RuntimeError("model not available")


VERDICT = Verdict(rating=Rating.FALSE, confidence=95, reasoning="r",
                  correction="c", citations=[])


@pytest.fixture()
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "cache.db"))
    monkeypatch.setattr(settings, "embedding_dim", 4)
    monkeypatch.setattr(settings, "semantic_cache_enabled", True)
    init_db()
    return ClaimCache(embedder=FakeEmbedder())


def test_exact_get_never_touches_the_embedder(cache):
    cache.put("5G spreads coronavirus.", VERDICT)
    calls_after_put = cache._embedder.calls
    assert cache.get("5G spreads coronavirus.") == VERDICT
    assert cache.get("  5G   SPREADS coronavirus. ") == VERDICT  # normalization
    assert cache._embedder.calls == calls_after_put


def test_nearest_nominates_a_candidate_not_a_verdict(cache):
    cache.put("5G spreads coronavirus.", VERDICT)
    candidate = cache.nearest("Coronavirus is spread by 5G networks.")
    assert candidate is not None
    assert candidate.verdict == VERDICT
    assert candidate.text == "5g spreads coronavirus."  # normalized cached text
    assert candidate.distance < 0.01


def test_nearest_within_candidate_window_includes_lookalikes(cache):
    # ~0.15 distance: nominated (the Haiku confirm step is what rejects it).
    cache.put("5G spreads coronavirus.", VERDICT)
    candidate = cache.nearest("5G towers are somewhat related to illness.")
    assert candidate is not None
    assert 0.10 < candidate.distance <= settings.semantic_candidate_distance


def test_nearest_respects_the_candidate_distance_setting(cache, monkeypatch):
    cache.put("5G spreads coronavirus.", VERDICT)
    monkeypatch.setattr(settings, "semantic_candidate_distance", 0.10)
    assert cache.nearest("5G towers are somewhat related to illness.") is None


def test_unrelated_claim_is_not_nominated(cache):
    cache.put("5G spreads coronavirus.", VERDICT)
    assert cache.nearest("The UNESCO anthem claim is false.") is None


def test_disabled_flag_skips_embedding_entirely(cache, monkeypatch):
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    cache.put("5G spreads coronavirus.", VERDICT)
    assert cache.nearest("Coronavirus is spread by 5G networks.") is None
    assert cache._embedder.calls == 0


def test_broken_embedder_degrades_to_exact_only(tmp_path, monkeypatch):
    """A hard-down model latches off after a few tries, never sinking a claim."""
    from app.store.repository import _MAX_EMBED_FAILURES

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "broken.db"))
    monkeypatch.setattr(settings, "embedding_dim", 4)
    monkeypatch.setattr(settings, "semantic_cache_enabled", True)
    init_db()
    cache = ClaimCache(embedder=ExplodingEmbedder())

    cache.put("5G spreads coronavirus.", VERDICT)      # failure 1
    assert cache.get("5G spreads coronavirus.") == VERDICT  # exact tier still fine
    for _ in range(_MAX_EMBED_FAILURES + 2):
        assert cache.nearest("Coronavirus is spread by 5G networks.") is None
    # Tried up to the budget, then stopped calling the broken model entirely.
    assert cache._embedder.calls == _MAX_EMBED_FAILURES


def test_transient_embedding_failure_does_not_disable_the_tier(cache):
    """One network blip on the lazy model load must not cost the whole run."""
    real = cache._embedder

    class FlakyOnce:
        def __init__(self):
            self.calls = 0

        def embed(self, text):
            self.calls += 1
            if self.calls == 1:
                raise ConnectionError("hub unreachable")
            return real.embed(text)

    cache._embedder = FlakyOnce()
    cache.put("5G spreads coronavirus.", VERDICT)  # embed fails -> no vector
    assert cache.nearest("Coronavirus is spread by 5G networks.") is None

    cache.put("5G spreads coronavirus.", VERDICT)  # recovered -> indexed now
    assert cache.nearest("Coronavirus is spread by 5G networks.") is not None


def test_changing_embedding_model_wipes_vectors_not_verdicts(cache, monkeypatch):
    cache.put("5G spreads coronavirus.", VERDICT)
    assert cache.nearest("Coronavirus is spread by 5G networks.") is not None

    monkeypatch.setattr(settings, "embedding_model", "some/other-model")
    init_db()  # signature mismatch -> vectors dropped

    assert cache.get("5G spreads coronavirus.") == VERDICT      # exact survives
    assert cache.nearest("Coronavirus is spread by 5G networks.") is None
    with get_conn() as conn:
        assert conn.execute("SELECT count(*) c FROM claim_vecs").fetchone()["c"] == 0


def test_reput_after_wipe_relearns_the_vector(cache, monkeypatch):
    cache.put("5G spreads coronavirus.", VERDICT)
    monkeypatch.setattr(settings, "embedding_model", "some/other-model")
    init_db()
    cache.put("5G spreads coronavirus.", VERDICT)  # upsert re-embeds
    assert cache.nearest("Coronavirus is spread by 5G networks.") is not None
