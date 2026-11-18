"""Reel / Shorts link ingestion: resolve a URL, read its text, fetch its audio.

Every decision here traces to a measurement (PROJECT_PLAN §0a/§6, 2026-07-28,
scripts/link_probe.py on real URLs Vinayak supplied):

- Instagram Reels and YouTube (all three URL forms) resolve anonymously.
- Instagram advertises NO duration and NO filesize, so the pre-spend caps
  cannot come from metadata. The order is what preserves invariant 5: the
  download is byte- and wall-clock-capped as it streams (free — bandwidth,
  not API), then ffprobe reads the real duration (normalize_to_wav already
  refuses before decoding), and only then is the first paid second of ASR
  bought.
- YouTube Hindi videos carry auto-captions ('hi-orig') — the spoken claim for
  ₹0 of ASR. Instagram has no subtitle tracks at all, so ASR is the fallback.
- A post's caption often carries the claim outright (measured: 599 chars with
  a full quoted assertion) and is often pure promo; it is a supplement the
  extract stage can discard, never a replacement.

- Facebook (added after its own probe, same day): three public government
  /videos/ URLs resolved anonymously, WITH duration advertised, and its auto
  captions are named '<lang>_FB' — one track, the recognized speech.

SSRF: this module deliberately fetches remote URLs — the very door §7 records
closing for uploads (ffmpeg's protocol whitelist). Three fences, each
independent: `allowed_link_host` fails closed with the same parser discipline
as trusted_sources.trusted_domain_of; yt-dlp is pinned to the Instagram,
YouTube and Facebook extractors so its generic extractor (which would fetch
ANY url) can never run; and noplaylist keeps one link meaning one video.
Facebook share links, which only generic could follow, are expanded by
`expand_share_link` instead: one redirect at a time, each target through
`allowed_link_host` before it is requested.
"""
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from app.hosts import strict_host

# Exact hosts, not suffix matching: the endpoint fetches whatever this allows,
# so a lookalike (youtube.com.evil.com) must fail. m.instagram.com and short
# youtu.be links are how phones actually share these.
ALLOWED_HOSTS = {
    "instagram.com", "www.instagram.com", "m.instagram.com",
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    # Facebook measured 2026-07-28: three public /videos/ URLs (PIB, I&B and
    # Defence ministry pages) all resolved anonymously, WITH duration — so
    # unlike Instagram, an over-cap FB video is rejected before any download.
    "facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com",
    "fb.watch",
}
_ALLOWED_HOSTS = ALLOWED_HOSTS   # historical private name, kept for callers

# The one sentence users are told about which links work. Derived from the
# platform list, because it had already drifted: Facebook was added to the
# hosts, the extractors and the page regex, but all three user-facing
# messages still said "Instagram and YouTube" — so someone whose valid
# Facebook link failed for an unrelated reason was told the platform is not
# supported at all.
SUPPORTED_PLATFORMS = ("Instagram", "YouTube", "Facebook")
SUPPORTED_LINKS_MSG = (
    "Only public "
    + ", ".join(SUPPORTED_PLATFORMS[:-1])
    + f" and {SUPPORTED_PLATFORMS[-1]} links can be checked (https)."
)

# yt-dlp extractor allowlist. yt-dlp FULL-matches each name, case-insensitively,
# against every extractor's IE_NAME — so "Facebook" admits exactly 'facebook',
# never 'facebook:reel'. This comment used to say "anchored at the start", and
# on that belief every Facebook /reel/<id> link failed in the app as "not a
# video" (MEASURED 2026-10-15) while link_probe, which loads every extractor,
# said it worked. What matters most is that "generic" is NOT here: without it
# yt-dlp will not fall back to fetching arbitrary pages, which is the SSRF path
# this list exists to close — share links are expanded by expand_share_link
# instead, one host-checked hop at a time.
_ALLOWED_EXTRACTORS = ["Instagram", "Youtube", "Facebook", "facebook:reel"]

# Facebook's Share button produces /share/r/<code>/ (and fb.watch/<code>)
# links that carry no video id: Facebook answers them with one HTTP redirect
# to the canonical /reel/<id> (MEASURED 2026-10-15). No pinned extractor
# claims them; only yt-dlp's generic extractor would follow that redirect.
_FACEBOOK_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com",
                   "web.facebook.com"}
_REDIRECT_STATUSES = {301, 302, 303, 307, 308}
_SHARE_HOPS = 3
# ONE budget for the whole expansion, not one per socket operation per hop
# (review R2: summed, they let one link hold a slot for most of a minute).
_SHARE_DEADLINE_S = 10.0

_RESOLVE_TIMEOUT_S = 30      # per socket op inside yt-dlp
_DOWNLOAD_WALL_S = 180.0     # a trickling stream must not pin a worker
_SUBTITLE_TIMEOUT_S = 20
_SUBTITLE_MAX_BYTES = 5_000_000   # caption tracks are ~100 KB; 5 MB is absurd

# A photo post, or a carousel of pictures, has no video at all. yt-dlp then
# fails ("There is no video in this post", "No video formats found!") unless
# told not to — and four people's Instagram links failed that way on 17-18 Nov
# 2026, each told only "That link could not be read." Asked only of Instagram:
# YouTube and Facebook keep their old behaviour exactly.
_INSTAGRAM_HOSTS = {"instagram.com", "www.instagram.com", "m.instagram.com"}
# Where Instagram serves a post's pictures. MEASURED 2026-11-18: every version
# of a photo and every carousel cover was on instagram.f<pop>.fna.fbcdn.net;
# scontent-*.cdninstagram.com is its other name. The URL comes from
# Instagram's reply, but the server connects to it, so it is fenced like
# allowed_link_host: https, port 443, on a dot boundary of these suffixes.
_IMAGE_HOST_SUFFIXES = (".cdninstagram.com", ".fbcdn.net")
# What the vision model reads (the docs' list, 2026-11-18). HEIC is not.
_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_IMAGE_DEADLINE_S = 20.0
# MEASURED 2026-11-18: a photo's versions carry no width or height. The size
# is in the URL's stp parameter (dst-jpg_e35_s480x480_tt6); the full-size one
# has no size token at all.
_SIZE_TOKEN = re.compile(r"_s(\d{2,5})x(\d{2,5})")
_UNSIZED = 10 ** 8           # no size token: the original, the largest there is


class LinkError(Exception):
    """A link could not be resolved or fetched. `str(exc)` is user-facing.

    `kind` is machine-facing: gated / private / not_found / network /
    unsupported / other. The route maps kinds to HTTP statuses.
    """

    def __init__(self, kind: str, message: str):
        self.kind = kind
        super().__init__(message)


class LinkTooLarge(LinkError):
    """The stream crossed the byte cap mid-download and was aborted."""

    def __init__(self, limit_bytes: int):
        super().__init__(
            "too_large",
            f"That video is larger than this service handles "
            f"({limit_bytes // (1024 * 1024)} MB). Try a shorter clip.",
        )


@dataclass(frozen=True)
class SubtitleRef:
    """One fetchable caption track, chosen at resolve time."""

    lang: str
    url: str
    ext: str   # "json3" or "vtt"


@dataclass(frozen=True)
class LinkInfo:
    """What resolve_link() learned for free, before any download."""

    url: str
    platform: str
    video_id: str
    title: str
    uploader: str
    duration: float | None    # None on Instagram — measured, not hypothetical
    caption: str              # the post's own text; often carries the claim
    has_media: bool
    subtitle: SubtitleRef | None
    # A photo post's pictures, largest version each, in the post's order:
    # read by the vision model instead of a transcription. Every one has
    # passed image_host_ok.
    images: tuple[str, ...] = ()
    videos_skipped: int = 0   # a carousel's videos: not listened to


_WARNED: set[str] = set()


class _Silent:
    """yt-dlp writes to stderr regardless of quiet; failures are OUR output.

    scripts/link_probe.py imports this rather than copying it: the probe's
    job is to predict what /verify/link does, and every copied constant
    between the two has drifted at least once.

    Warnings are the exception: each distinct one is logged ONCE per process,
    scrubbed (log_safe). They were dropped (audit-ops OPS-25), and the day
    YouTube stops working without a JavaScript runtime — yt-dlp already warns
    that the no-runtime mode is deprecated — nothing would have said why.
    """

    def debug(self, m): pass
    def info(self, m): pass
    def error(self, m): pass

    def warning(self, m):
        line = log_safe(m)
        if line not in _WARNED and len(_WARNED) < 64:
            _WARNED.add(line)
            print(f"[links] yt-dlp warning: {line}")


def allowed_link_host(url: str) -> str | None:
    """The host this URL really points at, or None. Fails closed.

    Here the stakes are higher than for a citation: this decides what the
    SERVER will fetch. The host is read by the one shared parser
    (app/hosts.py, also used by trusted_domain_of) — the two used to parse
    separately and had already drifted — and must then be an EXACT allowed
    host: no suffix matching, so youtube.com.evil.com fails.
    """
    if not isinstance(url, str):
        return None
    # Inside the link (a paste's edges are trimmed by strict_host): urlsplit
    # silently DROPS tab/CR/LF, so "link\nquestion" passed this gate and then
    # crashed httpx — a 500 (REPRODUCED, review R3). Fail closed.
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url.strip()):
        return None
    host = strict_host(url, schemes=("https",))   # these platforms are https-only
    if host not in ALLOWED_HOSTS:
        return None
    # The host alone is not where the server connects: a visitor-chosen port
    # made it open connections anywhere on Facebook's hosts, and a dropped
    # port was a free ~31 s hold (REPRODUCED, review R2).
    try:
        if urlsplit(url.strip()).port not in (None, 443):
            return None
    except ValueError:
        return None
    return host


_MSG_NOT_OPENABLE = (
    "That post couldn't be opened — it may have been removed, or be visible "
    "only to people who are logged in. Only public posts work."
)
# Every dead end says what to do instead: "That link could not be read." on
# its own was the whole answer four people got for a photo post.
_MSG_UNREADABLE = ("That link could not be read. Send a screenshot or a screen "
                   "recording of the post instead.")
_MSG_NO_VIDEO = ("That post has no video this service can read. For a post of "
                 "pictures, send a screenshot instead.")
_MSG_VIDEO_CAROUSEL = (
    "That post is a set of videos, and only a single video can be checked from "
    "a link so far. Send a screen recording of the one you mean instead.")


def _is_share_link(url: str) -> bool:
    """A Facebook share link: no video id of its own, only a redirect."""
    host = allowed_link_host(url)
    if host == "fb.watch":
        return True
    if host in _FACEBOOK_HOSTS:
        return urlsplit(url.strip()).path.startswith("/share/")
    return False


def _share_client() -> httpx.Client:
    """httpx never follows a redirect itself here: every hop is host-checked
    by expand_share_link before it is taken. Its plain default headers got
    the redirect (measured); a made-up browser User-Agent got a 400."""
    return httpx.Client(timeout=_SHARE_DEADLINE_S, follow_redirects=False)


def expand_share_link(url: str, client: httpx.Client | None = None) -> str:
    """A share link -> the canonical URL it redirects to. Anything else is
    returned untouched, without a request. Raises LinkError.

    One hop at a time, each target through allowed_link_host BEFORE it is
    requested: this is the redirect yt-dlp's generic extractor would have
    followed blindly, and keeping generic out is this module's SSRF fence.
    """
    url = url.strip()
    if not _is_share_link(url):
        return url
    own = client is None
    client = client or _share_client()
    deadline = time.monotonic() + _SHARE_DEADLINE_S
    try:
        for _ in range(_SHARE_HOPS):
            left = deadline - time.monotonic()
            if left <= 0:
                raise LinkError("network", "The platform could not be reached "
                                           "right now. Try again in a minute.")
            try:
                resp = client.get(url, timeout=left)
            except Exception as exc:  # noqa: BLE001 — httpx.InvalidURL is not an HTTPError
                raise _classified(exc) from exc
            location = resp.headers.get("location")
            if resp.status_code not in _REDIRECT_STATUSES or not location:
                raise LinkError("gated", _MSG_NOT_OPENABLE)
            try:
                target = str(httpx.URL(url).join(location))
            except Exception as exc:  # noqa: BLE001 — a Location nobody can parse
                raise LinkError("other", _MSG_UNREADABLE) from exc
            if allowed_link_host(target) is None:
                raise LinkError("unsupported", SUPPORTED_LINKS_MSG)
            if urlsplit(target).path.startswith("/login"):
                raise LinkError("gated", _MSG_NOT_OPENABLE)
            if not _is_share_link(target):
                return target
            url = target
        raise LinkError("other", _MSG_UNREADABLE)
    finally:
        if own:
            client.close()


_ANY_URL = re.compile(r"\w+://\S+")
# yt-dlp names the post right after the extractor: "[Instagram] ABCdef123: ..."
_YTDLP_POST = re.compile(r"(\[[\w:]+\]) [\w-]+:")


def log_safe(text, limit: int = 300) -> str:
    """A platform's error, fit for a log line: what went wrong, without the
    URL or the post id — which say exactly which reel someone checked
    (audit-ops OPS-11; on a host, logs outlive the 30-day promise)."""
    text = _ANY_URL.sub("<url>", " ".join(str(text).split()))
    return _YTDLP_POST.sub(r"\1 <post>:", text)[:limit]


def _classified(exc: Exception) -> LinkError:
    """Name the failure; 'it did not work' is not something a user can act on.

    The raw platform message is logged server-side only — the audit found
    error internals leaking to users elsewhere, and this module must not add
    another instance.
    """
    m = str(exc).lower()
    print(f"[links] resolve/fetch failed: {log_safe(exc)}")
    if isinstance(exc, LinkError):
        return exc
    if "empty media response" in m or "cookies" in m or "login" in m or "logged-in" in m:
        return LinkError(
            "gated",
            "That post needs a login to view, so it can't be checked. "
            "Only public posts work.",
        )
    if "private" in m:
        return LinkError("private", "That post is private, so it can't be checked.")
    if "cannot parse data" in m:
        # MEASURED 2026-09-22 on real Facebook reels: the extractor's reply
        # when a post is removed, restricted, or shown only to logged-in
        # users — even on the latest yt-dlp, and whether reached by its
        # share link or its /reel/<id> address. Other public reels resolved.
        return LinkError("gated", _MSG_NOT_OPENABLE)
    if "no video in this post" in m or "no video formats found" in m:
        # yt-dlp's words for a post of pictures. Instagram's are read now
        # (resolve_link); this is what is left: another platform's photo post.
        return LinkError("unsupported", _MSG_NO_VIDEO)
    if "unsupported url" in m:
        return LinkError(
            "unsupported",
            "That link doesn't point at a video this service can read.",
        )
    if ("unavailable" in m or "not found" in m or "404" in m
            or "removed" in m or "does not exist" in m):
        return LinkError(
            "not_found",
            "No public post was found at that link — check the URL.",
        )
    if "429" in m or "rate" in m:
        return LinkError(
            "network",
            "The platform is rate-limiting this server. Try again in a few minutes.",
        )
    if "timed out" in m or "timeout" in m or "connection" in m or "network" in m:
        return LinkError(
            "network",
            "The platform could not be reached right now. Try again in a minute.",
        )
    return LinkError("other", _MSG_UNREADABLE)


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": False,       # let them reach _Silent.warning, once each
        "noprogress": True,
        "socket_timeout": _RESOLVE_TIMEOUT_S,
        "noplaylist": True,
        "allowed_extractors": list(_ALLOWED_EXTRACTORS),
        "logger": _Silent(),
    }


# Parseable caption formats, best first. json3 is preferred because YouTube's
# rolling VTT repeats most lines twice; json3 events carry each line once.
_SUB_EXTS = ("json3", "vtt")


def _pick_subtitle(info: dict) -> SubtitleRef | None:
    """Choose one caption track: any manual track, else an auto '-orig' one.

    Auto tracks WITHOUT '-orig' are machine TRANSLATIONS of the original —
    feeding one to the pipeline would hand normalize() a translation of a
    translation. '-orig' is the recognized source speech, which is exactly
    the ASR output we would otherwise pay Sarvam for.
    """
    def usable(tracks: list[dict]) -> tuple[str, str] | None:
        by_ext = {t.get("ext"): t.get("url") for t in tracks or [] if t.get("url")}
        for ext in _SUB_EXTS:
            if by_ext.get(ext):
                return ext, by_ext[ext]
        return None

    manual = info.get("subtitles") or {}
    for lang in sorted(manual):
        found = usable(manual[lang])
        if found:
            return SubtitleRef(lang=lang, url=found[1], ext=found[0])
    autos = info.get("automatic_captions") or {}
    for lang in sorted(autos):
        # YouTube marks the recognized source speech '-orig' (everything else
        # is a machine TRANSLATION). Facebook names its single auto track
        # '<lang>_FB' and does not serve translated auto tracks — measured on
        # a Hindi I&B ministry video carrying exactly one track, 'hi_FB'.
        if lang.endswith("-orig") or lang.endswith("_FB"):
            found = usable(autos[lang])
            if found:
                return SubtitleRef(lang=lang, url=found[1], ext=found[0])
    return None


def resolve_link(url: str) -> LinkInfo:
    """Metadata only — free, no download, no paid call. Raises LinkError."""
    import yt_dlp  # heavy import (~1 s); loaded only when a link is actually used

    if allowed_link_host(url) is None:
        raise LinkError("unsupported", SUPPORTED_LINKS_MSG)
    # Before yt-dlp, and kept: the download later starts from LinkInfo.url,
    # and a share URL there would meet the same dead end.
    url = expand_share_link(url)
    instagram = allowed_link_host(url) in _INSTAGRAM_HOSTS
    opts = _base_opts()
    if instagram:
        opts["ignore_no_formats_error"] = True   # a post of pictures is a post
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 — classified for the user
        raise _classified(exc) from exc

    playlist = isinstance(info, dict) and (info.get("entries") is not None
                                           or info.get("_type") == "playlist")
    if playlist and instagram:
        return _carousel(url, info)
    if not isinstance(info, dict) or playlist:
        raise LinkError(
            "unsupported",
            "That looks like a channel or playlist — send one video's link.",
        )
    if info.get("is_live"):
        raise LinkError(
            "unsupported",
            "Live streams can't be checked — send a finished video.",
        )

    has_media = bool(info.get("formats"))
    picture = _best_image(info) if instagram and not has_media else None
    return LinkInfo(
        url=url,
        platform=info.get("extractor") or "unknown",
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        duration=info.get("duration"),
        caption=str(info.get("description") or ""),
        has_media=has_media,
        subtitle=_pick_subtitle(info),
        images=(picture,) if picture else (),
    )


def _carousel(url: str, info: dict) -> LinkInfo:
    """An Instagram post of several pictures (or videos): yt-dlp's playlist.

    Its pictures are read; its videos are not listened to, and the reader is
    told so (gather_link_text). Downloading one video out of a carousel is a
    different job from a reel's, so a carousel of ONLY videos is refused here,
    for free, with what works instead.
    """
    items = [e for e in list(info.get("entries") or []) if isinstance(e, dict)]
    pictures = [e for e in items if not e.get("formats")]
    if not pictures:
        raise LinkError("unsupported", _MSG_VIDEO_CAROUSEL)
    return LinkInfo(
        url=url,
        platform=info.get("extractor") or "Instagram",
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        duration=None,
        caption=str(info.get("description") or ""),
        has_media=False,
        subtitle=None,
        images=tuple(p for p in map(_best_image, pictures) if p),
        videos_skipped=len(items) - len(pictures),
    )


def image_host_ok(url: str) -> bool:
    """May the server fetch this picture? Only from Instagram's image
    servers, over https, on port 443. Fails closed, like allowed_link_host."""
    if not isinstance(url, str):
        return False
    if any(ch.isspace() or ord(ch) < 0x20 or ord(ch) == 0x7F for ch in url):
        return False
    host = strict_host(url, schemes=("https",))
    if host is None or not host.endswith(_IMAGE_HOST_SUFFIXES):
        return False
    try:
        return urlsplit(url).port in (None, 443)
    except ValueError:
        return False


def _best_image(entry: dict) -> str | None:
    """The largest version of a post's picture that the server may fetch.

    By declared size when there is one, else by the size token in the URL
    (none means the original). Not yt-dlp's own pick: with no sizes it is
    last only because the URLs happen to sort that way (measured).
    """
    thumbs = list(entry.get("thumbnails") or [])
    if not thumbs and entry.get("thumbnail"):
        thumbs = [{"url": entry["thumbnail"]}]
    best, best_area, refused = None, -1, None
    for thumb in thumbs:
        url = thumb.get("url") if isinstance(thumb, dict) else None
        if not isinstance(url, str) or not image_host_ok(url):
            refused = refused or (strict_host(url) if isinstance(url, str) else None)
            continue
        width, height = thumb.get("width"), thumb.get("height")
        if isinstance(width, int) and isinstance(height, int):
            area = width * height
        else:
            token = _SIZE_TOKEN.search(urlsplit(url).query)
            area = int(token[1]) * int(token[2]) if token else _UNSIZED
        if area > best_area:
            best, best_area = url, area
    if best is None and refused:
        # The day Instagram serves pictures from a new domain, its posts are
        # checked by their captions alone; this line says why. A host only.
        print(f"[links] a post's picture is on a server outside the fence: {refused}")
    return best


def fetch_post_image(url: str, max_bytes: int,
                     client: httpx.Client | None = None) -> tuple[bytes, str]:
    """One picture of a post -> (bytes, media type). Raises LinkError.

    Fenced before any request (image_host_ok), never redirected, and capped in
    bytes and in time as it streams — the same discipline as the audio
    download, for a file the vision model is then paid to read.
    """
    if not image_host_ok(url):
        raise LinkError("unsupported", _MSG_UNREADABLE)
    own = client is None
    client = client or httpx.Client(timeout=_IMAGE_DEADLINE_S, follow_redirects=False)
    deadline = time.monotonic() + _IMAGE_DEADLINE_S
    try:
        with client.stream("GET", url) as resp:
            if resp.status_code in (404, 410):
                raise LinkError("not_found", "A picture in that post is gone.")
            if resp.status_code != 200:
                raise LinkError("other", "A picture in that post could not be fetched.")
            ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
            if ctype not in _IMAGE_TYPES:
                raise LinkError("other", "A picture in that post is in a format "
                                         "this service cannot read.")
            data = bytearray()
            for chunk in resp.iter_bytes():
                data.extend(chunk)
                if len(data) > max_bytes:
                    raise LinkError("too_large", "A picture in that post is too large.")
                if time.monotonic() > deadline:
                    raise LinkError("network", "Fetching that post's pictures took "
                                               "too long. Try again in a minute.")
        return bytes(data), ctype
    except LinkError:
        raise
    except Exception as exc:  # noqa: BLE001 — httpx.InvalidURL is not an HTTPError
        raise _classified(exc) from exc
    finally:
        if own:
            client.close()


def _parse_json3(data: bytes) -> str:
    events = json.loads(data.decode("utf-8", errors="replace")).get("events") or []
    lines = []
    for event in events:
        text = "".join(s.get("utf8", "") for s in (event.get("segs") or []))
        text = " ".join(text.split())
        if text:
            lines.append(text)
    return " ".join(lines)


def _parse_vtt(text: str) -> str:
    """Fallback parser. YouTube's rolling VTT repeats lines as they scroll,
    so consecutive duplicates are collapsed."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"<[^>]+>", "", raw).strip()   # strip cue tags like <c>
        if not line or "-->" in line or line == "WEBVTT":
            continue
        if line.startswith(("Kind:", "Language:", "NOTE", "STYLE", "REGION")):
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return " ".join(lines)


def subtitle_text(ref: SubtitleRef) -> str | None:
    """Fetch and flatten one caption track. None means 'fall back to ASR' —
    a broken subtitle download must degrade to paying, never to failing."""
    try:
        resp = httpx.get(ref.url, timeout=_SUBTITLE_TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        if len(resp.content) > _SUBTITLE_MAX_BYTES:
            return None
        text = (_parse_json3(resp.content) if ref.ext == "json3"
                else _parse_vtt(resp.text))
        text = " ".join(text.split())
        return text or None
    except Exception as exc:  # noqa: BLE001 — degrade to the audio path
        print(f"[links] subtitle fetch failed ({ref.lang}/{ref.ext}): "
              f"{type(exc).__name__}: {log_safe(exc)}")
        return None


def download_link_audio(url: str, max_bytes: int) -> tuple[bytes, str]:
    """Fetch the smallest audio stream, capped AS IT STREAMS -> (bytes, ext).

    Instagram advertises no filesize, so the cap cannot be checked up front;
    a progress hook aborts the moment the counter crosses it, and a
    wall-clock deadline in the same hook bounds a trickling stream (data
    that flows too slowly for the socket timeout to fire). Belt and braces:
    the finished file is measured again, because fragmented (DASH) downloads
    report progress per-fragment and could under-count.
    """
    import yt_dlp

    from app.store import scratch     # not %TEMP%: startup empties it (S5-17)

    if allowed_link_host(url) is None:   # the route checks too; fail closed here anyway
        raise LinkError("unsupported", SUPPORTED_LINKS_MSG)

    state = {"too_large": False, "too_slow": False}
    deadline = time.monotonic() + _DOWNLOAD_WALL_S

    def guard(progress: dict) -> None:
        if (progress.get("downloaded_bytes") or 0) > max_bytes:
            state["too_large"] = True
            raise yt_dlp.utils.DownloadError("byte cap exceeded")
        if time.monotonic() > deadline:
            state["too_slow"] = True
            raise yt_dlp.utils.DownloadError("download deadline exceeded")

    with scratch.workdir() as tmp:
        opts = {
            **_base_opts(),
            # Audio-only when the platform offers it (all three do —
            # measured); whole file otherwise. ffmpeg strips video
            # later either way.
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmp, "media.%(ext)s"),
            "progress_hooks": [guard],
            "max_filesize": max_bytes,   # advertised-size fast path, when known
            "retries": 1,
            "fragment_retries": 1,
        }
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])
        except Exception as exc:  # noqa: BLE001 — classified below
            if state["too_large"]:
                raise LinkTooLarge(max_bytes) from exc
            if state["too_slow"]:
                raise LinkError(
                    "network",
                    "Fetching that video took too long. Try again in a minute.",
                ) from exc
            raise _classified(exc) from exc

        files = [n for n in os.listdir(tmp) if n.startswith("media.")]
        if not files:
            raise LinkError("other", "The platform returned no media for that link.")
        path = os.path.join(tmp, files[0])
        if os.path.getsize(path) > max_bytes:
            raise LinkTooLarge(max_bytes)
        with open(path, "rb") as f:
            data = f.read()
        return data, os.path.splitext(files[0])[1]
