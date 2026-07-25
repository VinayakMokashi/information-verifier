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
import re
from urllib.parse import urlparse

# Crawler-accessible -> safe for web_search `allowed_domains`.
SEARCH_DOMAINS: list[str] = [
    "altnews.in",
    "boomlive.in",
    "factly.in",
    "factcheck.thequint.com",
    "pib.gov.in",
]

# Trusted for citations but reached via the Google Fact Check API, NOT web
# search — either they block the Anthropic crawler (verified 2026-07-24) or
# they haven't been crawler-smoke-tested yet. A paid smoke test can promote
# an untested entry to SEARCH_DOMAINS.
FACTCHECK_ONLY_DOMAINS: list[str] = [
    # Block the crawler (verified):
    "reuters.com",
    "ptinews.com",
    "thehindu.com",
    "indiatoday.in",
    "vishvasnews.com",
    # Added 2026-07-25 (user-approved), crawler access untested:
    "thequint.com",       # ClaimReview lives on www.thequint.com (WebQoof),
                          # not the factcheck. subdomain used for web search
    "factcrescendo.com",  # IFCN-certified, India (english./marathi./hindi. subdomains)
    "fullfact.org",       # IFCN-certified, UK — covers global claims that reach India
    "snopes.com",         # US — covers global claims that reach India
]

# Everything we treat as trustworthy. Enforced: web search via allowed_domains
# (server-side), Fact Check API results via trusted_domain_of() below.
TRUSTED_DOMAINS: list[str] = SEARCH_DOMAINS + FACTCHECK_ONLY_DOMAINS


# A hostname is dot-separated labels of [a-z0-9-] only. Anything else (\ or
# space or unicode) means Python's urlparse and a browser's WHATWG parser can
# disagree about where the host ends — and that disagreement is exploitable.
_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")


def trusted_domain_of(url: str) -> str | None:
    """The whitelist entry a URL belongs to, or None if the URL is untrusted.

    Matching is by exact host or dot-boundary subdomain: hindi.boomlive.in
    matches boomlive.in, but a lookalike such as notboomlive.in does not.
    An entry that is itself a subdomain (factcheck.thequint.com) trusts only
    that subtree — the rest of thequint.com stays untrusted.

    This is a security boundary, so anything a browser could read differently
    than urlparse does fails closed: only http(s), no userinfo (rejects
    https://evil.com\\@altnews.in/, where browsers navigate to evil.com), and
    the host must be a plain hostname (rejects https://evil.example\\.altnews.in/,
    which browsers cut at the backslash).
    """
    try:
        parts = urlparse(url)
        host = parts.hostname  # lowercased; port and userinfo stripped
    except ValueError:
        return None
    if parts.scheme not in ("http", "https"):
        return None
    if parts.username is not None:  # no legitimate fact-check URL has userinfo
        return None
    if not host or not _HOST_RE.match(host):
        return None
    for domain in TRUSTED_DOMAINS:
        if host == domain or host.endswith("." + domain):
            return domain
    return None


def is_trusted_url(url: str) -> bool:
    return trusted_domain_of(url) is not None
