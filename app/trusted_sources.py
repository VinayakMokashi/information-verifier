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

MEASURED 2026-09-22 with `scripts/crawl_probe.py`, before the first paid
check: apnews.com and factcheck.afp.com block the crawler. With them listed,
EVERY pass-1 request 400'd and fell back to the five core domains — the
general-purpose widening had never actually searched WHO, NASA or Snopes.
Both moved to FACTCHECK_ONLY (still trusted when cited). If a site starts
blocking later, `app/engine/chat.py` drops exactly the domains the 400 names
and keeps the rest; run the probe after any edit to this file.

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
    # factcheck.afp.com and apnews.com block the crawler (measured
    # 2026-09-22) — they live in FACTCHECK_ONLY_DOMAINS below.
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
    # Both block the crawler (measured 2026-09-22 — the 400 named
    # 'apnews.com' and 'factcheck.afp.com'). afp.com covers AFP Fact Check's
    # factcheck.afp.com subdomain: IFCN-certified, with an India desk, and
    # KEPT trusted — Vinayak left the call to me; see PROJECT_PLAN §7.
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


def domains_named_in(message: str, domains: list[str]) -> list[str]:
    """Which of `domains` an API error message names, e.g. the crawler 400:

        "The following domains are not accessible to our user agent:
         ['apnews.com', 'factcheck.afp.com']"   (measured 2026-09-22)

    Intersected with what was sent rather than parsed structurally — the
    wording is not a contract, the domain names are. Whole-name matches only,
    so 'nih.gov' is not found inside 'ncbi.nlm.nih.gov'.
    """
    lowered = message.lower()
    return [d for d in domains
            if re.search(r"(?<![a-z0-9.-])" + re.escape(d) + r"(?![a-z0-9.-])", lowered)]
