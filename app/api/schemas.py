"""Request/response DTOs for the REST surface.

Kept separate from the domain models so the wire contract can evolve
independently of the engine's internal shapes.
"""
from pydantic import BaseModel, Field

from app.models.answer import JobStatus


# The reader picks the reply language (2026-09-23). A NAME, not a code —
# the model reads it directly, and the page's box lets anyone type one that
# is not on a button. Empty or "auto" means "the language it came in".
_LANGUAGE = Field(default=None, max_length=40,
                  description='Reply language, e.g. "Hindi". Omit for the '
                              "sender's own language.")


class VerifyTextRequest(BaseModel):
    text: str = Field(min_length=1, description="Raw text/claim to fact-check.")
    language: str | None = _LANGUAGE


class VerifyLinkRequest(BaseModel):
    url: str = Field(
        min_length=12, max_length=2048,
        description="A public Instagram Reel or YouTube (Shorts) URL to fact-check.",
    )
    language: str | None = _LANGUAGE


class JobAccepted(BaseModel):
    """Returned immediately; the report is built in the background."""

    job_id: str
    status: JobStatus
