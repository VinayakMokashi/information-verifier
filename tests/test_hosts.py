"""One host parser for both security boundaries. Free.

`trusted_domain_of` (may this URL be labelled a fact-checker?) and
`allowed_link_host` (may the SERVER fetch this URL?) used to parse hosts
separately and had drifted. Measured against the previous code, 2026-09-22:

  * "https://evil..altnews.in/x" — an empty label — was TRUSTED as Alt News:
    it ends with ".altnews.in". No such host can exist in DNS.
  * A trailing-dot host ("www.youtube.com.") was fetchable by one check and
    rejected by the other.
"""
import pytest

from app.hosts import strict_host, valid_hostname
from app.providers.links import allowed_link_host
from app.trusted_sources import trusted_domain_of


def test_an_empty_label_is_not_a_trusted_subdomain():
    assert trusted_domain_of("https://evil..altnews.in/x") is None
    assert trusted_domain_of("https://.altnews.in/x") is None


def test_one_trailing_dot_is_the_same_host_in_both_checks():
    """DNS treats "altnews.in." as altnews.in; now both checks agree."""
    assert trusted_domain_of("https://altnews.in./x") == "altnews.in"
    assert allowed_link_host("https://www.youtube.com./shorts/x") == "www.youtube.com"
    # ...but only one: a second dot is an empty label.
    assert trusted_domain_of("https://altnews.in../x") is None
    assert allowed_link_host("https://www.youtube.com../shorts/x") is None


@pytest.mark.parametrize("host, ok", [
    ("altnews.in", True), ("hindi.boomlive.in", True),
    ("xn--80ak6aa92e.com", True),                 # punycode is ASCII: fine
    ("evil..altnews.in", False), ("-evil.altnews.in", False),
    ("evil-.altnews.in", False), ("evil_x.altnews.in", False),
    ("a" * 64 + ".com", False),                   # label over 63
    ("évil.com", False),                          # non-ASCII fails closed
    ("", False),
])
def test_hostname_grammar(host, ok):
    assert valid_hostname(host) is ok


TRICKY = [
    r"https://evil.example\.altnews.in/x",   # browsers cut at the backslash
    "https://evil.example .altnews.in/x",     # ...or the space
    r"https://evil.com\@altnews.in/x",       # userinfo in disguise
    "https://user:pass@altnews.in/x",
    "https://[::1]/x", "http://[", "https://", "", "not a url",
    "https://" + "a" * 2050 + ".com/",
]


@pytest.mark.parametrize("url", TRICKY)
def test_both_boundaries_refuse_the_same_tricks(url):
    """One parser, so a trick either works on both or on neither — and here,
    on neither."""
    assert strict_host(url) is None
    assert trusted_domain_of(url) is None
    assert allowed_link_host(url) is None


def test_the_fetcher_is_still_https_only_and_exact():
    """Sharing the parser must not loosen the fetch rule."""
    assert allowed_link_host("http://www.youtube.com/watch?v=x") is None
    assert allowed_link_host("https://youtube.com.evil.com/watch") is None
    assert strict_host("http://www.youtube.com/x") == "www.youtube.com"
