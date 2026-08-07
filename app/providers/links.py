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
"""
import json
import os
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

# Exact hosts, not suffix matching: the endpoint fetches whatever this allows,
# so a lookalike (youtube.com.evil.com) must fail. m.instagram.com and short
# youtu.be links are how phones actually share these.
_ALLOWED_HOSTS = {
    "instagram.com", "www.instagram.com", "m.instagram.com",
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    # Facebook measured 2026-07-28: three public /videos/ URLs (PIB, I&B and
    # Defence ministry pages) all resolved anonymously, WITH duration — so
    # unlike Instagram, an over-cap FB video is rejected before any download.
    "facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com",
    "fb.watch",
}

# yt-dlp extractor allowlist. Names are matched as regexes anchored at the
# start, so "Youtube" also admits YoutubeTab etc. (harmless — still YouTube,
# and playlist results are rejected after resolve). What matters is that
# "generic" is NOT here: without it yt-dlp will not fall back to fetching
# arbitrary pages, which is the SSRF path this list exists to close.
_ALLOWED_EXTRACTORS = ["Instagram", "Youtube", "Facebook"]

_RESOLVE_TIMEOUT_S = 30      # per socket op inside yt-dlp
_DOWNLOAD_WALL_S = 180.0     # a trickling stream must not pin a worker
_SUBTITLE_TIMEOUT_S = 20
_SUBTITLE_MAX_BYTES = 5_000_000   # caption tracks are ~100 KB; 5 MB is absurd


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


class _Silent:
    """yt-dlp writes to stderr regardless of quiet; failures are OUR output.

    (scripts/link_probe.py carries its own copy on purpose — scripts import
    app, never the reverse, and the probe must stay standalone.)
    """

    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


def allowed_link_host(url: str) -> str | None:
    """The host this URL really points at, or None. Fails closed.

    Same discipline as trusted_sources.trusted_domain_of, for the same
    reason: browsers and Python can disagree about where a host ends
    (`https://evil.com\\@youtube.com/` reads as youtube.com to a naive
    parser), and here the stakes are higher — this check decides what the
    SERVER will fetch, not what a verdict may cite.
    """
    if not isinstance(url, str) or len(url) > 2048:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme != "https":         # these platforms are https-only
        return None
    try:
        if parts.username is not None or parts.password is not None:
            return None
        host = (parts.hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    if not host or not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    return host if host in _ALLOWED_HOSTS else None


def _classified(exc: Exception) -> LinkError:
    """Name the failure; 'it did not work' is not something a user can act on.

    The raw platform message is logged server-side only — the audit found
    error internals leaking to users elsewhere, and this module must not add
    another instance.
    """
    m = str(exc).lower()
    print(f"[links] resolve/fetch failed: {' '.join(str(exc).split())[:300]}")
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
    return LinkError("other", "That link could not be read.")


def _base_opts() -> dict:
    return {
        "quiet": True,
        "no_warnings": True,
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
        raise LinkError(
            "unsupported",
            "Only public Instagram and YouTube links can be checked (https).",
        )
    try:
        with yt_dlp.YoutubeDL(_base_opts()) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 — classified for the user
        raise _classified(exc) from exc

    if not isinstance(info, dict) or info.get("entries") is not None \
            or info.get("_type") == "playlist":
        raise LinkError(
            "unsupported",
            "That looks like a channel or playlist — send one video's link.",
        )
    if info.get("is_live"):
        raise LinkError(
            "unsupported",
            "Live streams can't be checked — send a finished video.",
        )

    return LinkInfo(
        url=url,
        platform=info.get("extractor") or "unknown",
        video_id=str(info.get("id") or ""),
        title=str(info.get("title") or ""),
        uploader=str(info.get("uploader") or info.get("channel") or ""),
        duration=info.get("duration"),
        caption=str(info.get("description") or ""),
        has_media=bool(info.get("formats")),
        subtitle=_pick_subtitle(info),
    )


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
              f"{type(exc).__name__}: {exc}")
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
    import tempfile

    import yt_dlp

    if allowed_link_host(url) is None:   # the route checks too; fail closed here anyway
        raise LinkError("unsupported", "Only Instagram and YouTube links can be fetched.")

    state = {"too_large": False, "too_slow": False}
    deadline = time.monotonic() + _DOWNLOAD_WALL_S

    def guard(progress: dict) -> None:
        if (progress.get("downloaded_bytes") or 0) > max_bytes:
            state["too_large"] = True
            raise yt_dlp.utils.DownloadError("byte cap exceeded")
        if time.monotonic() > deadline:
            state["too_slow"] = True
            raise yt_dlp.utils.DownloadError("download deadline exceeded")

    with tempfile.TemporaryDirectory() as tmp:
        opts = {
            **_base_opts(),
            # Audio-only when the platform offers it (Instagram and YouTube
            # both do — measured); whole file otherwise. ffmpeg strips video
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
