"""The whitelist.

IMPORTANT — allowed_domains is all-or-nothing. The domains passed to the
web_search tool's `allowed_domains` must ALL permit Anthropic's crawler. If
even one blocks it, the ENTIRE search request fails with HTTP 400.

Several trusted Indian news sites (Reuters, PTI, The Hindu, India Today,
Vishvas News) block the Anthropic crawler, so they CANNOT be used with web
search. They remain reachable through the Google Fact Check API, which indexes
their ClaimReview markup and does not depend on our crawler.

Curating this list is a trust decision, not a code change. When you add a
source, put it in SEARCH_DOMAINS only after confirming the crawler can reach
it (a quick smoke test against web search will 400 if it can't).
"""

# Crawler-accessible -> safe for web_search `allowed_domains`.
SEARCH_DOMAINS: list[str] = [
    "altnews.in",
    "boomlive.in",
    "factly.in",
    "factcheck.thequint.com",
    "pib.gov.in",
]

# Trusted but block the Anthropic crawler. Reached via the Google Fact Check
# API, NOT web search. Kept here for documentation and citation-trust checks.
FACTCHECK_ONLY_DOMAINS: list[str] = [
    "reuters.com",
    "ptinews.com",
    "thehindu.com",
    "indiatoday.in",
    "vishvasnews.com",
]

# Everything we treat as trustworthy, for reference / future validation.
TRUSTED_DOMAINS: list[str] = SEARCH_DOMAINS + FACTCHECK_ONLY_DOMAINS
