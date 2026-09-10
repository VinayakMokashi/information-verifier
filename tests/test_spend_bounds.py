"""Per-request spend must be bounded, not just per-request-count.

The rate limiter caps how many submissions a visitor makes; these cap what
a single submission can cost. Without them one paste could fan out to
arbitrarily many paid claim checks, and one small upload could pin the box.
"""
import shutil
import subprocess

import scripts.fake_stages as F

import pytest

from app.config import settings
from app.providers.media import MediaTooLong, normalize_to_wav


def test_a_single_check_cannot_exceed_its_search_budget():
    """The per-check ceiling is now arithmetic, not a claim-count cap: one
    trusted pass plus one web pass, each bounded by its own max_uses."""
    from app.config import settings

    worst_case_searches = (settings.chat_max_searches_trusted
                           + settings.chat_max_searches_web)
    assert worst_case_searches <= 8, "a single check could get expensive"
    assert settings.chat_max_tokens <= 20000


def test_overlong_text_is_refused_before_any_paid_work(client, monkeypatch):
    monkeypatch.setattr(settings, "max_input_chars", 100)
    resp = client.post("/api/v1/verify/text", json={"text": "x" * 500})
    assert resp.status_code == 413
    assert F.CALLS["answer"] == 0        # refused before the engine ran



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


def test_chunked_upload_cannot_skip_the_size_cap(client, monkeypatch):
    """Content-Length is advisory and absent on chunked uploads; the body
    must be counted as it streams or a 50 MB POST sails past a 1 MB cap."""
    monkeypatch.setattr(settings, "max_media_bytes", 1_000_000)
    boundary = "----t"
    prefix = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="big.ogg"\r\n'
        "Content-Type: audio/ogg\r\n\r\n"
    ).encode()

    def body():                       # a generator makes httpx send it chunked
        yield prefix
        for _ in range(20):
            yield b"x" * (256 * 1024)
        yield f"\r\n--{boundary}--\r\n".encode()

    resp = client.post(
        "/api/v1/verify/media",
        content=body(),
        headers={"content-type": f"multipart/form-data; boundary={boundary}"},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]


