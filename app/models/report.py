"""The Truth Report — the public-facing deliverable and job record."""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.models.claim import Claim
from app.models.verdict import Rating, Verdict


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ClaimVerdict(BaseModel):
    claim: Claim
    verdict: Verdict
    cache_hit: bool = False  # served from the claim cache without a fresh LLM call


class ModelUsage(BaseModel):
    """Token totals for one model across a report, from the API's own usage."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0


class ReportUsage(BaseModel):
    """What this report actually spent — measured, not modelled.

    §8's numbers were models until the first metered run (2026-07-28);
    this block makes every report carry its own bill. `estimated_usd`
    applies list prices to measured tokens, so the tokens are facts and
    only the dollar figure inherits pricing-table staleness.
    """

    models: dict[str, ModelUsage] = Field(default_factory=dict)
    web_searches: int = 0
    asr_seconds: float = 0.0
    estimated_usd: float = 0.0


class LocalizedClaim(BaseModel):
    """One claim's prose in the reader's language.

    Carries no rating, confidence or citation on purpose. A rating is a
    structured enum and must not survive a round-trip through a translator;
    a citation's title and publisher are the strings a reader looks for on
    the source page, so translating them makes the receipt unfindable.
    """

    claim: str = Field(description="The claim itself, in the target language.")
    reasoning: str = Field(
        description="Why this rating follows from the evidence, in the target language."
    )
    correction: str = Field(
        description="The accurate information, in the target language. Empty "
        "string if the English correction was empty — never invent one."
    )


class LocalizedReport(BaseModel):
    """The English report's prose, restated in the reader's language."""

    language: str
    summary: str | None = None
    # Index-aligned with TruthReport.claim_verdicts, same length, and `None`
    # where that one claim's translation failed. A missing entry means "show
    # the English for this claim", never "shift the next one up".
    claims: list[LocalizedClaim | None] = Field(default_factory=list)


class TruthReport(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None

    input_language: str | None = None       # BCP-47-ish code detected at normalize
    # What the engine actually read, when a machine derived it: the ASR
    # transcript or the OCR text. Shown back to the user because a
    # mis-transcription would otherwise mean silently checking a DIFFERENT
    # claim (measured: Sarvam dropped "5जी" from a Hindi clip).
    source_text: str | None = None
    overall_rating: Rating | None = None
    summary: str | None = None
    claim_verdicts: list[ClaimVerdict] = Field(default_factory=list)
    # The same report in the language the message arrived in. ADDITIVE: the
    # English above stays canonical, so a bad translation can never overwrite
    # what was actually adjudicated, and the claim cache keeps storing English
    # verdicts. Absent when the input was English, when translation is off, or
    # when it failed — clients must fall back to the English fields.
    localized: LocalizedReport | None = None
    # Measured spend for this report (None for reports predating the meter).
    usage: ReportUsage | None = None
    error: str | None = None
