"""Speech-to-text behind a Protocol, backed by Sarvam AI.

Sarvam is purpose-built for Indic languages (Hindi, Marathi, Tamil,
Bengali, and code-mixed Hinglish), where general models have much worse
WER on exactly the audio Indian users send. The Protocol keeps the
pipeline decoupled from the vendor — swap in AI4Bharat IndicWhisper or
another provider without touching engine code.

NOTE (Phase 2): the request/response shape below follows Sarvam's
documented STT API but should be confirmed against their current docs
before production use. The audio path is not wired into the REST surface
in Phase 1 — this is the adapter, ready to plug in.
"""
from typing import Protocol

import httpx

from app.config import settings
from app.models.evidence import Source  # noqa: F401  (kept for symmetry / future use)


class Transcript:
    def __init__(self, text: str, language: str | None = None):
        self.text = text
        self.language = language


class ASRProvider(Protocol):
    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        ...


class SarvamASR:
    """Sarvam AI Saarika speech-to-text."""

    _ENDPOINT = "https://api.sarvam.ai/speech-to-text"

    def __init__(self, api_key: str):
        self._api_key = api_key

    async def transcribe(self, audio: bytes, language_hint: str | None = None) -> Transcript:
        headers = {"api-subscription-key": self._api_key}
        data = {"model": "saarika:v2", "language_code": language_hint or "unknown"}
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
