"""Speech-to-text behind a Protocol, backed by Sarvam AI.

Sarvam is purpose-built for Indic languages (Hindi, Marathi, Tamil,
Bengali, and code-mixed Hinglish), where general models have much worse
WER on exactly the audio Indian users send. The Protocol keeps the
pipeline decoupled from the vendor — swap in AI4Bharat IndicWhisper or
another provider without touching engine code.

NOTE (Phase 2): request/response shape re-verified against Sarvam's docs
on 2026-07-25 (endpoint, api-subscription-key header, multipart fields).
Not yet live-tested — needs a SARVAM_API_KEY. The sync endpoint takes
audio up to 30 s; longer audio must be chunked (ffmpeg -f segment) or go
through Sarvam's batch API. WhatsApp voice notes (OGG/Opus) are accepted
directly. The audio path is not wired into the REST surface yet — this
is the adapter, ready to plug in.
"""
from typing import Protocol

import httpx

from app.config import settings


class Transcript:
    def __init__(self, text: str, language: str | None = None):
        self.text = text
        self.language = language


class ASRProvider(Protocol):
    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        ...


class SarvamASR:
    """Sarvam AI Saaras speech-to-text (saarika is legacy, deprecating)."""

    _ENDPOINT = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        headers = {"api-subscription-key": self._api_key}
        # mode=translate would emit English directly into our English-centric
        # pipeline; decide transcribe-vs-translate when wiring /verify/media.
        data = {"model": "saaras:v3", "language_code": language_hint or "unknown"}
        files = {"file": ("audio.wav", audio, "audio/wav")}
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(self._ENDPOINT, headers=headers, data=data, files=files)
        resp.raise_for_status()
        body = resp.json()
        return Transcript(text=body.get("transcript", ""), language=body.get("language_code"))


class StubASR:
    """No-op provider used when SARVAM_API_KEY is unset, so the app still boots."""

    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        raise RuntimeError("ASR is not configured. Set SARVAM_API_KEY to enable audio.")


def get_asr_provider() -> ASRProvider:
    if settings.sarvam_api_key:
        return SarvamASR(settings.sarvam_api_key)
    return StubASR()
