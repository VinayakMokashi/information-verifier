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

Unlike /verify/link, this WILL attempt a host that is not allowlisted — and
says so loudly — because evaluating a new platform before adding it is the
workflow that put Facebook on the list. It is an operator tool for URLs you
typed yourself, never an endpoint.

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
from app.providers.links import ALLOWED_HOSTS, _classified, _pick_subtitle  # noqa: E402

# Sarvam bills ~Rs 30/hour by the second (PROJECT_PLAN section 8).
_ASR_RUPEES_PER_SECOND = 30.0 / 3600.0

# A real check would only ever fetch from an allowlist — this endpoint
# deliberately reopens the SSRF door section 7 records closing, so the probe
# reports the host and whether it is one we would be willing to fetch.
# Imported, never copied: this list decides what the SERVER will fetch,
# and the probe's whole job is to predict /verify/link's behaviour. A
# local copy had already drifted (missing m.instagram.com), so the probe
# mispredicted the very thing it exists to check.
_ALLOWED_HOSTS = ALLOWED_HOSTS


from app.providers.links import _Silent  # noqa: E402  (yt-dlp logger silencer)
from scripts.render import force_utf8_stdout  # noqa: E402


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


def caption_verdict(info: dict) -> str:
    """What /verify/link would do with this post's captions — asked of the
    app's own `_pick_subtitle`, never re-derived here.

    MEASURED 2026-09-22: this probe said "COULD SKIP SARVAM" for any post
    with any caption track, while the app only trusts an uploader's track,
    YouTube's '-orig' or Facebook's '_FB' (anything else may be a machine
    TRANSLATION of the speech). A Spanish Facebook video carrying
    ['es_CL', 'vi_VN'] was promised free when the app would pay for ASR.
    """
    ref = _pick_subtitle(info)
    if ref is None:
        return "the app would transcribe the audio (Sarvam ASR)"
    return f"the app would read the '{ref.lang}' captions instead - Rs 0 of ASR"


def _captions(info: dict) -> tuple[list[str], list[str]]:
    manual = sorted((info.get("subtitles") or {}).keys())
    auto = sorted((info.get("automatic_captions") or {}).keys())
    return manual, auto


def _indic(langs: list[str]) -> list[str]:
    """The languages this project exists for."""
    want = {"hi", "mr", "ta", "bn", "te", "kn", "ml", "gu", "pa", "ur", "or", "as"}
    return [l for l in langs if l.split("-")[0].split("_")[0] in want]


# Operator-facing gloss per LinkError.kind. The CLASSIFICATION itself comes
# from links._classified — the probe exists to predict what /verify/link will
# do, so a second keyword list here would (and did) drift: this copy lacked
# the rate-limit branch and disagreed with the app about "unavailable".
_KIND_HINT = {
    "gated": ("GATED — the platform refused anonymous access. NOTE: for a "
              "made-up ID this looks identical to 'no such post'. Only a real "
              "public URL distinguishes the two."),
    "private": "PRIVATE or REMOVED.",
    "unsupported": "NOT A MEDIA URL — no extractor matched this address.",
    "not_found": "NOT FOUND — bad ID, or deleted.",
    "network": "NETWORK — the platform could not be reached (or rate-limited us).",
    "too_large": "TOO LARGE — over the byte cap.",
    "other": "UNCLASSIFIED — read the raw message below.",
}


def _diagnose(exc: Exception) -> str:
    """Name the failure exactly as the app would, because 'it did not work'
    is not a measurement — and a probe that disagrees with the endpoint it
    models is worse than no probe."""
    err = _classified(exc)
    return f"[{err.kind}] {_KIND_HINT.get(err.kind, _KIND_HINT['other'])}"


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
        print("RESOLVES  : NO")
        print(f"Diagnosis : {_diagnose(exc)}")
        print(f"Raw       : {' '.join(str(exc).split())[:200]}")
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
    print(f"  -> {caption_verdict(info)}")

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
    force_utf8_stdout()   # captions are routinely Hindi
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
