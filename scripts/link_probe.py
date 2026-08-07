"""FREE probe: what can we actually get from a Reel / Shorts link? Costs $0.

Answers the questions that decide how /verify/link should be built, BEFORE
any of it is built (same idea as factcheck_probe.py):

  1. Does the URL resolve at all from this machine? YouTube Shorts is expected
     to; Instagram Reels usually want login cookies and Instagram blocks
     aggressively. That is a measurement, not an assumption.
  2. Are there CAPTIONS? If yes we can read the claim without downloading the
     video and without paying Sarvam at all — a link check would then cost
     only the pipeline. This is the single biggest cost lever here.
  3. Is it within max_media_seconds, and what would ASR cost if we did have to
     transcribe it?

Nothing is downloaded and no paid API is called: yt-dlp runs metadata-only.
The only traffic is to the platform itself.

    .venv\\Scripts\\python.exe scripts\\link_probe.py <url> [<url> ...]
    .venv\\Scripts\\python.exe scripts\\link_probe.py --self-test
    .venv\\Scripts\\python.exe scripts\\link_probe.py --cookies-from chrome <url>

`--cookies-from` lends yt-dlp your BROWSER'S LOGIN for sites that gate
anonymous access (Instagram does). It reads your real session, so use it only
on your own machine and understand the server would then be acting as your
logged-in account — reasonable for a personal tool, not for a public service.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

# Sarvam bills ~Rs 30/hour by the second (PROJECT_PLAN section 8).
_ASR_RUPEES_PER_SECOND = 30.0 / 3600.0

# A real check would only ever fetch from an allowlist — this endpoint
# deliberately reopens the SSRF door section 7 records closing, so the probe
# reports the host and whether it is one we would be willing to fetch.
_ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com", "web.facebook.com",
    "fb.watch",
}


class _Silent:
    """yt-dlp prints its own errors to stderr; we report them ourselves."""

    def debug(self, m): pass
    def info(self, m): pass
    def warning(self, m): pass
    def error(self, m): pass


def _platform(url: str) -> str:
    u = url.lower()
    if "youtube.com/shorts" in u:
        return "YouTube Shorts"
    if "youtube.com" in u or "youtu.be" in u:
        return "YouTube"
    if "instagram.com/reel" in u or "instagram.com/p/" in u:
        return "Instagram Reel"
    if "instagram.com" in u:
        return "Instagram"
    if "facebook.com" in u or "fb.watch" in u:
        return "Facebook video/reel"
    if u.startswith("ytsearch"):
        return "YouTube (search)"
    return "unknown"


def _host_of(url: str) -> str:
    from urllib.parse import urlparse

    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _captions(info: dict) -> tuple[list[str], list[str]]:
    manual = sorted((info.get("subtitles") or {}).keys())
    auto = sorted((info.get("automatic_captions") or {}).keys())
    return manual, auto


def _indic(langs: list[str]) -> list[str]:
    """The languages this project exists for."""
    want = {"hi", "mr", "ta", "bn", "te", "kn", "ml", "gu", "pa", "ur", "or", "as"}
    return [l for l in langs if l.split("-")[0].split("_")[0] in want]


def _diagnose(message: str) -> str:
    """Name the failure, because 'it did not work' is not a measurement.

    The distinction that matters for /verify/link: a platform that gates
    anonymous access (fixable only with credentials, and a policy decision)
    versus a URL that is simply wrong (the user's problem, fixable by them).
    """
    m = message.lower()
    if "cookies" in m or "login" in m or "empty media response" in m:
        return ("GATED — the platform refused anonymous access. NOTE: for a "
                "made-up ID this looks identical to 'no such post'. Only a real "
                "public URL distinguishes the two.")
    if "unsupported url" in m:
        return "NOT A MEDIA URL — no extractor matched this address."
    if "private" in m or "not available" in m:
        return "PRIVATE or REMOVED."
    if "unavailable" in m or "404" in m or "not found" in m:
        return "NOT FOUND — bad ID, or deleted."
    if "timed out" in m or "timeout" in m or "connection" in m:
        return "NETWORK — could not reach the platform from this machine."
    return "UNCLASSIFIED — read the message above."


def probe(url: str, cookies_from: str | None = None) -> None:
    import yt_dlp

    print("=" * 70)
    print(f"URL       : {url}")
    print(f"Platform  : {_platform(url)}")
    host = _host_of(url)
    if host:
        ok = host in _ALLOWED_HOSTS
        print(f"Host      : {host}   [{'allowlisted' if ok else 'NOT on the allowlist'}]")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,      # metadata only — nothing is fetched
        "socket_timeout": 20,
        "noplaylist": True,
        "extract_flat": False,
        "logger": _Silent(),        # yt-dlp writes to stderr regardless of quiet
    }
    if cookies_from:
        opts["cookiesfrombrowser"] = (cookies_from,)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as exc:  # noqa: BLE001 — the whole point is to see failures
        msg = " ".join(str(exc).split())
        print("RESOLVES  : NO")
        print(f"Diagnosis : {_diagnose(msg)}")
        print(f"Raw       : {msg[:200]}")
        print("=" * 70)
        return

    if info.get("entries"):          # a search or playlist result
        info = info["entries"][0]

    duration = info.get("duration")
    print("RESOLVES  : YES")
    print(f"Title     : {(info.get('title') or '')[:80]}")
    print(f"Uploader  : {info.get('uploader') or info.get('channel') or '?'}")
    if duration is None:
        # Do NOT fall back to 0. Reporting an unknown duration as "0s, within
        # the cap" announces that a spend guard passed when it was never
        # applied — wrong in the one direction that costs money. Instagram
        # returns no duration at all, so the cap has to move after download.
        print("Duration  : UNKNOWN — platform did not report it")
        print(f"            !! the {settings.max_media_seconds}s cap CANNOT be "
              f"enforced before downloading; it must be probed post-download")
    elif duration > settings.max_media_seconds:
        print(f"Duration  : {duration}s   OVER the {settings.max_media_seconds}s "
              f"cap -> would be rejected")
    else:
        print(f"Duration  : {duration}s   (within the {settings.max_media_seconds}s cap)")

    # The post's own caption text. On Instagram this is the ONLY free text
    # source (there are no subtitles), and it frequently carries the claim
    # outright — measured: a PEEK TV reel's caption held a full quoted
    # assertion, checkable with no download and no ASR at all.
    desc = " ".join((info.get("description") or "").split())
    print()
    print(f"Post caption text           : {len(desc)} chars"
          f"{'  <- FREE claim source, no download, no ASR' if len(desc) > 40 else ''}")
    if desc:
        print(f'   "{desc[:160]}{"..." if len(desc) > 160 else ""}"')

    manual, auto = _captions(info)
    print()
    print(f"Captions (uploader-provided): {manual or 'none'}")
    print(f"Captions (auto-generated)   : {(auto[:12] or 'none')}"
          f"{' ...' if len(auto) > 12 else ''}")
    indic = _indic(manual) or _indic(auto)
    if manual or auto:
        print(f"  -> Indic languages present : {indic or 'none'}")
        print("  -> COULD SKIP SARVAM: read the claim from captions, Rs 0 of ASR")
    else:
        print("  -> no captions: would need audio download + Sarvam ASR")

    # What the audio path would cost if we had to take it.
    audio = [f for f in (info.get("formats") or [])
             if f.get("acodec") not in (None, "none") and f.get("vcodec") in (None, "none")]
    sizes = [f.get("filesize") or f.get("filesize_approx") for f in audio]
    sizes = [s for s in sizes if s]
    print()
    print(f"Audio-only formats          : {len(audio)}", end="")
    if sizes:
        print(f"   smallest ~{min(sizes) / 1e6:.1f} MB")
    else:
        # Same hazard as the duration: no advertised size means the byte cap
        # cannot be applied up front either, so the download itself must be
        # what enforces it.
        print("   size NOT advertised — cap the download as it streams")
    if duration is None:
        print("ASR cost if transcribed     : UNKNOWN (no duration) — probe after download")
    else:
        print(f"ASR cost if transcribed     : ~Rs {duration * _ASR_RUPEES_PER_SECOND:.2f}")
    print("=" * 70)


def main() -> None:
    args = sys.argv[1:]
    cookies_from = None
    if "--cookies-from" in args:
        i = args.index("--cookies-from")
        cookies_from = args[i + 1]
        del args[i:i + 2]
    if not args:
        print(__doc__)
        return
    if args == ["--self-test"]:
        # Proves the plumbing without needing a URL to hand: ytsearch resolves
        # a real video by query, so no invented video ID is involved.
        args = ["ytsearch1:PIB Fact Check"]
    print(">> FREE: metadata only, nothing downloaded, no paid API called.")
    if cookies_from:
        print(f">> Using your {cookies_from} login. See the module docstring.")
    print()
    for url in args:
        probe(url, cookies_from)


if __name__ == "__main__":
    main()
