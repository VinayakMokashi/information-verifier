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
    ("https://www.facebook.com/pibfactcheck/videos/287009708974916/", "www.facebook.com"),
    ("https://facebook.com/reel/12345/", "facebook.com"),
    ("https://m.facebook.com/watch/?v=1", "m.facebook.com"),
    ("https://web.facebook.com/x/videos/1/", "web.facebook.com"),
    ("https://fb.watch/abc123/", "fb.watch"),
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
    "https://facebook.com.evil.com/videos/1",     # FB lookalikes fail the same way
    "https://fb.watch.evil.com/x",
    "https://fbwatch.com/x",
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


def test_facebooks_auto_caption_naming_is_accepted():
    """Facebook names its single auto track '<lang>_FB' (measured: an I&B
    ministry Hindi video carried exactly 'hi_FB'). It is the recognized
    speech, not a translation, so it may stand in for ASR."""
    ref = L._pick_subtitle({"automatic_captions": {"hi_FB": [_track()]}})
    assert ref.lang == "hi_FB"


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


# -- Facebook reels, probed 2026-09-22 -----------------------------------------

def test_a_facebook_post_that_cannot_be_parsed_is_explained():
    """Real reels answered 'Cannot parse data' (removed, restricted or
    login-only) — by share link and by /reel/<id>, on the latest yt-dlp."""
    from app.providers.links import _classified

    err = _classified(Exception(
        "ERROR: [facebook] 925703473004518: Cannot parse data; please report "
        "this issue on https://github.com/yt-dlp/yt-dlp/issues?q= , filling out "
        "the appropriate issue template. Confirm you are on the latest version"))
    assert err.kind == "gated"
    assert "public" in str(err) and "yt-dlp" not in str(err)


def test_the_probe_predicts_exactly_what_the_app_would_do():
    """The probe said "could skip Sarvam" for ANY caption track; the app
    trusts only uploader tracks, YouTube '-orig' and Facebook '_FB' — a
    locale-named track may be a machine translation of the speech."""
    from scripts.link_probe import caption_verdict

    spanish_fb = {"automatic_captions": {
        "es_CL": [{"ext": "vtt", "url": "https://x/es"}],
        "vi_VN": [{"ext": "vtt", "url": "https://x/vi"}]}}
    assert "transcribe the audio" in caption_verdict(spanish_fb)

    hindi_fb = {"automatic_captions": {"hi_FB": [{"ext": "vtt", "url": "https://x/hi"}]}}
    assert "'hi_FB' captions" in caption_verdict(hindi_fb)

    youtube = {"automatic_captions": {"hi-orig": [{"ext": "json3", "url": "https://x"}],
                                      "en": [{"ext": "json3", "url": "https://y"}]}}
    assert "'hi-orig' captions" in caption_verdict(youtube)


# -- Facebook /reel/ and share links, measured 2026-10-15 ----------------------

# The form Facebook's own Share button produces, and where it redirected
# (one HTTP 302, measured live 2026-10-15).
_FB_SHARE = "https://www.facebook.com/share/r/17RQxbYP2j/"
_FB_REEL = ("https://www.facebook.com/reel/848607324236464?rdid=NdXrkNK8Kv9W34Pv"
            "&share_url=https%3A%2F%2Fwww.facebook.com%2Fshare%2Fr%2F17RQxbYP2j%2F")


def _loaded_extractors():
    import yt_dlp

    with yt_dlp.YoutubeDL(L._base_opts()) as ydl:
        return list(ydl._ies.values())


@pytest.mark.parametrize("url", [
    "https://www.instagram.com/reel/DbsVyqLpbRa/",
    "https://www.youtube.com/shorts/QBHKZ36_dlo",
    "https://youtu.be/QBHKZ36_dlo",
    "https://www.facebook.com/pibfactcheck/videos/287009708974916/",
    "https://www.facebook.com/watch/?v=287009708974916",
    "https://www.facebook.com/reel/848607324236464",
    _FB_REEL,
])
def test_every_direct_link_form_reaches_an_extractor_the_app_loads(url):
    """MEASURED 2026-10-15: yt-dlp FULL-matches allowed_extractors, so
    "Facebook" admitted only the extractor named exactly 'facebook' — and
    /reel/<id> belongs to 'facebook:reel'. Every Facebook reel failed in the
    app as "not a video" while link_probe (all extractors) said it worked."""
    assert any(ie.suitable(url) for ie in _loaded_extractors())


def _fake_share_host(routes, seen):
    """A Facebook that answers each URL with (status, Location)."""
    import httpx

    def handler(request):
        seen.append(str(request.url))
        status, location = routes.get(str(request.url), (404, None))
        return httpx.Response(status, headers={"location": location} if location else {})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_share_link_is_expanded_by_one_checked_hop():
    seen = []
    client = _fake_share_host({_FB_SHARE: (302, _FB_REEL)}, seen)
    assert L.expand_share_link(_FB_SHARE, client=client) == _FB_REEL
    assert seen == [_FB_SHARE]          # the reel page itself is yt-dlp's job


@pytest.mark.parametrize("url", [
    "https://www.youtube.com/shorts/QBHKZ36_dlo",
    "https://www.instagram.com/reel/DbsVyqLpbRa/",
    "https://www.facebook.com/reel/848607324236464",
])
def test_a_direct_link_is_never_fetched_for_expansion(url):
    seen = []
    assert L.expand_share_link(url, client=_fake_share_host({}, seen)) == url
    assert seen == []


@pytest.mark.parametrize("target", [
    "https://evil.example/reel/1",
    "http://www.facebook.com/reel/1",              # downgraded to http
    "https://127.0.0.1/reel/1",
    "https://www.facebook.com.evil.com/reel/1",
])
def test_a_share_redirect_off_the_allowlist_is_refused_before_it_is_fetched(target):
    """The hop is taken HERE precisely so each target is host-checked; yt-dlp's
    generic extractor (the only other way) would follow anything."""
    seen = []
    with pytest.raises(L.LinkError) as info:
        L.expand_share_link(_FB_SHARE, client=_fake_share_host({_FB_SHARE: (302, target)}, seen))
    assert info.value.kind == "unsupported"
    assert seen == [_FB_SHARE]


def test_a_relative_redirect_resolves_against_the_share_host():
    client = _fake_share_host({_FB_SHARE: (302, "/reel/848607324236464")}, [])
    assert (L.expand_share_link(_FB_SHARE, client=client)
            == "https://www.facebook.com/reel/848607324236464")


def test_a_share_link_that_does_not_redirect_is_explained():
    with pytest.raises(L.LinkError) as info:
        L.expand_share_link(_FB_SHARE, client=_fake_share_host({_FB_SHARE: (200, None)}, []))
    assert info.value.kind == "gated"


def test_a_share_link_that_lands_on_the_login_wall_says_so():
    client = _fake_share_host(
        {_FB_SHARE: (302, "https://www.facebook.com/login/?next=%2Freel%2F1")}, [])
    with pytest.raises(L.LinkError) as info:
        L.expand_share_link(_FB_SHARE, client=client)
    assert info.value.kind == "gated"


def test_a_redirect_loop_is_cut_off():
    a = "https://www.facebook.com/share/r/AAAA/"
    b = "https://www.facebook.com/share/r/BBBB/"
    seen = []
    with pytest.raises(L.LinkError):
        L.expand_share_link(a, client=_fake_share_host({a: (302, b), b: (302, a)}, seen))
    assert len(seen) <= 3


def test_resolve_hands_yt_dlp_the_expanded_url_and_keeps_it(monkeypatch):
    """The download later runs from LinkInfo.url: a share URL kept there
    would hit the same dead end at download time."""
    import yt_dlp

    asked = []

    class FakeYDL:
        def __init__(self, opts):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            asked.append(url)
            return {"extractor": "facebook", "id": "848607324236464", "title": "t",
                    "formats": [{"url": "x"}], "description": "", "duration": 14.1}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)
    monkeypatch.setattr(L, "_share_client",
                        lambda: _fake_share_host({_FB_SHARE: (302, _FB_REEL)}, []))
    info = L.resolve_link(_FB_SHARE)
    assert asked == [_FB_REEL]
    assert info.url == _FB_REEL


def test_the_probe_reports_what_the_app_itself_would_do(monkeypatch):
    """The probe loads EVERY extractor (it evaluates new platforms), so its own
    resolve cannot predict the app's: it said share links work while the app
    refused them. Its verdict on the APP now comes from the app's resolve."""
    import scripts.link_probe as P

    def refuse(url):
        raise L.LinkError("unsupported", "That link doesn't point at a video "
                                         "this service can read.")

    monkeypatch.setattr(P, "resolve_link", refuse)
    assert "NO" in P.app_verdict(_FB_SHARE) and "unsupported" in P.app_verdict(_FB_SHARE)


def test_the_probe_calls_a_photo_post_what_it_is(monkeypatch):
    """Since 2026-11-18 the app reads a post's pictures; "YES - Instagram
    video" for a carousel of photos would send the operator looking for one."""
    import scripts.link_probe as P

    post = L.LinkInfo(url=_IG_POST, platform="Instagram", video_id="C1", title="",
                      uploader="", duration=None, caption="", has_media=False,
                      subtitle=None, images=("a", "b", "c"), videos_skipped=1)
    monkeypatch.setattr(P, "resolve_link", lambda url: post)
    verdict = P.app_verdict(_IG_POST)
    assert verdict.startswith("YES") and "3 pictures" in verdict
    assert "video" not in verdict.split(":")[0] and "1 video" in verdict


# -- review R2/R3 (2026-10-15): ports, line breaks, unparseable hops ------------

@pytest.mark.parametrize("url", [
    "https://www.facebook.com:1/share/r/17RQxbYP2j/",
    "https://fb.watch:6379/abc/",
    "https://www.youtube.com:8443/watch?v=x",
])
def test_an_explicit_port_other_than_443_is_refused(url):
    """REPRODUCED (review R2): the gate read only the host, so the server
    connected to whatever port the visitor named on Facebook's hosts — and a
    dropped port was a free ~31 s hold. No pinned extractor even claims a
    URL with a port."""
    assert L.allowed_link_host(url) is None


def test_the_standard_port_written_out_is_still_fine():
    assert L.allowed_link_host("https://www.youtube.com:443/watch?v=x") == "www.youtube.com"


@pytest.mark.parametrize("url", [
    "https://www.facebook.com/share/r/17RQxbYP2j/\nKya yeh sach hai?",
    "https://www.facebook.com/share/r/17RQ\txbYP2j/",
    "https://www.youtube.com/wa\rtch?v=x",
    "https://www.youtube.com/watch?v=x y",
])
def test_whitespace_or_a_control_character_inside_a_link_is_refused(url):
    """REPRODUCED (review R3): urlsplit silently drops tab/CR/LF, so the
    gate passed, and httpx then refused the URL with an InvalidURL that
    nothing caught — a 500. Fail closed instead (edge whitespace from a
    paste is still trimmed)."""
    assert L.allowed_link_host(url) is None


@pytest.mark.parametrize("location", [
    "https:evil.example/x",               # no authority
    "https://xn--fdkkl/reel/1",           # no such label shape (punycode-ish junk)
    "https://фейсбук.com/reel/1",         # non-ASCII host
    "javascript:alert(1)",
])
def test_a_hop_nobody_can_parse_is_a_readable_refusal_not_a_crash(location):
    client = _fake_share_host({_FB_SHARE: (302, location)}, [])
    with pytest.raises(L.LinkError):
        L.expand_share_link(_FB_SHARE, client=client)


def test_the_whole_expansion_has_one_deadline(monkeypatch):
    """Per-socket timeouts summed over the hops let one link hold a slot for
    the better part of a minute; the expansion now has one budget."""
    import time

    import httpx

    monkeypatch.setattr(L, "_SHARE_DEADLINE_S", 0.3)
    hops = {"n": 0}

    def slow(request):
        hops["n"] += 1
        time.sleep(0.2)
        return httpx.Response(302, headers={"location": f"/share/r/HOP{hops['n']}/"})

    client = httpx.Client(transport=httpx.MockTransport(slow))
    with pytest.raises(L.LinkError) as info:
        L.expand_share_link(_FB_SHARE, client=client)
    assert info.value.kind == "network"
    assert hops["n"] <= 2


# -- Instagram photo posts and carousels (2026-11-18) -------------------------
# SEEN LIVE: four Instagram links on 17-18 Nov failed "No video formats
# found!" — carousels of pictures — and each person was told only "That link
# could not be read." A single-photo post fails "There is no video in this
# post"; a carousel of videos was refused as "a channel or playlist".
# MEASURED (docs/research/2026-11-18/link-and-image-complaints.md): a photo's
# versions carry no width or height; the size is the URL's `_s<W>x<H>` token,
# and the full-size one has none.

_IG_POST = "https://www.instagram.com/p/BsOGulcndj-/"
_CDN = "instagram.fbom3-2.fna.fbcdn.net"


def _pic(size=None, host=_CDN, **extra):
    stp = f"dst-jpg_e35_s{size}x{size}_tt6" if size else "dst-jpg_e35_tt6"
    return {"url": f"https://{host}/v/t51.2885-15/1_n.jpg?stp={stp}&oh=x", **extra}


def _fake_ydl(monkeypatch, info, seen_opts=None):
    import yt_dlp

    class FakeYDL:
        def __init__(self, opts):
            if seen_opts is not None:
                seen_opts.append(opts)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download):
            return info

    monkeypatch.setattr(yt_dlp, "YoutubeDL", FakeYDL)


def test_a_photo_post_is_its_caption_and_its_largest_picture(monkeypatch):
    _fake_ydl(monkeypatch, {
        "extractor": "Instagram", "id": "BsOGulcndj-", "title": "Post by x",
        "formats": [], "description": "A world record egg",
        "thumbnails": [_pic(150), _pic(480), _pic(), _pic(320)]})
    info = L.resolve_link(_IG_POST)
    assert info.images == (_pic()["url"],)
    assert not info.has_media             # nothing to download or transcribe
    assert info.caption == "A world record egg"
    assert info.video_id == "BsOGulcndj-"


def test_a_carousel_is_its_pictures_in_order_and_says_how_many_videos(monkeypatch):
    other = "scontent-bom1-1.cdninstagram.com"
    _fake_ydl(monkeypatch, {
        "_type": "playlist", "extractor": "Instagram", "id": "C1",
        "description": "Breaking news",
        "entries": [
            {"id": "a", "formats": [], "thumbnails": [_pic(150), _pic()]},
            {"id": "b", "formats": [{"url": "v"}], "thumbnails": [_pic()]},
            {"id": "c", "formats": [], "thumbnails": [_pic(host=other)]},
        ]})
    info = L.resolve_link(_IG_POST)
    assert info.images == (_pic()["url"], _pic(host=other)["url"])
    assert info.videos_skipped == 1
    assert info.video_id == "C1" and info.caption == "Breaking news"
    assert not info.has_media


def test_a_carousel_of_only_videos_is_refused_with_what_works_instead(monkeypatch):
    _fake_ydl(monkeypatch, {
        "_type": "playlist", "extractor": "Instagram", "id": "V",
        "entries": [{"id": "a", "formats": [{"url": "v"}], "thumbnails": [_pic()]}]})
    with pytest.raises(L.LinkError) as err:
        L.resolve_link(_IG_POST)
    assert err.value.kind == "unsupported"
    assert "screen recording" in str(err.value)


def test_a_playlist_anywhere_else_is_still_refused(monkeypatch):
    _fake_ydl(monkeypatch, {"_type": "playlist", "extractor": "youtube:tab",
                            "id": "PL", "entries": [{"id": "a", "formats": []}]})
    with pytest.raises(L.LinkError) as err:
        L.resolve_link("https://www.youtube.com/watch?v=x&list=PL")
    assert "playlist" in str(err.value)


def test_only_instagram_is_asked_for_a_post_without_video(monkeypatch):
    """YouTube and Facebook keep exactly their old behaviour: a video they
    cannot serve still fails there, rather than turning into a check of its
    description."""
    seen = []
    _fake_ydl(monkeypatch, {"extractor": "youtube", "id": "x", "formats": [{"url": "v"}]},
              seen)
    L.resolve_link("https://www.youtube.com/shorts/x")
    L.resolve_link("https://www.instagram.com/reel/x/")
    assert not seen[0].get("ignore_no_formats_error")
    assert seen[1]["ignore_no_formats_error"] is True


def test_a_post_with_no_picture_it_may_fetch_has_none(monkeypatch):
    _fake_ydl(monkeypatch, {"extractor": "Instagram", "id": "p", "formats": [],
                            "description": "only words",
                            "thumbnails": [_pic(host="evil.example")]})
    info = L.resolve_link(_IG_POST)
    assert info.images == () and info.caption == "only words"


def test_declared_sizes_beat_the_order_they_came_in():
    big = _pic(150, width=1080, height=1350)    # its URL token says small
    small = _pic(width=320, height=400)
    assert L._best_image({"thumbnails": [big, small]}) == big["url"]


@pytest.mark.parametrize("url", [
    "http://instagram.fbom3-2.fna.fbcdn.net/v/1.jpg",          # not https
    "https://evil.example/v/1.jpg",
    "https://fbcdn.net.evil.example/v/1.jpg",                  # lookalike
    "https://cdninstagram.com.evil.example/v/1.jpg",
    "https://fbcdn.net/v/1.jpg",                               # no subdomain
    "https://instagram.fbom3-2.fna.fbcdn.net:8443/v/1.jpg",    # another port
    "https://u@instagram.fbom3-2.fna.fbcdn.net/v/1.jpg",       # userinfo
    "https://instagram.fbom3-2.fna.fbcdn.net/v/1.jpg\n",       # a line break
])
def test_a_picture_is_fetched_only_from_instagrams_image_servers(url):
    """This decides what the SERVER connects to, so it gets the same
    paranoia as allowed_link_host: the URL came from Instagram's reply, but
    nothing about it is trusted."""
    assert not L.image_host_ok(url)
    with pytest.raises(L.LinkError):
        L.fetch_post_image(url, max_bytes=1000)   # refused before any request
    picked = L._best_image({"thumbnails": [{"url": url, "width": 9999, "height": 9999},
                                           _pic(150)]})
    assert picked == _pic(150)["url"]


def _image_server(status=200, ctype="image/jpeg", body=b"\xff\xd8jpeg", seen=None,
                  headers=None):
    import httpx

    def handler(request):
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, content=body,
                              headers={"content-type": ctype, **(headers or {})})

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_a_picture_is_fetched_whole():
    data, ctype = L.fetch_post_image(_pic()["url"], max_bytes=1000,
                                     client=_image_server())
    assert data == b"\xff\xd8jpeg" and ctype == "image/jpeg"


@pytest.mark.parametrize("server,kind", [
    (dict(status=302, headers={"location": "https://evil.example/"}), "other"),
    (dict(ctype="text/html"), "other"),
    (dict(ctype="image/heic"), "other"),      # the model cannot read it
    (dict(body=b"x" * 2000), "too_large"),
    (dict(status=404), "not_found"),
])
def test_a_picture_that_is_not_a_small_image_is_refused(server, kind):
    with pytest.raises(L.LinkError) as err:
        L.fetch_post_image(_pic()["url"], max_bytes=1000, client=_image_server(**server))
    assert err.value.kind == kind


@pytest.mark.parametrize("message", [
    "ERROR: [Instagram] BsOGulcndj-: There is no video in this post",
    "ERROR: [facebook] 1: No video formats found!; please report this issue",
])
def test_a_post_with_no_video_says_so_and_what_works_instead(message):
    err = L._classified(RuntimeError(message))
    assert err.kind == "unsupported"
    assert "screenshot" in str(err)


def test_the_catch_all_failure_still_says_what_to_do_instead():
    assert "screenshot" in str(L._classified(RuntimeError("something entirely novel")))

