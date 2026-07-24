"""Stage 2 — claim extraction (Opus 4.8 + validated structured output).

Extraction is on the expensive tier on purpose: a claim that is split
wrong or paraphrased into a different assertion poisons everything
downstream, and those errors are subtle.
"""
from app.config import settings
from app.engine.prompts import EXTRACTION_SYSTEM
from app.models.claim import Claim, ClaimList
from app.providers.llm import async_client


async def extract_claims(english_text: str) -> list[Claim]:
    resp = await async_client.messages.parse(
        model=settings.opus_model,
        max_tokens=8000,
        # cache_control marks the frozen prompt as cacheable (see prompts.py note)
        system=[{"type": "text", "text": EXTRACTION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": english_text}],
        output_format=ClaimList,
    )
    return resp.parsed_output.claims
