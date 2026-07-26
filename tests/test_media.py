"""Media path — real ffmpeg (tone clips generated on the fly), fake ASR.

Free: no Sarvam call, no LLM call. The one thing these tests can't prove is
Sarvam's live response shape — that's covered by scripts/asr_probe.py.
"""
import shutil
import subprocess

import pytest

from app.api import routes as R
from app.config import settings
from app.providers.asr import Transcript
from app.providers.media import MediaError, normalize_to_wav, split_wav

pytestmark = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg not installed"
)


def _tone(tmp_path, seconds: float, fmt: str = "ogg") -> bytes:
    """Synthesize a sine-tone clip — a real, sniffable audio container."""
    out = tmp_path / f"tone.{fmt}"
    codec = ["-c:a", "libopus"] if fmt == "ogg" else []
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         *codec, str(out)],
        check=True, capture_output=True,
    )
    return out.read_bytes()


class FakeASR:
    def __init__(self) -> None:
        self.calls = 0

    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        self.calls += 1
        return Transcript(text="WHO ne kaha 5G se corona hota hai", language="hi-IN")


# -- ffmpeg helpers (no app, no ASR) ----------------------------------------

def test_normalize_ogg_opus_to_wav(tmp_path):
    wav, duration = normalize_to_wav(_tone(tmp_path, 2.0), "voice_note.ogg")
    assert wav[:4] == b"RIFF"
    assert 1.5 < duration < 2.5


def test_normalize_rejects_garbage():
    with pytest.raises(MediaError):
        normalize_to_wav(b"this is not audio", "fake.mp3")


def test_split_wav_chunks(tmp_path):
    wav, _ = normalize_to_wav(_tone(tmp_path, 5.0), "long.ogg")
    chunks = split_wav(wav, chunk_seconds=2)
    assert len(chunks) == 3
    assert all(c[:4] == b"RIFF" for c in chunks)


# -- the /verify/media route (offline client from conftest) ------------------

@pytest.fixture()
def media_client(client, monkeypatch, tmp_path):
    fake = FakeASR()
    monkeypatch.setattr(settings, "sarvam_api_key", "test-key")
    monkeypatch.setattr(R, "get_asr_provider", lambda: fake)
    client.fake_asr = fake
    return client


def test_voice_note_flow(media_client, tmp_path):
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", _tone(tmp_path, 2.0), "audio/ogg")},
    )
    assert resp.status_code == 202
    assert media_client.fake_asr.calls == 1
    report = media_client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "COMPLETE"
    assert report["overall_rating"] == "FALSE"


def test_long_audio_is_chunked(media_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "asr_chunk_seconds", 2)
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("long.ogg", _tone(tmp_path, 5.0), "audio/ogg")},
    )
    assert resp.status_code == 202
    assert media_client.fake_asr.calls == 3


def test_unsupported_type_rejected(media_client):
    resp = media_client.post(
        "/api/v1/verify/media", files={"file": ("a.txt", b"hi", "text/plain")}
    )
    assert resp.status_code == 415


def test_missing_key_gives_503(media_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", _tone(tmp_path, 1.0), "audio/ogg")},
    )
    assert resp.status_code == 503


def test_oversize_upload_rejected(media_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_media_bytes", 100)
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", _tone(tmp_path, 1.0), "audio/ogg")},
    )
    assert resp.status_code == 413


def test_overlong_audio_rejected(media_client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_media_seconds", 1)
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", _tone(tmp_path, 3.0), "audio/ogg")},
    )
    assert resp.status_code == 413
    assert media_client.fake_asr.calls == 0  # rejected before spending credits


def test_garbage_bytes_rejected(media_client):
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", b"not audio at all", "audio/ogg")},
    )
    assert resp.status_code == 422


def test_hostile_filename_cannot_shape_the_temp_path(tmp_path):
    from app.providers.media import _safe_suffix

    assert _safe_suffix("note.ogg") == ".ogg"
    assert _safe_suffix("note.OGG") == ".OGG"
    assert _safe_suffix("../../etc/passwd") == ".bin"
    assert _safe_suffix("x.ogg/../../../evil") == ".bin"
    assert _safe_suffix('a."; del *.*;"') == ".bin"
    assert _safe_suffix("noextension") == ".bin"
    # A hostile name still transcodes normally.
    wav, _ = normalize_to_wav(_tone(tmp_path, 1.0), "../../evil name.ogg")
    assert wav[:4] == b"RIFF"


def test_declared_oversize_rejected_before_buffering(media_client, monkeypatch):
    """413 must come from middleware, before the body is parsed or spooled."""
    monkeypatch.setattr(settings, "max_media_bytes", 1000)

    def explode(*a, **kw):  # nothing in the route may run
        raise AssertionError("request body was processed despite being oversize")

    monkeypatch.setattr(R, "normalize_to_wav", explode)
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("huge.ogg", b"x" * 50_000, "audio/ogg")},
    )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"]


def test_asr_outage_is_a_clean_502_not_a_500(media_client, tmp_path, monkeypatch):
    import httpx

    class DownASR:
        async def transcribe(self, audio, language_hint=None):
            raise httpx.ConnectError("sarvam unreachable")

    monkeypatch.setattr(R, "get_asr_provider", lambda: DownASR())
    resp = media_client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", _tone(tmp_path, 1.0), "audio/ogg")},
    )
    assert resp.status_code == 502
    assert "unavailable" in resp.json()["detail"]
