"""Google Fact Check Tools API — structured ClaimReview lookups.

Fact-checkers worldwide (Alt News, BOOM, Factly, AFP, AP, Full Fact...)
publish machine-readable ClaimReview markup that this free API aggregates. It returns a
prior human verdict for a claim when one exists — a strong signal that
complements live web search. Fails soft: no key or any error -> [].

Bounded trust applies here too: Google indexes ClaimReview from any
publisher worldwide, so results are filtered to TRUSTED_DOMAINS before
they can reach the model. Dropped reviews are logged, never silent —
recurring drops are the signal to consider widening the whitelist.
"""
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.hosts import strict_host
from app.models.answer import Source
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
            host = strict_host(url)
            if host is None or trusted_domain_of(url) is None:
                # Label drops by host only. Never echo the raw URL: it is
                # attacker-supplied and could forge lines in this audit log.
                try:
                    shown = urlparse(url).hostname or "(no host)"
                except ValueError:
                    shown = "(no host)"
                if shown not in dropped:
                    dropped.append(shown)
                continue
            # The host from the SAME parser the trust check used. A second
            # parser here (urlparse) once disagreed with it on a URL wrapped in
            # a no-break space, raised, and took every other fact-check with it.
            host = host.removeprefix("www.")
            # Google sometimes omits publisher.name — fall back to the host,
            # www-stripped like _publisher_of() on the web-search path, so one
            # outlet never shows up under two names in the same report.
            publisher = (review.get("publisher") or {}).get("name") or host
            rating = review.get("textualRating", "")
            base = review.get("title") or claim.get("text", "") or "Fact check"
            # Lead with the prior verdict so the model sees it explicitly.
            title = f"[Rated: {rating}] {base}" if rating else base
            sources.append(Source(url=url, title=title, publisher=publisher))
    return sources, dropped


async def _fetch(query: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            _ENDPOINT,
            # No languageCode: the old pipeline always queried in English
            # because an English pivot ran first. The chat engine has no
            # pivot, so pinning "en" would silently return nothing for a
            # Hindi or Spanish claim. Unset lets Google match any language
            # its ClaimReview index covers.
            params={
                "query": query,
                "key": settings.google_factcheck_api_key,
                "pageSize": _PAGE_SIZE,
            },
        )
    resp.raise_for_status()
    return resp.json()


async def search_factcheck(query: str) -> list[Source]:
    """Prior published fact-checks for `query`, trust-filtered. Never raises.

    MEASURED 2026-09-22, first paid run: this returned nothing, and the same
    query minutes later returned five trusted reviews (AP, AFP, BBC, BOOM,
    Full Fact). Every failure was swallowed without a word, so the cheapest
    evidence this service has — free, and a human verdict — vanished with no
    trace. Failures are now logged and a dropped connection is retried once.

    The log carries the exception TYPE and the HTTP status only: an httpx
    error's text includes the request URL, and that URL carries the API key.
    """
    if not settings.google_factcheck_api_key:
        return []
    data = None
    for attempt in (1, 2):
        try:
            data = await _fetch(query)
            break
        except httpx.HTTPStatusError as exc:
            print(f"[factcheck] lookup failed: HTTP {exc.response.status_code}")
            return []          # a 4xx will not improve on a retry
        except (httpx.TransportError, ValueError) as exc:
            print(f"[factcheck] lookup failed (attempt {attempt}/2): "
                  f"{type(exc).__name__}")
        except httpx.HTTPError as exc:
            print(f"[factcheck] lookup failed: {type(exc).__name__}")
            return []
    if data is None:
        return []  # fail soft — the engine still has web search

    sources, dropped = _parse_and_filter(data)
    if dropped:
        print(f"[factcheck] dropped {len(dropped)} untrusted publisher(s): "
              + ", ".join(dropped))
    if len(sources) > _MAX_SOURCES:
        print(f"[factcheck] trimming {len(sources) - _MAX_SOURCES} trusted "
              f"source(s) over the cap of {_MAX_SOURCES}")
        sources = sources[:_MAX_SOURCES]
    return sources
