"""Per-request spend must be bounded, not just per-request-count.

The rate limiter caps how many submissions a visitor makes; these cap what
a single submission can cost. Without them one paste could fan out to
arbitrarily many paid claim checks, and one small upload could pin the box.
"""
import shutil
import subprocess

import pytest

import scripts.fake_stages as F
from app.config import settings
from app.engine import pipeline as P
from app.models.claim import Claim
from app.providers.media import MediaTooLong, normalize_to_wav


def test_overlong_text_is_refused_before_any_paid_work(client, monkeypatch):
    monkeypatch.setattr(settings, "max_input_chars", 100)
    resp = client.post("/api/v1/verify/text", json={"text": "x" * 500})
    assert resp.status_code == 413
    assert F.CALLS["adjudicate"] == 0


def test_claim_fanout_is_capped_and_disclosed(client, monkeypatch):
    """20 checkworthy claims must not become 20 paid adjudications."""
    async def many_claims(english_text):
        return [
            Claim(text=f"Claim number {i} about India.", subject="India",
                  claim_type="other", checkworthy=True)
            for i in range(20)
        ]

    monkeypatch.setattr(P, "extract_claims", many_claims)
    monkeypatch.setattr(settings, "max_claims_per_report", 3)

    accepted = client.post("/api/v1/verify/text", json={"text": "many claims"})
    report = client.get(f"/api/v1/reports/{accepted.json()['job_id']}").json()

    assert len(report["claim_verdicts"]) == 3
    assert F.CALLS["adjudicate"] == 3            # spend bounded
    assert "17 were not verified" in report["summary"]   # and disclosed


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_long_audio_is_rejected_without_decoding_it_all(tmp_path):
    """A tiny low-bitrate file decoding to an hour must not reach RAM."""
    src = tmp_path / "hour.opus"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=200:duration=3600",
         "-c:a", "libopus", "-b:a", "6k", "-ar", "16000", "-ac", "1", str(src)],
        check=True, capture_output=True,
    )
    data = src.read_bytes()
    assert len(data) < settings.max_media_bytes   # passes the byte cap

    with pytest.raises(MediaTooLong) as exc:
        normalize_to_wav(data, "hour.opus", max_seconds=300)
    assert exc.value.seconds > 3000               # detected from the header


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_within_limit_audio_still_normalizes(tmp_path):
    src = tmp_path / "ok.opus"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=300:duration=5", "-c:a", "libopus", str(src)],
        check=True, capture_output=True,
    )
    wav, duration = normalize_to_wav(src.read_bytes(), "ok.opus", max_seconds=300)
    assert wav[:4] == b"RIFF"
    assert 4.5 < duration < 5.5


def test_semantic_tier_off_does_not_break_the_database(tmp_path, monkeypatch):
    """A missing/broken sqlite-vec must cost the cache, never the whole API."""
    from app.store import db as D

    monkeypatch.setattr(settings, "db_path", str(tmp_path / "novec.db"))
    monkeypatch.setattr(D, "_vec_broken", True)   # simulate a failed load
    D.init_db()

    from app.store.repository import ClaimCache, ReportRepository
    from app.models.verdict import Rating, Verdict

    repo = ReportRepository()
    cache = ClaimCache()
    v = Verdict(rating=Rating.FALSE, confidence=90, reasoning="r",
                correction="c", citations=[])

    cache.put("a claim", v)                       # writes, just without a vector
    assert cache.get("a claim") == v
    assert cache.nearest("a claim") is None       # semantic tier simply off
    assert repo.get("nope") is None               # reports still readable
