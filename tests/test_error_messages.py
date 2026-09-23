"""Every error a person can see is written for them. Free.

Vinayak (2026-09-22): "There's also an error message that displays technical
text." Reproduced before fixing — four of them, straight from the API:

    Could not read audio from this file (Error opening input files: End of file).
    Unsupported image type: application/pdf
    Unsupported media type: application/vnd.openxmlformats-officedocument...
    Audio checking is not configured (SARVAM_API_KEY missing).

The first is ffmpeg's own stderr (which can also carry server temp paths);
the last is an operator's configuration detail shown to a stranger. The
technical detail still reaches the server log; the person gets a sentence
that says what to do instead.
"""
import re

import pytest

from app.config import settings

# Things a person should never have to read.
TECHNICAL = re.compile(
    r"application/|audio/|image/|video/|_KEY|SARVAM|ffmpeg|ffprobe|"
    r"Error opening|End of file|Traceback|Exception|HTTP \d|"
    r"[A-Z]{2,}_[A-Z_]{2,}",           # an environment-variable name
)


def _assert_plain(message: str):
    assert message and not TECHNICAL.search(message), f"technical text: {message!r}"
    assert message.rstrip().endswith((".", "!", "?")), f"not a sentence: {message!r}"


def test_unreadable_audio(client, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "configured")
    resp = client.post("/api/v1/verify/media",
                       files={"file": ("note.ogg", b"not audio at all", "audio/ogg")})
    assert resp.status_code == 422
    _assert_plain(resp.json()["detail"])


def test_a_pdf_sent_as_an_image(client):
    resp = client.post("/api/v1/verify/image",
                       files={"file": ("doc.pdf", b"%PDF-1.4", "application/pdf")})
    assert resp.status_code == 415
    _assert_plain(resp.json()["detail"])


def test_a_word_document_sent_as_media(client, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "configured")
    resp = client.post("/api/v1/verify/media", files={"file": (
        "a.docx", b"PK",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert resp.status_code == 415
    _assert_plain(resp.json()["detail"])


@pytest.mark.parametrize("path, kwargs", [
    ("/api/v1/verify/media", {"files": {"file": ("n.ogg", b"OggS", "audio/ogg")}}),
    ("/api/v1/verify/link", {"json": {"url": "https://www.instagram.com/reel/DbsVyqLpbRa/"}}),
])
def test_missing_transcription_config_is_not_a_strangers_problem(client, monkeypatch,
                                                                   capsys, path, kwargs):
    from app.api import routes as R
    from app.providers.links import LinkInfo

    monkeypatch.setattr(settings, "sarvam_api_key", "")
    # A link whose speech needs ASR (no subtitles), so the config gate fires.
    monkeypatch.setattr(R, "resolve_link", lambda url: LinkInfo(
        url=url, platform="Instagram", video_id="x", title="", uploader="",
        duration=10, caption="", has_media=True, subtitle=None))
    resp = client.post(path, **kwargs)
    assert resp.status_code == 503
    _assert_plain(resp.json()["detail"])
    assert "SARVAM_API_KEY" in capsys.readouterr().out    # the operator still hears it


def test_a_refusal_reads_as_a_sentence(client, monkeypatch):
    from app.engine import chat as C

    async def refused(text, *, heard=None, emit=None, language=None):
        raise C.AnswerRefused("cyber")

    monkeypatch.setattr(C, "answer", refused)
    job = client.post("/api/v1/verify/text", json={"text": "x"}).json()["job_id"]
    report = client.get(f"/api/v1/reports/{job}").json()
    assert report["status"] == "FAILED"
    _assert_plain(report["error"])
    assert "cyber" not in report["error"]


def test_audio_that_fails_behind_the_202_reads_as_a_sentence(client, monkeypatch, tmp_path):
    """The background path: MediaError text used to be interpolated in."""
    from app.api import routes as R
    from app.providers.media import MediaError

    async def broken(wav, duration):
        raise MediaError("Error opening input files: /tmp/tmpab12/media.ogg: End of file")

    monkeypatch.setattr(settings, "sarvam_api_key", "configured")
    monkeypatch.setattr(R, "transcribe_wav", broken)
    monkeypatch.setattr(R, "normalize_to_wav", lambda data, name, cap: (b"RIFF", 1.0))
    resp = client.post("/api/v1/verify/media",
                       files={"file": ("n.ogg", b"OggS", "audio/ogg")})
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "FAILED"
    _assert_plain(report["error"])
    assert "/tmp" not in report["error"]


def test_the_page_never_shows_http_codes_or_browser_errors():
    """`HTTP 500` and a browser's own "Failed to fetch" are not for readers."""
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "static" / "index.html"
            ).read_text(encoding="utf-8")
    body = page[page.index("async function submit("):page.index("// Resume on load")]
    assert "`HTTP ${resp.status}`" not in body
    assert "function friendlyError(" in page
    assert "friendlyError(e)" in body
