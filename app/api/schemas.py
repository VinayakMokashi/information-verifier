"""Request/response DTOs for the REST surface.

Kept separate from the domain models so the wire contract can evolve
independently of the engine's internal shapes.
"""
from pydantic import BaseModel, Field

from app.models.report import JobStatus


class VerifyTextRequest(BaseModel):
    text: str = Field(min_length=1, description="Raw text/claim to fact-check.")
    language_hint: str | None = Field(
        default=None, description="Optional source-language code to aid normalization."
    )


class JobAccepted(BaseModel):
    """Returned immediately; the report is built in the background."""

    job_id: str
    status: JobStatus
