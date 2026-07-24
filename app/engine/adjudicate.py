"""Stage 4 — adjudication (Opus 4.8, adaptive thinking, validated Verdict).

This is the one call where correctness matters most, so it gets the
reasoning tier and adaptive thinking. It has NO tools: it reasons only over
the evidence retrieval already gathered, which keeps citations grounded in
real, whitelisted URLs and removes the pause_turn complexity from the
structured-output path.
"""
from app.config import settings
from app.engine.prompts import ADJUDICATION_SYSTEM
from app.models.claim import Claim
from app.models.evidence import Evidence
from app.models.verdict import Rating, Verdict
from app.providers.llm import async_client


def _render(claim: Claim, evidence: Evidence) -> str:
    lines = [f"CLAIM: {claim.text}", "", "EVIDENCE SUMMARY:", evidence.summary or "(none found)", ""]
    if evidence.sources:
        lines.append("SOURCES (cite only from this list):")
        for i, s in enumerate(evidence.sources, 1):
            lines.append(f"[{i}] {s.publisher} — {s.title}\n    {s.url}")
    else:
        lines.append("SOURCES: (none)")
    return "\n".join(lines)


async def adjudicate(claim: Claim, evidence: Evidence) -> Verdict:
    # No sources found -> don't even spend a reasoning call; abstain deterministically.
    if not evidence.sources and not evidence.summary:
        return Verdict(
            rating=Rating.UNVERIFIED,
            confidence=0,
            reasoning="No trusted source addressed this claim, so it cannot be rated.",
            correction="",
            citations=[],
        )

    resp = await async_client.messages.parse(
        model=settings.opus_model,
        max_tokens=8000,
        system=[{"type": "text", "text": ADJUDICATION_SYSTEM, "cache_control": {"type": "ephemeral"}}],
        thinking={"type": "adaptive"},  # effort defaults to "high" on Opus 4.8
        messages=[{"role": "user", "content": _render(claim, evidence)}],
        output_format=Verdict,
    )
    return resp.parsed_output
