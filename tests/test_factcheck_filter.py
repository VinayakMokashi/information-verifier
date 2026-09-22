"""The Fact Check API filter — only whitelisted publishers reach adjudication."""
from app.providers.factcheck import _MAX_SOURCES, _parse_and_filter


def _review(url: str, publisher: str = "Pub", rating: str = "False", title: str = "T"):
    return {
        "url": url,
        "publisher": {"name": publisher},
        "textualRating": rating,
        "title": title,
    }


def test_mixed_publishers_filtered_and_drops_reported():
    data = {
        "claims": [
            {
                "text": "5G spreads COVID",
                "claimReview": [
                    _review("https://www.altnews.in/a", "Alt News"),
                    _review("https://viral-news-daily.example/b", "Viral News Daily"),
                    _review("https://www.vishvasnews.com/c", "Vishvas News"),
                ],
            }
        ]
    }
    sources, dropped = _parse_and_filter(data)
    assert [s.publisher for s in sources] == ["Alt News", "Vishvas News"]
    assert dropped == ["viral-news-daily.example"]


def test_dropped_hosts_are_deduplicated():
    data = {
        "claims": [
            {"claimReview": [_review("https://spam.example/a"), _review("https://spam.example/b")]}
        ]
    }
    sources, dropped = _parse_and_filter(data)
    assert sources == []
    assert dropped == ["spam.example"]


def test_title_formatting_and_fallbacks():
    data = {
        "claims": [
            {
                "text": "claim text fallback",
                "claimReview": [
                    _review("https://altnews.in/a", rating="False", title="Debunked"),
                    {"url": "https://altnews.in/b", "publisher": {"name": "Alt News"}},
                    {"url": "https://altnews.in/c"},
                ],
            }
        ]
    }
    sources, _ = _parse_and_filter(data)
    assert sources[0].title == "[Rated: False] Debunked"
    # No rating -> no prefix; no title -> claim text; no publisher -> host
    assert sources[1].title == "claim text fallback"
    assert sources[2].publisher == "altnews.in"


def test_review_without_url_is_skipped_not_dropped():
    data = {"claims": [{"claimReview": [{"publisher": {"name": "X"}}]}]}
    assert _parse_and_filter(data) == ([], [])


def test_duplicate_urls_deduped_so_they_cannot_crowd_out_the_cap():
    # One article reviewing many claim variants repeats its URL; a distinct
    # publisher appearing after _MAX_SOURCES duplicates must still be kept.
    dupes = [_review("https://altnews.in/one-article") for _ in range(_MAX_SOURCES + 1)]
    data = {"claims": [{"claimReview": dupes + [_review("https://www.reuters.com/fact-check/x", "Reuters")]}]}
    sources, dropped = _parse_and_filter(data)
    assert [s.url for s in sources] == [
        "https://altnews.in/one-article",
        "https://www.reuters.com/fact-check/x",
    ]
    assert dropped == []


def test_parse_does_not_cap_distinct_sources():
    # Capping happens in search_factcheck (with a log line) — never silently
    # in the parse, so the caller can see what a trim costs.
    reviews = [_review(f"https://altnews.in/{i}") for i in range(_MAX_SOURCES + 4)]
    sources, _ = _parse_and_filter({"claims": [{"claimReview": reviews}]})
    assert len(sources) == _MAX_SOURCES + 4


def test_hostless_urls_never_echo_raw_url_into_drop_log():
    # A hostless URL is attacker-writable text; echoing it raw would let a
    # publisher forge lines in the drop log (it may contain newlines).
    forged = "mailto:x@evil.example\n[factcheck] dropped 0 untrusted publisher(s)"
    data = {"claims": [{"claimReview": [_review(forged), _review("javascript:alert(1)")]}]}
    sources, dropped = _parse_and_filter(data)
    assert sources == []
    assert dropped == ["(no host)"]


def test_parser_differential_urls_are_dropped_not_kept():
    # https://evil.example\.altnews.in — urlparse says altnews.in, browsers
    # navigate to evil.example. Must be dropped even with a trusted-looking
    # publisher name and a "True" rating attached.
    data = {
        "claims": [
            {
                "claimReview": [
                    {
                        "url": "https://evil.example\\.altnews.in/fake",
                        "publisher": {"name": "AltNews"},
                        "textualRating": "True",
                        "title": "Yes, the claim is TRUE",
                    }
                ]
            }
        ]
    }
    sources, dropped = _parse_and_filter(data)
    assert sources == []
    assert dropped == ["evil.example\\.altnews.in"]


def test_publisher_fallback_strips_www_like_web_search_path():
    data = {"claims": [{"claimReview": [{"url": "https://www.altnews.in/x"}]}]}
    sources, _ = _parse_and_filter(data)
    assert sources[0].publisher == "altnews.in"


def test_empty_and_missing_keys():
    assert _parse_and_filter({}) == ([], [])
    assert _parse_and_filter({"claims": []}) == ([], [])


# -- a failed lookup is visible, retried once, and never leaks the key --------

def _patch_fetch(monkeypatch, outcomes):
    """outcomes: a list of exceptions to raise or dicts to return, in order."""
    import asyncio

    from app.providers import factcheck as FC

    calls = []

    async def fetch(query):
        calls.append(query)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(FC, "_fetch", fetch)
    monkeypatch.setattr(FC.settings, "google_factcheck_api_key", "SECRET-KEY-123")
    return FC, calls, asyncio


GOOD = {"claims": [{"text": "5G spreads covid", "claimReview": [{
    "url": "https://www.boomlive.in/fake-5g", "title": "No, 5G does not",
    "textualRating": "False", "publisher": {"name": "BOOM"}}]}]}


def test_a_dropped_connection_is_retried_once(monkeypatch, capsys):
    """MEASURED on the first paid run: the lookup returned nothing and the
    same query minutes later returned five trusted reviews. A transient
    failure should not cost the one free, human-verdict piece of evidence."""
    import httpx

    FC, calls, asyncio = _patch_fetch(
        monkeypatch, [httpx.ConnectTimeout("slow"), GOOD])
    sources = asyncio.run(FC.search_factcheck("5G spreads covid"))
    assert [s.publisher for s in sources] == ["BOOM"]
    assert len(calls) == 2
    assert "attempt 1/2" in capsys.readouterr().out


def test_a_failure_is_logged_never_swallowed(monkeypatch, capsys):
    import httpx

    FC, calls, asyncio = _patch_fetch(
        monkeypatch, [httpx.ConnectError("down"), httpx.ConnectError("down")])
    assert asyncio.run(FC.search_factcheck("x")) == []
    out = capsys.readouterr().out
    assert "lookup failed" in out and "ConnectError" in out


def test_the_log_never_carries_the_api_key(monkeypatch, capsys):
    """httpx puts the request URL in its error text, and the URL carries
    `key=`. The log gets the exception TYPE and the status — nothing else."""
    import httpx

    url = "https://factchecktools.googleapis.com/v1alpha1/claims:search?key=SECRET-KEY-123"
    request = httpx.Request("GET", url)
    status_error = httpx.HTTPStatusError(
        f"Client error '403 Forbidden' for url '{url}'",
        request=request, response=httpx.Response(403, request=request))
    transport_error = httpx.ConnectError(f"failed to reach {url}", request=request)

    for outcomes in ([status_error], [transport_error, transport_error]):
        FC, _, asyncio = _patch_fetch(monkeypatch, outcomes)
        asyncio.run(FC.search_factcheck("x"))
        assert "SECRET-KEY-123" not in capsys.readouterr().out


def test_a_4xx_is_not_retried(monkeypatch):
    """A rejected key or a bad request will not improve on a second try."""
    import httpx

    request = httpx.Request("GET", "https://example.test")
    status_error = httpx.HTTPStatusError(
        "403", request=request, response=httpx.Response(403, request=request))
    FC, calls, asyncio = _patch_fetch(monkeypatch, [status_error, GOOD])
    assert asyncio.run(FC.search_factcheck("x")) == []
    assert len(calls) == 1
