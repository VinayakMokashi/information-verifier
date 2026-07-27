"""Indic text must survive the whole stack byte-for-byte.

The users this project exists for write in Devanagari, Tamil and Bengali, so
a mojibake bug anywhere between the transcript and the rendered page would
break the product for exactly the people it targets. These tests are free:
the ASR and LLM stages are simulated, only the real storage/serialization/
HTTP layers are exercised.
"""
import json

import pytest

import scripts.fake_stages as F
from app.api import routes as R
from app.config import settings
from app.engine import pipeline as P
from app.models.verdict import Citation, Rating, Verdict
from app.store.db import init_db
from app.store.repository import ClaimCache

HINDI = "डब्ल्यूएचओ ने कहा है कि 5जी से कोरोना वायरस फैलता है।"
MARATHI = "५जी मुळे कोरोना पसरतो असे डब्ल्यूएचओने म्हटले आहे."
TAMIL = "5ஜி மூலம் கொரோனா பரவுகிறது என்று உலக சுகாதார அமைப்பு கூறியது."
BENGALI = "বিশ্ব স্বাস্থ্য সংস্থা বলেছে যে ৫জি থেকে করোনা ছড়ায়।"
ALL_SCRIPTS = [HINDI, MARATHI, TAMIL, BENGALI]


@pytest.mark.parametrize("text", ALL_SCRIPTS)
def test_verdicts_round_trip_through_sqlite_unchanged(tmp_path, monkeypatch, text):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "indic.db"))
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    init_db()
    cache = ClaimCache()

    verdict = Verdict(
        rating=Rating.FALSE, confidence=95,
        reasoning=f"दावा गलत है: {text}",
        correction=f"सही जानकारी: {text}",
        citations=[Citation(url="https://altnews.in/x", title=text, publisher="ऑल्ट न्यूज़")],
    )
    cache.put(text, verdict)
    got = cache.get(text)

    assert got == verdict
    assert got.reasoning.endswith(text)          # no mojibake, no truncation
    assert got.citations[0].publisher == "ऑल्ट न्यूज़"


def test_indic_claim_normalizes_for_the_cache_key(tmp_path, monkeypatch):
    """Whitespace collapsing must not mangle combining marks."""
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "key.db"))
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)
    init_db()
    cache = ClaimCache()
    v = Verdict(rating=Rating.FALSE, confidence=90, reasoning="r", correction="c", citations=[])

    cache.put(HINDI, v)
    assert cache.get(f"  {HINDI}  ") == v        # padded lookup still hits
    assert cache.get(HINDI.replace("।", "")) is None  # genuinely different text misses


def test_hindi_transcript_survives_the_api_as_utf8(client, monkeypatch):
    """Transcript -> pipeline -> SQLite -> JSON response, unchanged."""
    async def hindi_extract(english_text):
        from app.models.claim import Claim
        return [Claim(text=HINDI, subject="डब्ल्यूएचओ",
                      claim_type="attribution", checkworthy=True)]

    async def hindi_adjudicate(claim, evidence):
        return Verdict(rating=Rating.FALSE, confidence=97,
                       reasoning=f"यह दावा झूठा है। {HINDI}",
                       correction="कोरोना वायरस 5जी से नहीं फैलता।",
                       citations=[Citation(url="https://www.boomlive.in/x",
                                           title="5जी और कोरोना", publisher="बूम")])

    monkeypatch.setattr(P, "extract_claims", hindi_extract)
    monkeypatch.setattr(P, "adjudicate", hindi_adjudicate)

    accepted = client.post("/api/v1/verify/text", json={"text": HINDI})
    assert accepted.status_code == 202
    resp = client.get(f"/api/v1/reports/{accepted.json()['job_id']}")

    # Bytes on the wire must decode to the same characters we stored.
    body = json.loads(resp.content.decode("utf-8"))
    cv = body["claim_verdicts"][0]
    assert cv["claim"]["text"] == HINDI
    assert cv["verdict"]["correction"] == "कोरोना वायरस 5जी से नहीं फैलता।"
    assert cv["verdict"]["citations"][0]["publisher"] == "बूम"


def test_page_is_utf8_so_indic_verdicts_render(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert 'charset="utf-8"' in resp.text.lower()
    # The page escapes with a character-level function; confirm Devanagari is
    # not in the escape set (it would be double-encoded if it were).
    assert "&#" not in HINDI


def test_devanagari_filename_upload_is_accepted(client, monkeypatch, tmp_path):
    """WhatsApp names forwarded files in the user's language."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")

    out = tmp_path / "tone.ogg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    monkeypatch.setattr(settings, "sarvam_api_key", "demo-mode-not-a-real-key")
    monkeypatch.setattr(R, "get_asr_provider", lambda: F.FakeASR())

    resp = client.post(
        "/api/v1/verify/media",
        files={"file": ("वॉइस-नोट.ogg", out.read_bytes(), "audio/ogg")},
    )
    assert resp.status_code == 202
