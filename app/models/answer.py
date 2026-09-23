"""The Answer — one Claude-style reply to one submitted thing.

This replaces the structured Truth Report (rating enum + per-claim verdicts +
localized block). The shape difference is the point of the pivot: a person
who pastes a forward wants a paragraph that explains, not a form to read.

What is still STRUCTURED, deliberately, is everything a user could be misled
by if the model simply asserted it in prose:

  * `sources` — built from the API's own citation objects, never parsed out
    of the answer text. The model can write a convincing fake link in
    markdown; renderers show links only from here.
  * `tier` — computed from `trusted_domain_of()` over those sources, never
    from what the model claims about its own searching.
  * `confidence` — parsed from a sentinel the input cannot forge, validated,
    and always displayed with its basis.

`sections` keeps the two evidence tiers separate on the page: a "trusted
fact-checkers" section and, when they were silent, a clearly-labelled
"general web" one. Merging them into one blob is how a reader ends up
thinking a random blog carried a fact-checker's authority.
"""
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"


class ModelUsage(BaseModel):
    """Token totals for one model across a job, from the API's own usage."""

    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0


class ReportUsage(BaseModel):
    """What this job actually spent — measured, not modelled.

    The cost model was only ever a model until the first metered run
    (2026-07-28: $0.279 against $0.39 predicted). Every job carries its own
    bill so the numbers in PROJECT_PLAN §8 stay honest. `estimated_usd`
    applies list prices to measured tokens — the tokens are facts, only the
    dollar figure inherits pricing-table staleness.
    """

    models: dict[str, ModelUsage] = Field(default_factory=dict)
    web_searches: int = 0
    asr_seconds: float = 0.0
    estimated_usd: float = 0.0
    # Where the money went — so the spending dashboard can say "searches cost
    # more than thinking this week" without re-deriving prices. They sum to
    # estimated_usd (before rounding).
    llm_usd: float = 0.0
    search_usd: float = 0.0
    asr_usd: float = 0.0


Tier = Literal["trusted", "web", "none"]


class Source(BaseModel):
    """One piece of evidence the API actually returned.

    `tier` is assigned by the server from the URL's host, so a source found
    during the open-web pass that happens to be AltNews is still `trusted`,
    and one the model merely *described* as a fact-checker is not.
    """

    url: str
    title: str = ""
    publisher: str = ""      # "BOOM", "WHO" — what a reader recognises
    tier: Tier = "web"
    via: Literal["search", "factcheck"] = "search"
    cited_text: str = ""

    @property
    def display_name(self) -> str:
        """Publisher if we have one, else the bare host. Never an empty chip."""
        if self.publisher:
            return self.publisher
        from urllib.parse import urlparse

        return (urlparse(self.url).hostname or "source").removeprefix("www.")


class AnswerSection(BaseModel):
    """One tier's worth of prose, kept separate from the other's."""

    tier: Tier
    markdown: str


class Answer(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    completed_at: datetime | None = None

    # What the person sent. Needed to redraw their side of the conversation
    # when a job is resumed from the page's #job= hash after a reload.
    input_text: str = ""
    # What a MACHINE read, when one did: the ASR transcript or the OCR text,
    # or a link's caption + transcript. Shown back before the answer, because
    # a mis-hear would otherwise become a confident reply about words the
    # sender never said.
    source_text: str | None = None

    sections: list[AnswerSection] = Field(default_factory=list)
    # Two short lines for a reader who will not read the whole answer, shown
    # in their own highlighted box (Vinayak, 2026-09-23). Written by the
    # model in the reply's language and taken out of the prose, so it is
    # never shown twice. None when the model did not write one.
    summary: str | None = None
    sources: list[Source] = Field(default_factory=list)
    confidence: int | None = None        # None = the model did not state one
    tier: Tier = "none"
    truncated: bool = False              # hit max_tokens; answer is cut short

    cached: bool = False                 # served from answer_cache, $0
    usage: ReportUsage | None = None
    error: str | None = None

    @property
    def markdown(self) -> str:
        """The whole answer as one string (console, bot, cache round-trip)."""
        return "\n\n".join(s.markdown for s in self.sections if s.markdown.strip())
