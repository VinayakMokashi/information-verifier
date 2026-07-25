"""Google Fact Check Tools API — structured ClaimReview lookups.

Indian fact-checkers (AltNews, BOOM, Factly, Vishvas) publish machine-
readable ClaimReview markup that this free API aggregates. It returns a
prior human verdict for a claim when one exists — a strong signal that
complements live web search. Fails soft: no key or any error -> [].

Bounded trust applies here too: Google indexes ClaimReview from any
publisher worldwide, so results are filtered to TRUSTED_DOMAINS before
they can reach the adjudicator. Dropped reviews are logged, never silent —
recurring drops are the signal to consider widening the whitelist.
"""
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.models.evidence import Source
from app.trusted_sources import trusted_domain_of

_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"

# Ask for more claims than we expect to keep — the trust filter thins the
# results — then cap what we forward so the evidence note stays tight.
_PAGE_SIZE = 10
_MAX_SOURCES = 8


def _parse_and_filter(data: dict) -> tuple[list[Source], list[str]]:
    """Turn an API response into (trusted sources, dropped untrusted hosts).

    Sources are deduplicated by URL (one article often reviews several claim
    variants) but NOT capped here — the caller caps, so a duplicate can never
    crowd a distinct publisher out of the cap window.
    """
    sources: list[Source] = []
    seen_urls: set[str] = set()
    dropped: list[str] = []
    for claim in data.get("claims", []):
        for review in claim.get("claimReview", []):
            url = review.get("url", "")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            if trusted_domain_of(url) is None:
                # Label drops by host only. Never echo the raw URL: it is
                # attacker-supplied and could forge lines in this audit log.
                try:
                    host = urlparse(url).hostname or "(no host)"
                except ValueError:
                    host = "(no host)"
                if host not in dropped:
                    dropped.append(host)
                continue
            host = urlparse(url).hostname.removeprefix("www.")
            # Google sometimes omits publisher.name — fall back to the host,
            # www-stripped like _publisher_of() on the web-search path, so one
            # outlet never shows up under two names in the same report.
            publisher = (review.get("publisher") or {}).get("name") or host
            rating = review.get("textualRating", "")
            base = review.get("title") or claim.get("text", "") or "Fact check"
            # Lead with the prior verdict so adjudication sees it explicitly.
            title = f"[Rated: {rating}] {base}" if rating else base
            sources.append(Source(url=url, title=title, publisher=publisher))
    return sources, dropped


async def search_factcheck(query: str) -> list[Source]:
    if not settings.google_factcheck_api_key:
        return []
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                _ENDPOINT,
                params={
                    "query": query,
                    "key": settings.google_factcheck_api_key,
                    "languageCode": "en",
                    "pageSize": _PAGE_SIZE,
                },
            )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []  # fail soft — retrieval still has web search

    sources, dropped = _parse_and_filter(data)
    if dropped:
        print(f"[factcheck] dropped {len(dropped)} untrusted publisher(s): "
              + ", ".join(dropped))
    if len(sources) > _MAX_SOURCES:
        print(f"[factcheck] trimming {len(sources) - _MAX_SOURCES} trusted "
              f"source(s) over the cap of {_MAX_SOURCES}")
        sources = sources[:_MAX_SOURCES]
    return sources
