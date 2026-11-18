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




# -- a stranger's oversized text post (reproduced 2026-10-15) -------------------

def _spy_triage(monkeypatch):
    import app.api.routes as R

    seen = []
    monkeypatch.setattr(R, "nothing_to_check", lambda text: seen.append(len(text)) or False)
    return seen


def test_a_huge_text_post_is_refused_before_anything_reads_it(client, monkeypatch):
    """REPRODUCED 2026-10-15 (docs/research/2026-10-15/audit-security.md, F5):
    a 25 MB JSON body passed the upload cap — 25 MB, meant for media — was
    parsed whole, and the small-talk triage ran over it ON the event loop
    before any limit: 10-19 s with the whole server frozen, then refunded,
    so free to repeat. Non-upload routes now have a small cap of their own."""
    seen = _spy_triage(monkeypatch)
    resp = client.post("/api/v1/verify/text", json={"text": "a" * 2_000_000})
    assert resp.status_code == 413
    assert seen == []                       # triage never saw it
    assert F.CALLS["answer"] == 0


def test_the_small_cap_goes_by_path_not_by_what_the_client_claims(client):
    """Content-Type is the client's word: a huge body labelled multipart must
    not get the upload allowance on a JSON route."""
    resp = client.post("/api/v1/verify/text", content=b"x" * 2_000_000,
                       headers={"content-type": "multipart/form-data; boundary=x"})
    assert resp.status_code == 413


def test_a_long_message_is_refused_before_triage_and_without_a_slot(client, monkeypatch):
    import app.api.routes as R

    monkeypatch.setattr(settings, "max_input_chars", 100)
    seen = _spy_triage(monkeypatch)
    claimed = []

    async def no_claim(request):
        claimed.append(1)
        return None

    monkeypatch.setattr(R, "claim", no_claim)
    resp = client.post("/api/v1/verify/text", json={"text": "x" * 500})
    assert resp.status_code == 413
    assert "500 characters" in resp.json()["detail"]
    assert seen == [] and claimed == []


def test_pictures_too_large_together_are_not_told_to_send_a_shorter_clip(client, monkeypatch):
    """Several images in one check (2026-11-18) can cross the upload cap
    together; "send a shorter clip" is the voice-note wording."""
    monkeypatch.setattr(settings, "max_media_bytes", 1000)
    resp = client.post("/api/v1/verify/image",
                       files=[("file", ("a.png", b"\x89PNG" + b"0" * 800, "image/png")),
                              ("file", ("b.png", b"\x89PNG" + b"0" * 800, "image/png"))])
    assert resp.status_code == 413
    detail = resp.json()["detail"]
    assert "clip" not in detail and "pictures" in detail
    media = client.post("/api/v1/verify/media",
                        files={"file": ("a.ogg", b"0" * 2000, "audio/ogg")})
    assert media.status_code == 413 and "clip" in media.json()["detail"]


def test_an_image_upload_still_gets_the_upload_allowance(client):
    """The guard on the other side: the small cap must not reach uploads."""
    resp = client.post("/api/v1/verify/image",
                       files={"file": ("shot.png", b"\x89PNG" + b"0" * 300_000, "image/png")})
    assert resp.status_code == 202


def test_the_small_cap_always_fits_a_maximum_length_message(client):
    """A message at max_input_chars and a language at its limit, in the
    COSTLIEST JSON a client can send, must reach the route, never the body
    cap. Both limits count code POINTS, and a \\u-escaping client (Python's
    json.dumps by default) writes one outside the BMP — an emoji — as a
    surrogate PAIR, "\\ud83d\\ude00": 12 bytes. Review R7: this test used to
    assume 6 a character, so it allowed max_input_chars up to ~10,700 while
    past ~5,400 an emoji-heavy message inside the limit was refused as "too
    long". Built, not computed: the arithmetic was only ever a model."""
    import json

    from annotated_types import MaxLen

    from app.api.schemas import VerifyTextRequest

    language_max = next(m.max_length for m in VerifyTextRequest.model_fields["language"].metadata
                        if isinstance(m, MaxLen))
    body = json.dumps({"text": "\U0001F600" * settings.max_input_chars,
                       "language": "\U0001F600" * language_max}).encode()
    assert len(body) <= settings.max_json_bytes, (
        f"the costliest maximum message is {len(body)} bytes; the cap is "
        f"{settings.max_json_bytes}")
    resp = client.post("/api/v1/verify/text", content=body,
                       headers={"content-type": "application/json"})
    assert resp.status_code != 413, resp.text
