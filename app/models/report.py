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
    overall_rating: Rating | None = None
    summary: str | None = None
    claim_verdicts: list[ClaimVerdict] = Field(default_factory=list)
    error: str | None = None
