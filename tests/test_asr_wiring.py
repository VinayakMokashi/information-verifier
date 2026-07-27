"""What we actually send to Sarvam, and what real phone audio does to it.

Free: the Sarvam call is intercepted by a mock transport and never sent.
These pin the wire contract (endpoint, auth header, model id, multipart
fields) that a live probe would otherwise be the only way to catch, and the
container formats Indian phones and WhatsApp really produce.
"""
import shutil
import subprocess

import httpx
import pytest

from app.config import settings
from app.providers.asr import SarvamASR
from app.providers.media import normalize_to_wav

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _clip(tmp_path, name: str, args: list[str], seconds: float = 2.0) -> bytes:
    out = tmp_path / name
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", f"sine=frequency=300:duration={seconds}", *args, str(out)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        pytest.skip(f"this ffmpeg build cannot make {name}")
    return out.read_bytes()


def test_whatsapp_voice_note_format_normalizes(tmp_path):
    """WhatsApp PTT: OGG/Opus, mono, 16 kHz, low VBR, .opus extension."""
    data = _clip(tmp_path, "PTT-20260727-WA0001.opus",
                 ["-c:a", "libopus", "-b:a", "24k", "-ar", "16000",
                  "-ac", "1", "-application", "voip"], seconds=8)
    wav, duration = normalize_to_wav(data, "PTT-20260727-WA0001.opus")
    assert wav[:4] == b"RIFF"
    assert 7.5 < duration < 8.5


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("clip.m4a", ["-c:a", "aac"]),
        ("clip.mp3", ["-c:a", "libmp3lame"]),
        ("clip.webm", ["-c:a", "libopus"]),
        ("clip.amr", ["-ar", "8000", "-ab", "12.2k", "-c:a", "libopencore_amrnb"]),
    ],
)
def test_phone_audio_containers_normalize(tmp_path, name, args):
    wav, duration = normalize_to_wav(_clip(tmp_path, name, args), name)
    assert wav[:4] == b"RIFF"
    assert 1.5 < duration < 3.5


def test_sarvam_request_shape(tmp_path, monkeypatch):
    """Endpoint, auth header, model id and multipart fields must not drift."""
    wav, _ = normalize_to_wav(_clip(tmp_path, "c.ogg", ["-c:a", "libopus"]), "c.ogg")
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["key"] = request.headers.get("api-subscription-key")
        body = request.content
        seen["fields"] = {f for f in (b"model", b"language_code", b"file")
                          if b'name="%s"' % f in body}
        i = body.find(b'name="model"')
        seen["model"] = body[i:i + 80].split(b"\r\n\r\n")[1].split(b"\r\n")[0].decode()
        # Sarvam replies in the source script — Devanagari here.
        return httpx.Response(200, json={"transcript": "5जी से कोरोना नहीं फैलता",
                                         "language_code": "hi-IN"})

    original = httpx.AsyncClient

    class Mocked(original):
        def __init__(self, *a, **kw):
            kw["transport"] = httpx.MockTransport(handler)
            super().__init__(*a, **kw)

    monkeypatch.setattr(httpx, "AsyncClient", Mocked)

    import asyncio
    transcript = asyncio.run(SarvamASR("test-key").transcribe(wav, language_hint="hi-IN"))

    assert seen["url"] == "https://api.sarvam.ai/speech-to-text"
    assert seen["key"] == "test-key"
    assert seen["fields"] == {b"model", b"language_code", b"file"}
    # saarika is deprecated; a silent revert would break Indic coverage.
    assert seen["model"] == "saaras:v3"
    # Devanagari must survive the JSON decode intact.
    assert transcript.text == "5जी से कोरोना नहीं फैलता"
    assert transcript.language == "hi-IN"


def test_long_note_is_chunked_under_the_sync_limit(tmp_path):
    from app.providers.media import split_wav

    wav, duration = normalize_to_wav(
        _clip(tmp_path, "long.opus", ["-c:a", "libopus", "-ar", "16000", "-ac", "1"],
              seconds=90),
        "long.opus",
    )
    chunks = split_wav(wav, settings.asr_chunk_seconds)
    assert duration > 60
    assert len(chunks) >= 4                      # 90s / 29s
    assert all(c[:4] == b"RIFF" for c in chunks)
