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
    error: str | None = None
