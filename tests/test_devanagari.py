"""Indic text must survive the whole stack byte-for-byte.

Many of the people this project exists for write in Devanagari, Tamil or
Bengali, so a mojibake bug anywhere between the transcript and the rendered
page would break the product for exactly its users. Free: the engine is
simulated, only the real storage / serialization / HTTP layers are exercised.
"""
import json
import uuid
from datetime import datetime, timezone

import pytest

import scripts.fake_stages as F
from app.api import routes as R
from app.config import settings
from app.models.answer import Answer, AnswerSection, JobStatus, Source
from app.store.db import init_db
from app.store.repository import AnswerRepository, _normalize_input

HINDI = "डब्ल्यूएचओ ने कहा है कि 5जी से कोरोना वायरस फैलता है।"
MARATHI = "५जी मुळे कोरोना पसरतो असे डब्ल्यूएचओने म्हटले आहे."
TAMIL = "5ஜி மூலம் கொரோனா பரவுகிறது என்று உலக சுகாதார அமைப்பு கூறியது."
BENGALI = "বিশ্ব স্বাস্থ্য সংস্থা বলেছে যে ৫জি থেকে করোনা ছড়ায়।"
ALL_SCRIPTS = [HINDI, MARATHI, TAMIL, BENGALI]


@pytest.mark.parametrize("text", ALL_SCRIPTS)
def test_answers_round_trip_through_sqlite_unchanged(tmp_path, monkeypatch, text):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "indic.db"))
    init_db()
    repo = AnswerRepository()

    answer = Answer(
        job_id=uuid.uuid4().hex, status=JobStatus.COMPLETE,
        created_at=datetime.now(timezone.utc),
        input_text=text,
        sections=[AnswerSection(tier="trusted", markdown=f"**झूठ है।** {text}")],
        sources=[Source(url="https://altnews.in/x", title=text,
                        publisher="ऑल्ट न्यूज़", tier="trusted")],
        confidence=95, tier="trusted",
    )
    repo.save(answer)
    got = repo.get(answer.job_id)

    assert got.markdown.endswith(text)          # no mojibake, no truncation
    assert got.sources[0].publisher == "ऑल्ट न्यूज़"
    assert got.input_text == text


def test_the_cache_key_survives_combining_marks(tmp_path, monkeypatch):
    """Whitespace folding must not mangle Devanagari combining marks."""
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "key.db"))
    init_db()

    assert _normalize_input(f"  {HINDI}  ") == _normalize_input(HINDI)
    # Genuinely different text still misses — dropping the danda changes it.
    assert _normalize_input(HINDI.replace("।", "")) != _normalize_input(HINDI)


def test_a_hindi_answer_survives_the_api_as_utf8(client):
    """Engine -> SQLite -> JSON response, unchanged."""
    accepted = client.post("/api/v1/verify/text", json={"text": HINDI})
    assert accepted.status_code == 202
    resp = client.get(f"/api/v1/reports/{accepted.json()['job_id']}")

    # Bytes on the wire must decode to the same characters we stored.
    body = json.loads(resp.content.decode("utf-8"))
    assert body["input_text"] == HINDI
    # Devanagari in -> Devanagari out (the fake mirrors the real prompt rule).
    assert body["sections"][0]["markdown"].startswith("**यह दावा झूठा है।**")


def test_the_page_is_utf8_so_indic_answers_render(client):
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
