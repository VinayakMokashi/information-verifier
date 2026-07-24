"""Google Fact Check Tools API — structured ClaimReview lookups.

Indian fact-checkers (AltNews, BOOM, Factly, Vishvas) publish machine-
readable ClaimReview markup that this free API aggregates. It returns a
prior human verdict for a claim when one exists — a strong signal that
complements live web search. Fails soft: no key or any error -> [].
"""
import httpx

from app.config import settings
from app.models.evidence import Source

_ENDPOINT = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


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
                    "pageSize": 5,
                },
            )
        resp.raise_for_status()
        data = resp.json()
    except (httpx.HTTPError, ValueError):
        return []  # fail soft — retrieval still has web search

    sources: list[Source] = []
    for claim in data.get("claims", []):
        for review in claim.get("claimReview", []):
            publisher = (review.get("publisher") or {}).get("name", "Unknown")
            rating = review.get("textualRating", "")
            base = review.get("title") or claim.get("text", "") or "Fact check"
            # Lead with the prior verdict so adjudication sees it explicitly.
            title = f"[Rated: {rating}] {base}" if rating else base
            url = review.get("url", "")
            if url:
                sources.append(Source(url=url, title=title, publisher=publisher))
    return sources
