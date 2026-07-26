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
import tempfile

_TIMEOUT_S = 120           # a crafted file must not pin a worker forever
_SAFE_SUFFIX = re.compile(r"^\.[A-Za-z0-9]{1,8}$")
# The uploaded bytes are untrusted. Some ffmpeg demuxers (HLS, concat) will
# happily open URLs referenced *inside* the file; restricting protocols to
# local files keeps a "voice note" from turning into a server-side fetcher.
# (-nostdin is an ffmpeg-only option — ffprobe errors on it.)
_PROTOCOL_GUARD = ["-protocol_whitelist", "file"]
_FFMPEG_GUARDS = ["-nostdin", *_PROTOCOL_GUARD]


class MediaError(Exception):
    """The file could not be read as audio (bad container, no audio track…)."""


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
    return suffix if _SAFE_SUFFIX.match(suffix) else ".bin"


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


def normalize_to_wav(data: bytes, filename: str = "media") -> tuple[bytes, float]:
    """Any audio/video bytes -> (16 kHz mono WAV bytes, duration in seconds)."""
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "src" + _safe_suffix(filename))
        wav = os.path.join(tmp, "out.wav")
        with open(src, "wb") as f:
            f.write(data)
        _run([
            "ffmpeg", "-v", "error", "-y", *_FFMPEG_GUARDS, "-i", src,
            "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
            wav,
        ])
        duration = _probe_duration(wav)
        with open(wav, "rb") as f:
            return f.read(), duration


def split_wav(wav_bytes: bytes, chunk_seconds: int) -> list[bytes]:
    """Split a WAV into <=chunk_seconds pieces (for the 30 s sync ASR limit)."""
    with tempfile.TemporaryDirectory() as tmp:
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
