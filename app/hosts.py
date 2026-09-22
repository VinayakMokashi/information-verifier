"""The one place a URL's host is read. It is a security boundary, twice over.

Two checks depend on it:

  * `trusted_sources.trusted_domain_of` — may this URL be labelled a
    fact-checker? (A wrong answer puts false authority on a page.)
  * `providers.links.allowed_link_host` — may the SERVER fetch this URL?
    (A wrong answer is server-side request forgery.)

They used to parse separately, and had already drifted: one stripped a
trailing dot and the other rejected it, and their character rules differed.
Both also accepted EMPTY labels, so "evil..altnews.in" ended with
".altnews.in" and counted as a trusted subdomain. Now there is one parser, and
the next parser-differential trick is fixed once.

Fail closed on anything a browser might read differently than Python: a
backslash or space in the authority (browsers cut the host there), userinfo
(`https://evil.com\\@altnews.in/` navigates to evil.com), non-ASCII hosts,
empty or malformed labels, and oversized input.
"""
import re
from urllib.parse import urlsplit

_MAX_URL = 2048
_LABEL = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")


def valid_hostname(host: str) -> bool:
    """RFC 1123 hostname grammar: dot-separated labels of 1-63 chars from
    [a-z0-9-], not starting or ending with '-'; 253 chars at most."""
    if not host or len(host) > 253:
        return False
    return all(_LABEL.match(label) for label in host.split("."))


def strict_host(url: str, schemes: tuple[str, ...] = ("https", "http")) -> str | None:
    """The host this URL really points at, lowercased — or None. Never raises.

    Exactly ONE trailing dot is removed ("altnews.in." is the same host in
    DNS); a second is not, and fails the grammar like any empty label.
    """
    if not isinstance(url, str) or len(url) > _MAX_URL:
        return None
    try:
        parts = urlsplit(url.strip())
        if parts.scheme.lower() not in schemes:
            return None
        if parts.username is not None or parts.password is not None:
            return None
        host = (parts.hostname or "").lower()
    except ValueError:
        return None
    if host.endswith("."):
        host = host[:-1]
    return host if valid_hostname(host) else None
