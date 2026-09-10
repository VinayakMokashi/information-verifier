"""The chat engine: one submitted thing in, one Claude-style answer out.

Replaces the six-stage pipeline. The design points that matter:

**Whitelist first, then the open web.** Pass 1 searches only SEARCH_DOMAINS —
the Indian fact-checkers this service trusts. If they had nothing, pass 2
searches the wider web and its prose is labelled as such. `allowed_domains`
and `blocked_domains` are mutually exclusive on one web_search tool, so this
is genuinely two requests; and since `tools` render first in the cache prefix,
a continuation would share no cache with pass 1 anyway.

**Tier is computed, never claimed.** The model's `trusted=` flag can only
TRIGGER a wider search — the label on every source comes from
`trusted_domain_of()` over the URLs the API itself returned. So a model that
says "I found AltNews" while citing a blog cannot promote its own answer, and
a genuinely trusted page found during pass 2 is still labelled trusted.

**A parse failure never escalates spend.** No sentinel means no confidence and
no second pass: the failure mode of a malformed marker must be "answer with
what we have", not "spend again".

**Streaming is not instrumented by providers/usage.py** (it wraps parse and
create only), so every request here reports its own usage explicitly or the
report bills $0.00 while real money leaves.
"""
import asyncio
from dataclasses import dataclass, field
from typing import Awaitable, Callable

import anthropic

from app.config import settings
from app.engine.chat_prompts import (
    CHAT_SYSTEM_TRUSTED, CHAT_SYSTEM_WEB, as_prompt_data,
)
from app.engine.marker import MarkerFilter
from app.models.answer import AnswerSection, Source, Tier
from app.providers.factcheck import search_factcheck
from app.providers.llm import async_client
from app.providers.usage import note_llm
from app.trusted_sources import (
    CORE_SEARCH_DOMAINS, SEARCH_DOMAINS, trusted_domain_of,
)

# A paused turn must not loop forever; same backstop the old retrieval had.
_MAX_CONTINUATIONS = 6
_MAX_INPUT_CHARS = 8000       # a forward, not a book (also a spend bound)
_MAX_HEARD_CHARS = 8000
_MAX_FACTCHECK_LINES = 8

# Pass 2 reads the open web, where "someone said it on Facebook" is the
# rumour's own echo rather than evidence for it. Kept short on purpose: a long
# blocklist is a maintenance burden that mostly duplicates the model's own
# judgment about source quality.
_WEB_BLOCKED_DOMAINS = [
    "facebook.com", "instagram.com", "x.com", "twitter.com", "tiktok.com",
    "reddit.com", "quora.com", "sharechat.com", "koo.com", "t.me",
    "blogspot.com", "wordpress.com", "medium.com",
]


class AnswerRefused(Exception):
    """The model declined the request (stop_reason == "refusal")."""


@dataclass
class PassResult:
    markdown: str = ""
    sources: list[Source] = field(default_factory=list)
    confidence: int | None = None
    model_says_trusted: bool | None = None
    truncated: bool = False


@dataclass
class ChatAnswer:
    """What `answer()` produces; the caller persists it into an `Answer`."""

    sections: list[AnswerSection] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    confidence: int | None = None
    tier: Tier = "none"
    truncated: bool = False

    @property
    def markdown(self) -> str:
        """Every tier's prose as one string — mirrors Answer.markdown."""
        return "\n\n".join(s.markdown for s in self.sections if s.markdown.strip())


Emit = Callable[[str, dict], Awaitable[None]]


async def _noop_emit(kind: str, data: dict) -> None:
    return None


def _tools(trusted: bool, remaining: int, *, core_only: bool = False) -> list[dict]:
    tool: dict = {
        "type": "web_search_20260209",
        "name": "web_search",
        "max_uses": max(1, remaining),
    }
    # Mutually exclusive — one or the other, never both.
    if trusted:
        tool["allowed_domains"] = CORE_SEARCH_DOMAINS if core_only else SEARCH_DOMAINS
    else:
        tool["blocked_domains"] = _WEB_BLOCKED_DOMAINS
    return [tool]


def _tier_of(url: str) -> Tier:
    return "trusted" if trusted_domain_of(url) else "web"


def _publisher_of(url: str) -> str:
    """A readable name for a source chip, from the host."""
    from urllib.parse import urlparse

    return (urlparse(url).hostname or "").removeprefix("www.")


def _collect_sources(message) -> list[Source]:
    """Sources from the API's own structures — citations first, then results.

    Citations carry the sentence the model actually leaned on, so they are
    better evidence of what informed the answer than the raw result list.
    Both are read because a model can search without citing.
    """
    found: dict[str, Source] = {}

    def add(url: str, title: str, cited: str = "") -> None:
        if not url or not isinstance(url, str):
            return
        existing = found.get(url)
        if existing is None:
            found[url] = Source(url=url, title=title or "",
                                publisher=_publisher_of(url),
                                tier=_tier_of(url), via="search",
                                cited_text=cited or "")
        elif cited and not existing.cited_text:
            found[url] = existing.model_copy(update={"cited_text": cited})

    for block in getattr(message, "content", None) or []:
        if getattr(block, "type", None) == "text":
            for citation in getattr(block, "citations", None) or []:
                add(getattr(citation, "url", ""),
                    getattr(citation, "title", "") or "",
                    getattr(citation, "cited_text", "") or "")
        elif getattr(block, "type", None) == "web_search_tool_result":
            content = getattr(block, "content", None)
            # A search ERROR is a single object, not a list — the shape that
            # bit the old retrieval path.
            if isinstance(content, list):
                for result in content:
                    add(getattr(result, "url", ""),
                        getattr(result, "title", "") or "")
    return list(found.values())


def _searches_used(message) -> int:
    server_tools = getattr(getattr(message, "usage", None), "server_tool_use", None)
    return getattr(server_tools, "web_search_requests", 0) or 0


def _render_input(text: str, heard: str | None, factchecks: list) -> str:
    parts = [f"<message>\n{as_prompt_data(text, _MAX_INPUT_CHARS)}\n</message>"]
    if heard and heard.strip() and heard.strip() != text.strip():
        parts.append(
            "<heard>\n"
            + as_prompt_data(heard, _MAX_HEARD_CHARS)
            + "\n</heard>\n(The above was read by speech-to-text or OCR from "
              "what the person sent — it may contain mis-hearings.)"
        )
    if factchecks:
        lines = "\n".join(
            f"- {as_prompt_data(s.publisher, 100)}: "
            f"{as_prompt_data(s.title, 300)}"
            for s in factchecks[:_MAX_FACTCHECK_LINES]
        )
        parts.append(
            "<prior_factchecks>\n" + lines + "\n</prior_factchecks>\n"
            "(Prior published fact-checks the system found for this text. "
            "Treat them as strong evidence and say which publisher said what.)"
        )
    parts.append(
        "Check the message above and answer the sender directly, in their "
        "language."
    )
    return "\n\n".join(parts)


async def _run_pass(system: str, user_content: str, *, trusted: bool,
                    budget: int, emit: Emit, section_tier: Tier) -> PassResult:
    """One evidence tier: stream an answer, resuming paused turns.

    The search budget is enforced HERE rather than trusted to `max_uses`,
    which is per-REQUEST: a paused turn resumes as a new request and could
    lawfully be granted the full cap again. Each response's measured search
    count shrinks the next request's allowance, exactly as the old retrieval
    loop did.
    """
    result = PassResult()
    marker = MarkerFilter()
    messages: list[dict] = [{"role": "user", "content": user_content}]
    remaining = budget
    # `allowed_domains` is ALL-OR-NOTHING: one domain that blocks Anthropic's
    # crawler 400s the entire request (measured 2026-07-24). The whitelist was
    # widened well beyond the five domains that have actually been verified,
    # so a 400 falls back to the verified core rather than losing search
    # altogether. Coverage degrades for one request; nothing breaks.
    core_only = False

    for _ in range(_MAX_CONTINUATIONS):
        try:
            async with async_client.messages.stream(
                model=settings.chat_model,
                max_tokens=settings.chat_max_tokens,
                system=[{"type": "text", "text": system,
                         "cache_control": {"type": "ephemeral"}}],
                output_config={"effort": settings.chat_effort},
                tools=_tools(trusted, remaining, core_only=core_only),
                messages=messages,
            ) as stream:
                async for event in stream:
                    kind = getattr(event, "type", "")
                    if kind == "content_block_start":
                        block = getattr(event, "content_block", None)
                        if getattr(block, "type", "") == "server_tool_use":
                            await emit("status", {
                                "text": "Searching trusted fact-checkers…"
                                if trusted else "Searching the wider web…"})
                    elif kind == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        if getattr(delta, "type", "") == "text_delta":
                            visible = marker.feed(getattr(delta, "text", ""))
                            if visible:
                                result.markdown += visible
                                await emit("text", {"text": visible,
                                                    "tier": section_tier})
                final = await stream.get_final_message()
        except anthropic.APIError as exc:
            if (trusted and not core_only
                    and getattr(exc, "status_code", None) == 400):
                # Almost certainly a widened domain that blocks the crawler.
                print(f"[chat] domain list rejected ({exc}); retrying with the "
                      f"{len(CORE_SEARCH_DOMAINS)} verified core domains")
                core_only = True
                continue
            # A search-tool outage must not sink an answer we can still give.
            print(f"[chat] pass failed ({'trusted' if trusted else 'web'}): "
                  f"{type(exc).__name__}: {exc}")
            break

        # Streaming is NOT covered by usage.instrument(); without this the
        # report bills $0.00 while real money leaves.
        note_llm(settings.chat_model, getattr(final, "usage", None))

        result.sources.extend(_collect_sources(final))
        remaining -= _searches_used(final)

        stop = getattr(final, "stop_reason", None)
        if stop == "refusal":
            raise AnswerRefused(
                getattr(getattr(final, "stop_details", None), "category", "")
                or "refused"
            )
        if stop == "max_tokens":
            result.truncated = True
            break
        if stop == "pause_turn" and remaining > 0:
            messages.append({"role": "assistant", "content": final.content})
            continue
        if stop == "pause_turn":
            print(f"[chat] search budget spent ({budget}); not resuming")
        break

    tail = marker.flush()
    if tail:
        result.markdown += tail
        await emit("text", {"text": tail, "tier": section_tier})
    result.confidence, result.model_says_trusted = marker.parse()
    result.markdown = result.markdown.strip()

    # De-duplicate while preserving order.
    seen: set[str] = set()
    unique = []
    for source in result.sources:
        if source.url not in seen:
            seen.add(source.url)
            unique.append(source)
    result.sources = unique
    return result


async def answer(text: str, *, heard: str | None = None,
                 emit: Emit | None = None) -> ChatAnswer:
    """Fact-check `text` and return one chat-style answer.

    `emit(kind, data)` receives live events — `status`, `text`, `tier`,
    `source` — for the SSE stream. Omit it and the call is a plain await.
    """
    emit = emit or _noop_emit

    # Google Fact Check is FREE and returns prior published verdicts; it costs
    # nothing to hand the model that head start. Trust-filtered already.
    try:
        factchecks = await search_factcheck(text[:250])
    except Exception as exc:  # noqa: BLE001 — a free extra must never sink a check
        print(f"[chat] fact-check lookup failed: {type(exc).__name__}: {exc}")
        factchecks = []

    user_content = _render_input(text, heard, factchecks)
    prior = [
        Source(url=s.url, title=s.title, publisher=s.publisher,
               tier=_tier_of(s.url), via="factcheck")
        for s in factchecks
    ]

    await emit("status", {"text": "Checking trusted fact-checkers…"})
    first = await _run_pass(
        CHAT_SYSTEM_TRUSTED, user_content, trusted=True,
        budget=settings.chat_max_searches_trusted, emit=emit,
        section_tier="trusted",
    )

    sections = [AnswerSection(tier="trusted", markdown=first.markdown)]
    sources = prior + first.sources
    confidence = first.confidence
    truncated = first.truncated

    # Escalate only on a POSITIVE signal: the model said the trusted sources
    # were silent, or none of the evidence it produced was trusted. A missing
    # sentinel (model_says_trusted is None) is a parse failure, and a parse
    # failure must never buy a second pass.
    has_trusted = any(s.tier == "trusted" for s in sources)
    should_escalate = (
        settings.web_tier_enabled
        and not truncated
        and (first.model_says_trusted is False or not has_trusted)
        and first.model_says_trusted is not True
    )

    if should_escalate:
        await emit("tier", {"tier": "web"})
        await emit("status", {"text": "Nothing from the fact-checkers — "
                                      "searching the wider web…"})
        second = await _run_pass(
            CHAT_SYSTEM_WEB, user_content, trusted=False,
            budget=settings.chat_max_searches_web, emit=emit,
            section_tier="web",
        )
        if second.markdown:
            sections.append(AnswerSection(tier="web", markdown=second.markdown))
        sources = sources + second.sources
        if second.confidence is not None:
            confidence = second.confidence
        truncated = truncated or second.truncated

    seen: set[str] = set()
    unique_sources = []
    for source in sources:
        if source.url not in seen:
            seen.add(source.url)
            unique_sources.append(source)
    for source in unique_sources:
        await emit("source", source.model_dump())

    if any(s.tier == "trusted" for s in unique_sources):
        tier: Tier = "trusted"
    elif unique_sources:
        tier = "web"
    else:
        tier = "none"

    # An answer resting only on the general web must not display a
    # fact-checker-grade number, whatever the model claimed.
    cap = settings.web_tier_confidence_cap
    if tier != "trusted" and cap is not None and confidence is not None:
        confidence = min(confidence, cap)

    return ChatAnswer(
        sections=[s for s in sections if s.markdown.strip()],
        sources=unique_sources,
        confidence=confidence,
        tier=tier,
        truncated=truncated,
    )
