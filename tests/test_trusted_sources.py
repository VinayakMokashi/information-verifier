"""Domain matching is a security boundary — lookalike domains must not pass."""
import pytest

from app.trusted_sources import is_trusted_url, trusted_domain_of


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        # Exact hosts
        ("https://altnews.in/fake-5g-story", "altnews.in"),
        ("https://pib.gov.in/PressRelease.aspx", "pib.gov.in"),
        # Subdomains of a trusted domain
        ("https://www.boomlive.in/fact-check/x", "boomlive.in"),
        ("https://hindi.boomlive.in/fact-check/x", "boomlive.in"),
        ("https://telugu.factly.in/x", "factly.in"),
        # The subdomain entry wins for its own subtree; the rest of The Quint
        # matches the broader thequint.com entry (user-approved 2026-07-25)
        ("https://factcheck.thequint.com/story", "factcheck.thequint.com"),
        ("https://www.thequint.com/news/webqoof/story", "thequint.com"),
        # FACTCHECK_ONLY domains are trusted for citations
        ("https://www.vishvasnews.com/hindi/viral/x", "vishvasnews.com"),
        ("https://www.reuters.com/fact-check/x", "reuters.com"),
        ("https://english.factcrescendo.com/x", "factcrescendo.com"),
        ("https://fullfact.org/online/x", "fullfact.org"),
        ("https://www.snopes.com/fact-check/x", "snopes.com"),
        # Lookalikes must fail
        ("https://notaltnews.in/x", None),
        ("https://altnews.in.evil.com/x", None),
        ("https://factly.in.attacker.org/x", None),
        # Parser differentials: urlparse reads the host as altnews.in, but a
        # browser (WHATWG) cuts the authority at the backslash/space and
        # navigates to evil.example / evil.com. Must fail closed.
        ("https://evil.example\\.altnews.in/fake-fact-check", None),
        ("https://evil.example .altnews.in/x", None),
        ("https://evil.com\\@altnews.in/x", None),
        # Userinfo is never legitimate in a fact-check URL — reject all of it
        ("https://altnews.in@evil.com/x", None),
        ("https://user@altnews.in/x", None),
        # Only http(s) counts as trusted — no javascript:, data:, or
        # scheme-relative URLs in the citation list
        ("javascript://factly.in/%0aalert(1)", None),
        ("data://altnews.in/x", None),
        ("//altnews.in/x", None),
        ("ftp://altnews.in/x", None),
        ("http://altnews.in/x", "altnews.in"),
        # Publishers not on the whitelist stay untrusted
        ("https://www.politifact.com/x", None),
        ("https://leadstories.com/x", None),
        # Normalization: case and port
        ("HTTPS://WWW.ALTNEWS.IN/Story", "altnews.in"),
        ("https://altnews.in:8443/story", "altnews.in"),
        # Garbage in, None out — never an exception
        ("", None),
        ("not a url", None),
        ("https://", None),
        ("http://[", None),
    ],
)
def test_trusted_domain_of(url: str, expected: str | None):
    assert trusted_domain_of(url) == expected


def test_is_trusted_url_mirrors_domain_lookup():
    assert is_trusted_url("https://altnews.in/x")
    assert not is_trusted_url("https://politifact.com/x")
