"""Claim contract — the output schema for the extraction stage.

Every field is required (no defaults): structured outputs demand
`additionalProperties: false` and a fully-`required` object, so the model
must fill all of them. Descriptions are the model's instructions — write
them as such.
"""
from typing import Literal

from pydantic import BaseModel, Field

ClaimType = Literal["statistic", "event", "quote", "attribution", "causal", "other"]


class Claim(BaseModel):
    text: str = Field(
        description="One atomic, independently verifiable factual assertion, "
        "rewritten in clear English. Split compound sentences into separate claims."
    )
    subject: str = Field(
        description="The primary entity, person, or organization the claim is about."
    )
    claim_type: ClaimType = Field(
        description="The kind of assertion: a statistic, a dated event, a direct "
        "quote, an attribution of a statement, a causal link, or other."
    )
    checkworthy: bool = Field(
        description="True only if the claim is a falsifiable statement of fact. "
        "False for opinions, predictions, jokes, or unfalsifiable statements."
    )


class ClaimList(BaseModel):
    """Top-level structured-output wrapper for extraction."""

    claims: list[Claim]
