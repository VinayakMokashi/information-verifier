"""The whitelist — what this service is willing to treat as authoritative.

Scope widened 2026-09-11 from "Indian political misinformation" to
general-purpose claim verification: health, science, history, finance,
technology and celebrity/viral claims, anywhere in the world. India stays
first-class (it is the home market and the Indian fact-checkers are
excellent), it is simply no longer the only case.

IMPORTANT — `allowed_domains` is all-or-nothing. Every domain passed to the
web_search tool must permit Anthropic's crawler; if even ONE blocks it, the
whole search request fails with HTTP 400 (measured 2026-07-24). That makes
widening this list genuinely risky, so it is split:

  * CORE_SEARCH_DOMAINS  — crawler access verified against the live API.
  * GLOBAL_SEARCH_CANDIDATES — added for general-purpose coverage, crawler
    access NOT yet verified.

`app/engine/chat.py` retries with CORE only if a search 400s, so an
unverified candidate degrades coverage for one request instead of breaking
search outright. `scripts/crawl_probe.py` promotes candidates once measured.

Curating this list is a trust decision, not a code change.

NOT included, deliberately: Wikipedia and other user-editable references. For
an uncontroversial fact they would be ideal, but this product exists for
claims someone is actively pushing — and an editable page is part of that
attack surface. They still surface in the general-web tier, labelled as such,
which is the honest placement.
"""
import re
from urllib.parse import urlparse

# Crawler access VERIFIED against the live API (2026-07-24).
CORE_SEARCH_DOMAINS: list[str] = [
    "altnews.in",
    "boomlive.in",
    "factly.in",
    "factcheck.thequint.com",
    "pib.gov.in",
]

# Added 2026-09-11 for general-purpose verification. Crawler access UNVERIFIED
# — see the module docstring for what happens if one of these blocks the
# crawler. Grouped by what they are authoritative ABOUT, because a health
# claim and an astronomy claim do not have the same best source.
GLOBAL_SEARCH_CANDIDATES: list[str] = [
    # -- Fact-checkers (IFCN signatories and equivalents) ------------------
    "snopes.com",
    "politifact.com",
    "factcheck.org",
    "fullfact.org",
    "leadstories.com",
    "checkyourfact.com",
    "africacheck.org",
    "factcheck.afp.com",
    "apnews.com",
    "factcheckni.org",
    "truthorfiction.com",
    # -- Health and medicine ----------------------------------------------
    "who.int",
    "cdc.gov",
    "nih.gov",
    "ncbi.nlm.nih.gov",
    "nhs.uk",
    "cochrane.org",
    "mayoclinic.org",
    "healthfeedback.org",
    "ema.europa.eu",
    "fda.gov",
    # -- Science, climate, space ------------------------------------------
    "nasa.gov",
    "noaa.gov",
    "esa.int",
    "usgs.gov",
    "sciencefeedback.co",
    "climatefeedback.org",
    "nature.com",
    "science.org",
    "arxiv.org",
    # -- Governments, courts, multilaterals --------------------------------
    "un.org",
    "europa.eu",
    "gov.uk",
    "worldbank.org",
    "imf.org",
    "oecd.org",
    "sec.gov",
    "rbi.org.in",
    "supremecourt.gov.in",
    "eci.gov.in",
]

# Trusted for citations but reached via the Google Fact Check API, NOT web
# search — either they block the Anthropic crawler (verified 2026-07-24) or
# they have not been crawler-smoke-tested.
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
    "factcrescendo.com",  # IFCN-certified, India
    # Added 2026-09-11 with the general-purpose widening:
    "bbc.com",
    "bbc.co.uk",
    "apnews.com",
    "afp.com",
    "dw.com",
    "npr.org",
    "pbs.org",
]

# Offered to web_search. Order is stable so the prompt cache prefix is too.
SEARCH_DOMAINS: list[str] = CORE_SEARCH_DOMAINS + GLOBAL_SEARCH_CANDIDATES

# Everything we treat as trustworthy. Enforced two ways: web search via
# allowed_domains (server-side) and every returned URL via trusted_domain_of.
TRUSTED_DOMAINS: list[str] = sorted(
    set(SEARCH_DOMAINS) | set(FACTCHECK_ONLY_DOMAINS)
)


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
