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
