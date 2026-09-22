"""Sarvam ASR wiring probe — transcribes ONE short clip. Nearly free.

Costs a fraction of a rupee of Sarvam credits (billed per second, Rs 30/hr)
and NO Anthropic money — it stops at the transcript, never runs the pipeline.
Use it to confirm the key works or to try a WhatsApp voice note:

    .venv\\Scripts\\python.exe scripts\\asr_probe.py path\\to\\clip.ogg
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.providers.asr import get_asr_provider  # noqa: E402
from app.providers.media import normalize_to_wav  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402


async def main() -> None:
    force_utf8_stdout()   # it prints a Hindi transcript
    if not settings.sarvam_api_key:
        print("No SARVAM_API_KEY in .env. Aborting (no cost).")
        return
    if len(sys.argv) < 2:
        print("Usage: asr_probe.py <audio-or-video-file>")
        return

    path = sys.argv[1]
    with open(path, "rb") as f:
        data = f.read()
    wav, duration = normalize_to_wav(data, os.path.basename(path))
    cost = duration * 30 / 3600
    print(f">> {duration:.1f}s of audio -> Sarvam Saaras v3 (~Rs {cost:.3f} of credits)")

    transcript = await get_asr_provider().transcribe(wav)
    print(f">> language: {transcript.language}")
    print(f">> transcript: {transcript.text!r}")


if __name__ == "__main__":
    asyncio.run(main())
