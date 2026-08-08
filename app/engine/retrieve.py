"""Stage 3 — evidence retrieval.

Two sources run concurrently:
  1. Native web_search_20260209 with allowed_domains = the whitelist. The
     domain restriction is enforced server-side by Anthropic, so we never
     scrape or filter results ourselves.
  2. Google Fact Check API for prior structured ClaimReview verdicts.

Web search is a server-side tool, so the model runs its own search loop and
may return stop_reason == "pause_turn" when it hits the per-turn tool limit.
We resume by re-sending the assistant turn (no extra "continue" message).
"""
import asyncio
from urllib.parse import urlparse

import anthropic

from app.config import settings
from app.engine.prompts import RETRIEVAL_PROMPT
from app.models.claim import Claim
from app.models.evidence import Evidence, Source
from app.providers.factcheck import search_factcheck
from app.providers.llm import async_client
from app.trusted_sources import SEARCH_DOMAINS

_MAX_CONTINUATIONS = 6  # backstop against a runaway pause_turn loop


def _publisher_of(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host or "unknown"


def _tools(remaining_searches: int) -> list[dict]:
    return [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "allowed_domains": SEARCH_DOMAINS,   # only crawler-accessible domains
            "max_uses": remaining_searches,
            # Haiku doesn't support programmatic (code-invoked) tool calling;
            # declare web_search as directly-called so it runs on the cheap model.
            "allowed_callers": ["direct"],
        }
    ]


async def _web_search(claim: Claim) -> tuple[str, list[Source]]:
    # `max_uses` is a PER-REQUEST cap, and a pause_turn loop makes up to
    # _MAX_CONTINUATIONS requests — so "4 searches per claim" could lawfully
    # have billed 4 on each continuation. Whether the API resets the count on
    # resume was disputed in review; rather than settle the argument, the
    # budget is enforced HERE: each response's measured search count (its own
    # usage field) is subtracted, the next request offers only the remainder,
    # and the loop stops when the budget is spent. The documented cap is now
    # the code's cap regardless of server-side semantics.
    remaining = settings.max_search_uses
    messages = [{"role": "user", "content": RETRIEVAL_PROMPT.format(claim=claim.text)}]
    summary_parts: list[str] = []
    sources: list[Source] = []

    for _ in range(_MAX_CONTINUATIONS):
        try:
            # Haiku, not Opus: retrieval reads the full text of every page it
            # finds (token-heavy), but it's only gathering/summarizing evidence.
            # The judgment call happens later in adjudicate() on Opus. This is
            # the single biggest cost lever in the pipeline.
            resp = await async_client.messages.create(
                model=settings.haiku_model,
                max_tokens=6000,
                tools=_tools(remaining),
                messages=messages,
            )
        except anthropic.APIError as exc:
            # Web search unavailable (e.g. a whitelisted domain blocks the
            # crawler). Degrade gracefully — lean on Fact Check API evidence
            # instead of sinking the whole claim.
            print(f"[retrieve] web search failed: {type(exc).__name__}: {exc}")
            break
        for block in resp.content:
            if block.type == "text":
                summary_parts.append(block.text)
            elif block.type == "web_search_tool_result":
                content = block.content
                # success -> list of results; error -> a single error object
                if isinstance(content, list):
                    for r in content:
                        sources.append(
                            Source(url=r.url, title=r.title, publisher=_publisher_of(r.url))
                        )

        server_tools = getattr(getattr(resp, "usage", None), "server_tool_use", None)
        remaining -= getattr(server_tools, "web_search_requests", 0) or 0

        if resp.stop_reason == "pause_turn" and remaining > 0:
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason == "pause_turn":
            print(f"[retrieve] search budget spent ({settings.max_search_uses}); "
                  f"not resuming the paused turn")
        break

    return "\n".join(summary_parts).strip(), sources


def _dedup(sources: list[Source]) -> list[Source]:
    seen: set[str] = set()
    out: list[Source] = []
    for s in sources:
        if s.url and s.url not in seen:
            seen.add(s.url)
            out.append(s)
    return out


async def gather_evidence(claim: Claim) -> Evidence:
    (summary, web_sources), fc_sources = await asyncio.gather(
        _web_search(claim),
        search_factcheck(claim.text),
    )
    # Surface prior human fact-check verdicts at the top of the evidence so the
    # adjudicator weighs them explicitly, not just as extra links.
    if fc_sources:
        note = "Prior fact-check verdicts (Google Fact Check API):\n" + "\n".join(
            f"- {s.publisher}: {s.title}" for s in fc_sources
        )
        summary = f"{note}\n\n{summary}".strip()
    return Evidence(summary=summary, sources=_dedup(web_sources + fc_sources))
