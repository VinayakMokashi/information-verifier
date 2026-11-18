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
    detail = resp.json()["detail"]
    # Names every supported platform, from the single definition.
    for platform in ("Instagram", "YouTube", "Facebook"):
        assert platform in detail


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
    assert limits.used_today() == 0


def test_a_resolve_that_outlives_its_bound_is_a_refunded_502(client, monkeypatch):
    """The resolve runs INLINE, before the 202, so a caller is waiting on it.
    Traced by review: the Telegram bot gave up at 30 s and told the person to
    try again — while the server finished the resolve, created the job and
    billed a check whose answer nobody would ever deliver. The inline part
    is now bounded, well inside the bot's patience (tested bot-side)."""
    import time

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    monkeypatch.setattr(R, "_RESOLVE_WALL_S", 0.2)
    monkeypatch.setattr(R, "resolve_link", lambda u: time.sleep(1.0) or _info())

    resp = _submit(client)
    assert resp.status_code == 502
    assert "could not be reached" in resp.json()["detail"]
    assert limits.used_today() == 0                 # nothing was spent


def test_a_known_overlong_video_is_rejected_free(client, monkeypatch):
    """YouTube advertises duration, so the cap can fire before any download."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(duration=999.0))

    resp = _submit(client, SHORT)

    assert resp.status_code == 413
    assert "999" in resp.json()["detail"]
    assert limits.used_today() == 0           # refunded: nothing was fetched


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
    assert report["sections"]
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
    assert limits.used_today() == 1


# -- the page routes a pasted link ---------------------------------------------

def _page() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parent.parent / "static" / "index.html"
            ).read_text(encoding="utf-8")


def test_the_page_sends_a_bare_link_to_verify_link():
    page = _page()
    assert "api/v1/verify/link" in page
    assert "LINK_RE" in page
    # Anchored (^…$): a forward that merely CONTAINS a link stays a text check.
    assert "const LINK_RE = /^https:" in page
    assert page.index("LINK_RE.test(text)") < page.index('fetch("api/v1/verify/text"')


def test_the_page_link_regex_matches_what_the_server_accepts():
    """The page's quick test and the server's strict gate must agree on the
    happy path, or a valid reel would be sent as text and billed for nothing."""
    import re as _re

    page = _page()
    m = _re.search(r"const LINK_RE = /(.+)/i;", page)
    assert m, "LINK_RE not found in the page"
    link_re = _re.compile(m.group(1), _re.I)

    from app.providers.links import ALLOWED_HOSTS, allowed_link_host

    # EVERY allowlisted host, not a hand-picked few. The old version checked
    # four Instagram/YouTube URLs, so when Facebook was added server-side the
    # drift this test exists to catch went unguarded for the newest platform.
    for host in sorted(ALLOWED_HOSTS):
        url = f"https://{host}/reel/abc123"
        assert allowed_link_host(url) is not None, f"server rejects {url}"
        assert link_re.match(url), (
            f"the page would send {url} to /verify/text — a valid link "
            "treated as a string, billed, and finding nothing")
    # And both reject a message that merely contains a link.
    mixed = "Dekho yeh! https://youtu.be/x sach hai kya?"
    assert not link_re.match(mixed)


def test_every_user_facing_link_message_names_every_platform():
    """Facebook was added to the hosts, extractors and page regex — but all
    three rejection messages still said 'Instagram and YouTube', so a user
    whose valid FB link failed was told the platform is unsupported."""
    from app.providers.links import SUPPORTED_LINKS_MSG, SUPPORTED_PLATFORMS

    for platform in SUPPORTED_PLATFORMS:
        assert platform in SUPPORTED_LINKS_MSG

    # The stale wording must not come back anywhere in shipped code.
    import pathlib
    for path in ["app/api/routes.py", "app/providers/links.py",
                 "scripts/telegram_bot.py"]:
        text = pathlib.Path(path).read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue                      # comments may quote the history
            assert "Instagram and YouTube links" not in stripped, f"{path}: {line}"


def test_the_probe_predicts_the_server_exactly():
    """A probe that disagrees with the endpoint it models is worse than none."""
    import scripts.link_probe as probe
    from app.providers.links import ALLOWED_HOSTS

    assert probe._ALLOWED_HOSTS is ALLOWED_HOSTS      # aliased, never copied
    # And it classifies failures through the app's own classifier.
    assert "gated" in probe._diagnose(RuntimeError("Instagram sent an empty "
                                                   "media response, use cookies"))
    assert "network" in probe._diagnose(RuntimeError("HTTP Error 429: Too Many"))


# -- the transcript cache (2026-09-22) ----------------------------------------

def test_the_same_reel_twice_is_transcribed_once(client, monkeypatch):
    """One viral reel forwarded by many people re-downloaded and re-bought its
    whole ASR every time (~₹0.58 for a 70 s clip). The platform's own video
    id is known for free at resolve time, so it keys what the post said."""
    from app.api import routes as R

    calls = []

    async def counting_gather(info):
        calls.append(info.video_id)
        return "WHO ne kaha 5G se corona phailta hai (transcribed)"

    monkeypatch.setattr(R, "gather_link_text", counting_gather)
    for _ in range(3):
        resp = client.post("/api/v1/verify/link", json={"url": REEL})
        assert resp.status_code == 202
    assert len(calls) == 1, f"transcribed {len(calls)} times"
    last = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    # What the machine read is still shown back on a cache hit (invariant 4).
    assert last["source_text"].endswith("(transcribed)")
    assert last["usage"]["asr_seconds"] == 0


def test_a_failed_transcription_is_not_remembered(client, monkeypatch):
    """A failure must be retried next time, not cached as the post's text."""
    from app.api import routes as R
    from app.providers.links import LinkError

    outcomes = [LinkError("network", "The platform could not be reached."),
                "Now it worked"]
    calls = []

    async def flaky_gather(info):
        calls.append(1)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(R, "gather_link_text", flaky_gather)
    first = client.post("/api/v1/verify/link", json={"url": REEL}).json()["job_id"]
    assert client.get(f"/api/v1/reports/{first}").json()["status"] == "FAILED"
    second = client.post("/api/v1/verify/link", json={"url": REEL}).json()["job_id"]
    assert client.get(f"/api/v1/reports/{second}").json()["status"] == "COMPLETE"
    assert len(calls) == 2


def test_a_video_whose_audio_gave_nothing_is_retried_not_remembered(
        client, monkeypatch, tmp_path):
    """Found by review, reproduced: the cache's own rule is that a
    transcription that heard nothing is retried next time — but the empty
    check ran on caption + speech combined, so a post whose ASR came back
    empty was remembered as its caption alone for 30 days, and the claim it
    SPOKE could not be checked again for a month. Only what the audio or
    subtitles added beyond the caption is worth remembering; a caption costs
    nothing to read again."""
    from app.providers.asr import Transcript

    ogg = _tone_ogg(tmp_path)
    asr_calls = []

    class HeardNothing:
        async def transcribe(self, audio, language_hint=None):
            asr_calls.append(1)
            return Transcript(text="", language=None)

    _wire_real_gather(monkeypatch, download=lambda url, mb: (ogg, ".ogg"))
    monkeypatch.setattr(R, "get_asr_provider", lambda: HeardNothing())
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(caption="Watch till the end!! #viral #news"))

    for _ in range(2):
        assert _report(client, _submit(client))["status"] == "COMPLETE"
    assert len(asr_calls) == 2, "the empty transcription was remembered, not retried"


def test_an_empty_transcript_is_never_stored(client):
    from app.store.repository import TranscriptCache

    cache = TranscriptCache()
    cache.put("v1:instagram:x", "   ")
    assert cache.get("v1:instagram:x") is None


def test_transcripts_expire(client, monkeypatch):
    from app.store.repository import TranscriptCache

    cache = TranscriptCache()
    cache.put("v1:youtube:abc", "what the video said")
    assert cache.get("v1:youtube:abc") == "what the video said"
    monkeypatch.setattr(settings, "transcript_cache_ttl_days", -1)
    assert cache.get("v1:youtube:abc") is None


def test_a_post_without_an_id_is_not_cached():
    from app.api.routes import transcript_key
    from app.providers.links import LinkInfo

    base = dict(url=REEL, title="", uploader="", duration=None, caption="",
                has_media=True, subtitle=None)
    assert transcript_key(LinkInfo(platform="Instagram", video_id="", **base)) is None
    # v2: v1 entries could hold a caption alone, stored when the
    # transcription heard nothing — a rule that changed, so they are retired.
    assert transcript_key(LinkInfo(platform="Instagram", video_id="DbsVyqLpbRa",
                                   **base)) == "v2:instagram:DbsVyqLpbRa"


def test_a_link_with_a_line_break_is_a_readable_refusal_not_a_500(client):
    """REPRODUCED (review R3): the gate passed it and httpx crashed on it."""
    resp = client.post("/api/v1/verify/link",
                       json={"url": "https://www.facebook.com/share/r/17RQxbYP2j/\nKya?"})
    assert resp.status_code == 422


# -- photo posts and carousels (2026-11-18) -----------------------------------
# SEEN LIVE: four Instagram photo posts on 17-18 Nov were refused as "That
# link could not be read." Their pictures are now read by the vision model,
# all of them in ONE paid call, and what it read is shown back (invariant 4).

def _pics(n, start=1):
    return tuple(f"https://instagram.fbom3-2.fna.fbcdn.net/{i}.jpg"
                 for i in range(start, start + n))


def _wire_pictures(monkeypatch, *, fetch=None):
    _wire_real_gather(monkeypatch)        # no subtitles; a download would fail
    fetched, read = [], []

    def fake_fetch(url, max_bytes):
        fetched.append((url, max_bytes))
        return b"\xff\xd8" + url.encode(), "image/jpeg"

    async def fake_ocr(images):
        read.append(list(images))
        return "\n".join(f"Image {i}: words {i}" for i in range(1, len(images) + 1))

    monkeypatch.setattr(R, "fetch_post_image", fetch or fake_fetch)
    monkeypatch.setattr(R, "ocr_images", fake_ocr)
    return fetched, read


def test_a_photo_post_is_read_in_one_vision_call(client, monkeypatch):
    fetched, read = _wire_pictures(monkeypatch)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        has_media=False, caption="Sarkar sabko free laptop degi!", images=_pics(2)))

    report = _report(client, _submit(client))

    assert report["status"] == "COMPLETE"
    assert len(read) == 1 and len(read[0]) == 2          # one call, both pictures
    assert [cap for _, cap in fetched] == [settings.max_image_bytes] * 2
    assert "Sarkar sabko free laptop degi!" in report["source_text"]
    assert "Image 2: words 2" in report["source_text"]   # shown back


def test_past_the_cap_only_the_first_pictures_are_read_and_it_says_so(client, monkeypatch):
    monkeypatch.setattr(settings, "max_images_per_check", 2)
    _, read = _wire_pictures(monkeypatch)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        has_media=False, images=_pics(7), videos_skipped=2))

    report = _report(client, _submit(client))

    assert len(read[0]) == 2                             # the bound on the paid call
    assert "7 pictures" in report["source_text"]
    assert "first 2" in report["source_text"]
    assert "2 videos" in report["source_text"]


def test_a_photo_post_without_a_caption_is_checked_not_refused(client, monkeypatch):
    _wire_pictures(monkeypatch)
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(has_media=False, caption="", images=_pics(1)))
    assert _report(client, _submit(client))["status"] == "COMPLETE"


def test_a_picture_that_cannot_be_fetched_is_left_out_and_said(client, monkeypatch):
    def flaky(url, max_bytes):
        if url.endswith("2.jpg"):
            raise LinkError("network", "slow")
        return b"\xff\xd8", "image/jpeg"

    _, read = _wire_pictures(monkeypatch, fetch=flaky)
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(has_media=False, images=_pics(2)))

    report = _report(client, _submit(client))

    assert report["status"] == "COMPLETE" and len(read[0]) == 1
    assert "could not be fetched" in report["source_text"]


def test_no_picture_fetched_is_a_readable_failure_and_nothing_is_read(client, monkeypatch):
    def down(url, max_bytes):
        raise LinkError("network", "down")

    _, read = _wire_pictures(monkeypatch, fetch=down)
    monkeypatch.setattr(R, "resolve_link", lambda u: _info(
        has_media=False, caption="Some caption", images=_pics(1)))

    report = _report(client, _submit(client))

    assert report["status"] == "FAILED" and read == []   # no paid reading
    assert "screenshot" in report["error"]


def test_a_read_post_is_remembered_by_its_id(client, monkeypatch):
    _, read = _wire_pictures(monkeypatch)
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(has_media=False, images=_pics(1), video_id="P1"))
    for _ in range(2):
        assert _report(client, _submit(client))["status"] == "COMPLETE"
    assert len(read) == 1, "the same post's pictures were paid for twice"


def test_a_partly_read_post_is_not_remembered(client, monkeypatch):
    """Invariant 6: the transcript cache never keeps a failed read. A picture
    missed today must be fetched again next time, not left out for 30 days."""
    def flaky(url, max_bytes):
        if url.endswith("2.jpg"):
            raise LinkError("network", "slow")
        return b"\xff\xd8", "image/jpeg"

    _, read = _wire_pictures(monkeypatch, fetch=flaky)
    monkeypatch.setattr(R, "resolve_link",
                        lambda u: _info(has_media=False, images=_pics(2), video_id="P2"))
    for _ in range(2):
        assert _report(client, _submit(client))["status"] == "COMPLETE"
    assert len(read) == 2
