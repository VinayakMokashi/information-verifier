"""ffmpeg helpers for the audio/video path.

Everything Sarvam sees is first normalized to 16 kHz mono WAV — their
recommended input — which also collapses every container WhatsApp produces
(OGG/Opus voice notes, MP4 video, AAC, AMR…) into one uniform pipeline.
The sync Sarvam endpoint takes <=30 s of audio per request, so longer audio
is split into chunks with ffmpeg's segment muxer.

ffmpeg/ffprobe are called as subprocesses (installed via winget on this
machine). All helpers are synchronous — callers wrap them in
asyncio.to_thread so the event loop never blocks on a transcode.
"""
import os
import re
import subprocess

# Working files under the data folder, which startup empties — never %TEMP%,
# where a hard stop left people's voice notes for good (review S5-17).
from app.store import scratch

_TIMEOUT_S = 120           # a crafted file must not pin a worker forever
# \Z, not $: in Python `$` also matches before a trailing newline, so
# "note.ogg\n" would have passed and then failed at open() with an OSError
# the route does not catch — a 500 from any curl against the public link.
_SAFE_SUFFIX = re.compile(r"\.[A-Za-z0-9]{1,8}\Z")
# The uploaded bytes are untrusted. Some ffmpeg demuxers (HLS, concat) will
# happily open URLs referenced *inside* the file; restricting protocols to
# local files keeps a "voice note" from turning into a server-side fetcher.
# (-nostdin is an ffmpeg-only option — ffprobe errors on it.)
_PROTOCOL_GUARD = ["-protocol_whitelist", "file"]
_FFMPEG_GUARDS = ["-nostdin", *_PROTOCOL_GUARD]


class MediaError(Exception):
    """The file could not be read as audio (bad container, no audio track…)."""


class MediaTooLong(MediaError):
    """Longer than the caller allows — detected before decoding it."""

    def __init__(self, seconds: float):
        self.seconds = seconds
        super().__init__(f"Audio is {seconds:.0f}s long")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=_TIMEOUT_S)
    except FileNotFoundError as exc:  # ffmpeg/ffprobe not installed
        raise MediaError(f"{args[0]} is not installed on this server.") from exc
    except subprocess.TimeoutExpired as exc:
        raise MediaError("Audio processing timed out.") from exc
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["unknown ffmpeg error"]
        raise MediaError(tail[0])
    return proc


def _safe_suffix(filename: str) -> str:
    """A temp-file extension derived from, but never trusting, the upload name."""
    suffix = os.path.splitext(filename)[1]
    return suffix if _SAFE_SUFFIX.fullmatch(suffix) else ".bin"


def _probe_duration(path: str) -> float:
    proc = _run([
        "ffprobe", "-v", "error", *_PROTOCOL_GUARD,
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        path,
    ])
    try:
        return float(proc.stdout.strip())
    except ValueError as exc:
        raise MediaError("Could not determine audio duration.") from exc


def normalize_to_wav(
    data: bytes, filename: str = "media", max_seconds: float | None = None
) -> tuple[bytes, float]:
    """Any audio/video bytes -> (16 kHz mono WAV bytes, duration in seconds).

    Pass `max_seconds` to bound the work: decoding expands audio enormously
    (a 3 MB Opus file at 6 kbps is an hour of sound and 110 MB of PCM — 34x),
    so an upload that satisfies a byte cap can still exhaust memory if it is
    decoded before its duration is known. The source duration is probed
    first, and ffmpeg is additionally told to stop at the limit in case the
    container lies or the probe cannot read it.
    """
    with scratch.workdir() as tmp:
        src = os.path.join(tmp, "src" + _safe_suffix(filename))
        wav = os.path.join(tmp, "out.wav")
        try:
            with open(src, "wb") as f:
                f.write(data)
        except OSError as exc:  # a filesystem refusal is the caller's 422
            raise MediaError("Could not stage the upload for decoding.") from exc

        limit: list[str] = []
        if max_seconds is not None:
            try:
                source_seconds = _probe_duration(src)
            except MediaError:
                source_seconds = None  # unreadable header; -t still bounds us
            if source_seconds is not None and source_seconds > max_seconds:
                raise MediaTooLong(source_seconds)
            # Hard stop one second past the cap: never decode more than that.
            limit = ["-t", str(max_seconds + 1)]

        _run([
            "ffmpeg", "-v", "error", "-y", *_FFMPEG_GUARDS, "-i", src, *limit,
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            wav,
        ])
        duration = _probe_duration(wav)
        if max_seconds is not None and duration > max_seconds:
            raise MediaTooLong(duration)  # the probe was wrong; -t caught it
        # The produced WAV's duration is what Sarvam will bill by the second.
        # Noted here — the one place both the upload and link paths pass
        # through — into the ambient per-report meter, if one is active.
        from app.providers.usage import note_asr

        note_asr(duration)
        with open(wav, "rb") as f:
            return f.read(), duration


def split_wav(wav_bytes: bytes, chunk_seconds: int) -> list[bytes]:
    """Split a WAV into <=chunk_seconds pieces (for the 30 s sync ASR limit)."""
    with scratch.workdir() as tmp:
        src = os.path.join(tmp, "in.wav")
        with open(src, "wb") as f:
            f.write(wav_bytes)
        _run([
            "ffmpeg", "-v", "error", "-y", *_FFMPEG_GUARDS, "-i", src,
            "-f", "segment", "-segment_time", str(chunk_seconds),
            "-c", "copy",
            os.path.join(tmp, "chunk%04d.wav"),
        ])
        chunks = []
        for name in sorted(os.listdir(tmp)):
            if name.startswith("chunk"):
                with open(os.path.join(tmp, name), "rb") as f:
                    chunks.append(f.read())
        if not chunks:
            raise MediaError("Audio splitting produced no chunks.")
        return chunks
