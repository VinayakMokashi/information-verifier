"""FREE whitelist-curation probe for the Google Fact Check API. Costs $0.

No Anthropic calls — only the free Google Fact Check API. Shows every
ClaimReview Google returns for a query and whether the trust filter KEEPs or
DROPs it. If a good publisher keeps showing up as DROP, that's the signal to
consider a whitelist entry in app/trusted_sources.py.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\factcheck_probe.py
    .venv\\Scripts\\python.exe scripts\\factcheck_probe.py "your claim here"
"""
import asyncio
import os
import sys
from urllib.parse import urlparse

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.providers.factcheck import _ENDPOINT, _PAGE_SIZE  # noqa: E402
from app.trusted_sources import trusted_domain_of  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402


async def main() -> None:
    force_utf8_stdout()   # fact-check titles arrive in any language
    if not settings.google_factcheck_api_key:
        print("No GOOGLE_FACTCHECK_API_KEY found in .env. Aborting (no cost anyway).")
        return

    query = sys.argv[1] if len(sys.argv) > 1 else "5G spreads coronavirus"
    print(f">> FREE probe — Google Fact Check API only, no Anthropic calls.")
    print(f">> Query: {query}\n")

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

    kept = dropped = 0
    for claim in resp.json().get("claims", []):
        for review in claim.get("claimReview", []):
            url = review.get("url", "")
            if not url:
                continue
            host = urlparse(url).hostname or "?"
            publisher = (review.get("publisher") or {}).get("name", "Unknown")
            rating = review.get("textualRating", "-")
            verdict = trusted_domain_of(url)
            if verdict:
                kept += 1
                print(f"  KEEP  {host:<28} {publisher:<22} [{rating}]")
            else:
                dropped += 1
                print(f"  DROP  {host:<28} {publisher:<22} [{rating}]")

    print(f"\n>> {kept} kept, {dropped} dropped by the trust filter.")
    if not kept and not dropped:
        print(">> Google returned no ClaimReview results for this query.")


if __name__ == "__main__":
    asyncio.run(main())
