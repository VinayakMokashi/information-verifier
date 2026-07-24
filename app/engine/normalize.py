"""Stage 1 — language detection + translation to an English pivot (Haiku)."""
from pydantic import BaseModel, Field

from app.config import settings
from app.engine.prompts import NORMALIZE_SYSTEM
from app.providers.llm import async_client


class NormalizeResult(BaseModel):
    detected_language: str = Field(
        description="Primary language of the input as a short code or name, "
        "e.g. 'en', 'hi', 'mr', 'ta', 'bn'."
    )
    english_text: str = Field(
        description="Faithful English translation, preserving every factual "
        "assertion. If already English, the original text unchanged."
    )


async def normalize(text: str) -> NormalizeResult:
    resp = await async_client.messages.parse(
        model=settings.haiku_model,
        max_tokens=4000,
        system=NORMALIZE_SYSTEM,
        messages=[{"role": "user", "content": text}],
        output_format=NormalizeResult,
    )
    return resp.parsed_output
