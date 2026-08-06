"""The links provider: allowlist, caption parsing, subtitle choice. Free.

No network anywhere in this file. What these pin is the part of link
ingestion the SERVER is responsible for: which hosts it will ever fetch
(this decides what the machine connects to, so it gets the trusted_sources
level of paranoia), which caption track can stand in for paid ASR, and that
parsers survive the messy formats platforms actually serve.
"""
import pytest

from app.providers import links as L

# -- the fetch allowlist ------------------------------------------------------

GOOD = [
    ("https://www.instagram.com/reel/DbsVyqLpbRa/", "www.instagram.com"),
    ("https://instagram.com/reel/x/", "instagram.com"),
    ("https://m.instagram.com/reel/x/", "m.instagram.com"),
    ("https://www.youtube.com/shorts/QBHKZ36_dlo", "www.youtube.com"),
    ("https://www.youtube.com/watch?v=XI3ogCBeeSY", "www.youtube.com"),
    ("https://youtu.be/UiR55MZnzu0", "youtu.be"),
    ("https://m.youtube.com/watch?v=x", "m.youtube.com"),
    ("  https://youtu.be/abc  ", "youtu.be"),          # paste-with-whitespace
    ("https://WWW.YOUTUBE.COM/shorts/x", "www.youtube.com"),
]


@pytest.mark.parametrize("url,host", GOOD)
def test_real_platform_urls_pass(url, host):
    assert L.allowed_link_host(url) == host


EVIL = [
    "http://www.youtube.com/shorts/x",            # https only
    "https://youtube.com.evil.com/watch",         # lookalike suffix
    "https://evilyoutube.com/watch",              # lookalike prefix
    "https://youtu.be.evil.com/x",
    "https://user@youtube.com/watch",             # userinfo trickery
    "https://user:pass@instagram.com/reel/x",
    "https://evil.com\\@youtube.com/",            # parser-differential classic
    "javascript://www.youtube.com/%0aalert(1)",
    "file:///etc/passwd",
    "https://localhost/reel/x",
    "https://127.0.0.1/watch",
    "https://[::1]/watch",
    "https://youtube.com:8443@evil.com/",
    "",
    "not a url at all",
    "https://" + "a" * 2050 + ".com/",            # length bound
]


@pytest.mark.parametrize("url", EVIL)
def test_everything_else_fails_closed(url):
    """This check decides what the SERVER fetches — the SSRF door §7 closed
    for uploads must not reopen through the query string."""
    assert L.allowed_link_host(url) is None


def test_download_refuses_a_disallowed_url_even_if_called_directly():
    """Defense in depth: the route validates, but the provider must not trust
    its caller — a future code path could reach download without the check."""
    with pytest.raises(L.LinkError):
        L.download_link_audio("https://evil.com/x", max_bytes=1000)


def test_generic_extractor_is_not_allowed():
    """yt-dlp's generic extractor fetches ANY url; its absence from the
    allowlist is what makes redirect tricks dead ends."""
    lowered = [e.lower() for e in L._ALLOWED_EXTRACTORS]
    assert "generic" not in lowered and "default" not in lowered


# -- failure classification ---------------------------------------------------

@pytest.mark.parametrize("message,kind", [
    ("Instagram sent an empty media response. Use --cookies", "gated"),
    ("This video is private", "private"),
    ("Unsupported URL: https://x", "unsupported"),
    ("HTTP Error 404: Not Found", "not_found"),
    ("Video unavailable", "not_found"),
    ("HTTP Error 429: Too Many Requests", "network"),
    ("The read operation timed out", "network"),
    ("something entirely novel", "other"),
])
def test_failures_are_classified_for_the_user(message, kind):
    err = L._classified(RuntimeError(message))
    assert err.kind == kind
    # The user-facing text must not leak the platform's raw internals.
    assert "yt-dlp" not in str(err) and "--cookies" not in str(err)


# -- subtitle choice ----------------------------------------------------------

def _track(ext="json3", url="https://yt.example/sub"):
    return {"ext": ext, "url": url}


def test_manual_subtitles_beat_auto_captions():
    ref = L._pick_subtitle({
        "subtitles": {"hi": [_track()]},
        "automatic_captions": {"hi-orig": [_track()]},
    })
    assert ref.lang == "hi"


def test_auto_captions_only_the_orig_track_is_acceptable():
    """Non-orig auto tracks are machine TRANSLATIONS — feeding one to the
    pipeline would hand normalize() a translation of a translation."""
    ref = L._pick_subtitle({
        "automatic_captions": {
            "en": [_track()],          # translation of the Hindi speech
            "ta": [_track()],          # translation
            "hi-orig": [_track()],     # the recognized source speech
        },
    })
    assert ref.lang == "hi-orig"

    assert L._pick_subtitle({
        "automatic_captions": {"en": [_track()], "ta": [_track()]},
    }) is None


def test_no_tracks_means_none_not_error():
    assert L._pick_subtitle({}) is None
    assert L._pick_subtitle({"subtitles": {}, "automatic_captions": {}}) is None


def test_a_track_without_a_usable_format_is_skipped():
    ref = L._pick_subtitle({
        "subtitles": {
            "hi": [{"ext": "ttml", "url": "https://x/unparseable"}],  # no json3/vtt
            "mr": [_track("vtt")],
        },
    })
    assert (ref.lang, ref.ext) == ("mr", "vtt")


# -- caption parsers ----------------------------------------------------------

def test_json3_parsing_flattens_events():
    data = b"""{"events":[
        {"segs":[{"utf8":"5\\u091c\\u0940 "},{"utf8":"\\u0938\\u0947"}]},
        {"segs":[{"utf8":"\\n"}]},
        {"segs":[{"utf8":"\\u0915\\u094b\\u0930\\u094b\\u0928\\u093e"}]}
    ]}"""
    assert L._parse_json3(data) == "5जी से कोरोना"


def test_json3_tolerates_junk():
    assert L._parse_json3(b'{"events": []}') == ""
    assert L._parse_json3(b'{"events": [{}, {"segs": []}]}') == ""


def test_vtt_parsing_strips_cues_and_rolling_duplicates():
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: hi\n\n"
        "00:00:00.000 --> 00:00:02.000\n"
        "<c>5जी से कोरोना</c>\n\n"
        "00:00:02.000 --> 00:00:04.000\n"
        "5जी से कोरोना\n"          # the rolling repeat YouTube actually emits
        "फैलता है\n"
    )
    assert L._parse_vtt(vtt) == "5जी से कोरोना फैलता है"


def test_subtitle_text_returns_none_on_fetch_failure(monkeypatch):
    """A broken caption download must degrade to the audio path (paying),
    never to a failed report."""
    def boom(*a, **kw):
        raise OSError("network down")

    monkeypatch.setattr(L.httpx, "get", boom)
    ref = L.SubtitleRef(lang="hi-orig", url="https://yt.example/sub", ext="json3")
    assert L.subtitle_text(ref) is None
