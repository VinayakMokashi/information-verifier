"""Verdict contract — the output schema for the adjudication stage.

The rating scale deliberately includes UNVERIFIED. Absence of evidence in
the trusted sources is NOT evidence of falsehood; forcing a true/false
call on a novel claim is how a fact-checker manufactures confident wrong
answers. The model must be able to abstain.
"""
from enum import Enum

from pydantic import BaseModel, Field


class Rating(str, Enum):
    TRUE = "TRUE"
    MOSTLY_TRUE = "MOSTLY_TRUE"
    MISLEADING = "MISLEADING"
    FALSE = "FALSE"
    UNVERIFIED = "UNVERIFIED"  # trusted sources are silent — not a falsehood


class Citation(BaseModel):
    url: str = Field(description="Exact URL, copied from the provided sources only.")
    title: str = Field(description="Headline or title of the source, copied verbatim.")
    publisher: str = Field(description="Publisher name, e.g. 'AltNews', 'PIB', 'Reuters'.")


class Verdict(BaseModel):
    rating: Rating
    confidence: int = Field(
        description="Calibrated confidence in the rating, 0-100. Use low values "
        "when evidence is thin or sources disagree."
    )
    reasoning: str = Field(
        description="Why this rating follows from the evidence. Reference the "
        "sources by publisher. Two to four sentences."
    )
    correction: str = Field(
        description="The accurate information, if the claim is false or misleading. "
        "Empty string if the claim is TRUE or UNVERIFIED."
    )
    citations: list[Citation] = Field(
        description="The specific sources that support this verdict. Copy them from "
        "the provided source list only — never invent a URL. Empty if UNVERIFIED."
    )
