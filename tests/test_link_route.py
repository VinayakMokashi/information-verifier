"""/verify/link: paste a Reel or Shorts URL. Free — every seam faked.

The conftest client fixture fakes resolve_link and gather_link_text (network
and Sarvam). Tests that exercise the REAL gather logic restore the handle
grabbed at import time below and fake only the inner seams (subtitles,
download, ASR) — so the cost-order logic itself is what runs.
"""
import shutil
import subprocess

import pytest

import scripts.fake_stages as F
from app.api import limits, routes as R
from app.config import settings
from app.providers.links import LinkError, LinkInfo, LinkTooLarge, SubtitleRef

# Grabbed at collection time, BEFORE the client fixture patches them.
REAL_GATHER = R.gather_link_text

REEL = "https://www.instagram.com/reel/DbsVyqLpbRa/"
SHORT = "https://www.youtube.com/shorts/QBHKZ36_dlo"


def _info(**kw) -> LinkInfo:
    base = dict(url=REEL, platform="Instagram", video_id="X", title="t",
                uploader="u", duration=None, caption="", has_media=True,
                subtitle=None)
    base.update(kw)
    return LinkInfo(**base)


def _submit(client, url=REEL):
    return client.post("/api/v1/verify/link", json={"url": url})


def _report(client, resp):
    assert resp.status_code == 202, resp.text
    return client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()


def _tone_ogg(tmp_path) -> bytes:
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    out = tmp_path / "tone.ogg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    return out.read_bytes()


# -- the gate: what may even be resolved --------------------------------------

@pytest.mark.parametrize("url", [
    "http://www.youtube.com/shorts/x",         # not https
    "https://youtube.com.evil.com/watch",      # lookalike
    "https://evil.com/reel/x",                 # not a platform at all
    "https://user@instagram.com/reel/x",       # userinfo
])
def test_disallowed_urls_never_reach_resolve(client, url, monkeypatch):
    calls = []
    monkeypatch.setattr(R, "resolve_link", lambda u: calls.append(u))

    resp = _submit(client, url)

    assert resp.status_code == 422
    assert calls == []                       # the server never touched the URL
    assert "Instagram and YouTube" in resp.json()["detail"]


def test_resolve_failures_become_readable_http(client, monkeypatch):
    monkeypatch.setattr(R, "resolve_link", lambda u: (_ for _ in ()).throw(
        LinkError("gated", "That post needs a login to view.")))
    resp = _submit(client)
    assert resp.status_code == 422
    assert "login" in resp.json()["detail"]

    monkeypatch.setattr(R, "resolve_link", lambda u: (_ for _ in ()).throw(
        LinkError("network", "The platform could not be reached right now.")))
    assert _submit(client).status_code == 502


def test_a_rejected_link_is_refunded_nothing_was_spent(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    monkeypatch.setattr(R, "resolve_link", lambda u: (_ for _ in ()).throw(
        LinkError("not_found", "No public post was found at that link.")))

    assert _submit(client).status_code == 422
    assert len(limits._day) == 0


def test_a_known_overlong_video_is_rejected_free(client, monkeypatch):
    """YouTube advertises duration, so the cap can fire before any download."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(duration=999.0))

    resp = _submit(client, SHORT)

    assert resp.status_code == 413
    assert "999" in resp.json()["detail"]
    assert len(limits._day) == 0              # refunded: nothing was fetched


def test_audio_without_sarvam_key_is_a_clear_503(client, monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "")
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(subtitle=None))
    assert _submit(client).status_code == 503


def test_a_post_with_nothing_to_check_is_422(client, monkeypatch):
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(has_media=False, caption="   "))
    assert _submit(client).status_code == 422


# -- the demo/fake path (what serve_demo exercises) ---------------------------

def test_link_flow_end_to_end_with_fakes(client):
    report = _report(client, _submit(client))
    assert report["status"] == "COMPLETE"
    assert report["overall_rating"] == "FALSE"
    # Machine-read text is shown back (invariant 4) — link text is machine-read.
    assert "simulated reel" in report["source_text"]


# -- the real gather logic (inner seams faked) --------------------------------

def _wire_real_gather(monkeypatch, *, subtitle=None, download=None, sarvam_key=True):
    monkeypatch.setattr(R, "gather_link_text", REAL_GATHER)
    monkeypatch.setattr(R, "subtitle_text",
                        subtitle if subtitle else lambda ref: None)
    monkeypatch.setattr(
        R, "download_link_audio",
        download if download else lambda url, mb: (_ for _ in ()).throw(
            AssertionError("download must not be called in this test")))
    if sarvam_key:
        monkeypatch.setattr(settings, "sarvam_api_key", "demo-mode-not-a-real-key")


def test_subtitles_replace_asr_entirely(client, monkeypatch):
    """The cost lever: a caption track means no download and no Sarvam."""
    asr_calls = []

    class NoASR:
        async def transcribe(self, audio, language_hint=None):
            asr_calls.append(1)
            raise AssertionError("ASR must not run when subtitles exist")

    _wire_real_gather(monkeypatch,
                      subtitle=lambda ref: "डब्ल्यूएचओ ने कहा कि 5जी से कोरोना फैलता है")
    monkeypatch.setattr(R, "get_asr_provider", lambda: NoASR())
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        subtitle=SubtitleRef("hi-orig", "https://yt.example/sub", "json3"),
        caption="Sarkari alert!"))

    report = _report(client, _submit(client, SHORT))

    assert report["status"] == "COMPLETE"
    assert asr_calls == []
    assert "डब्ल्यूएचओ ने कहा" in report["source_text"]
    assert "Sarkari alert!" in report["source_text"]   # caption rides along


def test_no_subtitles_downloads_and_transcribes(client, monkeypatch, tmp_path):
    """The Instagram shape: no subtitle track -> capped download -> ASR."""
    ogg = _tone_ogg(tmp_path)
    downloads = []

    def fake_download(url, max_bytes):
        downloads.append((url, max_bytes))
        return ogg, ".ogg"

    _wire_real_gather(monkeypatch, download=fake_download)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(caption="Dekho yeh!"))

    report = _report(client, _submit(client))

    assert report["status"] == "COMPLETE"
    assert downloads == [(REEL, settings.max_media_bytes)]  # cap passed through
    assert "5G se coronavirus" in report["source_text"]     # FakeASR transcript
    assert "Dekho yeh!" in report["source_text"]


def test_a_failed_subtitle_fetch_degrades_to_asr_not_failure(client, monkeypatch, tmp_path):
    ogg = _tone_ogg(tmp_path)
    _wire_real_gather(monkeypatch, subtitle=lambda ref: None,
                      download=lambda url, mb: (ogg, ".ogg"))
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        subtitle=SubtitleRef("hi-orig", "https://yt.example/sub", "json3")))

    report = _report(client, _submit(client, SHORT))
    assert report["status"] == "COMPLETE"
    assert "5G se coronavirus" in report["source_text"]


def test_caption_only_posts_cost_no_media_work_at_all(client, monkeypatch):
    _wire_real_gather(monkeypatch)   # download would AssertionError if touched
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        has_media=False,
        caption="WHO ne kaha hai ki 5G se coronavirus phailta hai."))

    report = _report(client, _submit(client))
    assert report["status"] == "COMPLETE"
    assert "5G se coronavirus" in report["source_text"]


def test_a_stuffed_caption_is_capped(client, monkeypatch):
    _wire_real_gather(monkeypatch)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        has_media=False, caption="x" * 50_000))

    report = _report(client, _submit(client))
    assert len(report["source_text"]) <= R._MAX_CAPTION_CHARS + 10


# -- background failures ------------------------------------------------------

def test_background_failure_is_a_failed_report_with_readable_error(client, monkeypatch):
    _wire_real_gather(monkeypatch, download=lambda url, mb: (_ for _ in ()).throw(
        LinkTooLarge(settings.max_media_bytes)))
    monkeypatch.setattr(R, "resolve_link", lambda u: _info())

    report = _report(client, _submit(client))

    assert report["status"] == "FAILED"
    assert "larger than this service handles" in report["error"]
    assert "Traceback" not in report["error"]


def test_an_overlong_download_fails_with_the_duration_message(client, monkeypatch, tmp_path):
    from app.providers.media import MediaTooLong

    def too_long(data, filename, max_seconds):
        raise MediaTooLong(3600.0)

    _wire_real_gather(monkeypatch, download=lambda url, mb: (b"x", ".ogg"))
    monkeypatch.setattr(R, "normalize_to_wav", too_long)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info())

    report = _report(client, _submit(client))
    assert report["status"] == "FAILED"
    assert "3600s" in report["error"]


def test_an_accepted_job_keeps_its_quota_slot_even_if_the_fetch_fails(client, monkeypatch):
    """A refund cannot be issued from a background task; over-counting is the
    error the wallet survives."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    _wire_real_gather(monkeypatch, download=lambda url, mb: (_ for _ in ()).throw(
        LinkError("network", "fetch failed")))
    monkeypatch.setattr(R, "resolve_link", lambda u: _info())

    report = _report(client, _submit(client))

    assert report["status"] == "FAILED"
    assert len(limits._day) == 1
