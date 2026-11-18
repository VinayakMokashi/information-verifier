"""Nothing to check, nothing spent. Free.

MEASURED 2026-10-10: "hi" bought a full check (~8,000 tokens of fixed setup,
$0.03-0.05) and one of the day's capped slots. The filter is deliberately
narrow — turning away a real claim is worse than paying for a greeting.
"""
import pytest

from app.config import settings
from app.engine.triage import nothing_to_check, only_unopenable_links


@pytest.mark.parametrize("text", [
    "hi", "Hi!!", "hiii", "  ok  ", "Ok.", "thanks 🙏", "Thank you so much!",
    "👍", "🙏🙏", "...", "", "kya hua?", "Good morning", "you're welcome",
    "test", "नमस्ते", "धन्यवाद 🙏", "ठीक है", "हाँ",
])
def test_small_talk_is_nothing_to_check(text):
    assert nothing_to_check(text)


@pytest.mark.parametrize("text", [
    "5G causes covid", "Modi resigned", "No vaccine works",
    "hi, is it true that 5G causes covid?",
    "ok so NASA says 6 days of darkness", "Thanks to 5G, covid spread",
    "चाँद पर पानी है", "नहीं, चाँद पर पानी नहीं है",
    "地球是平的",        # a whole claim with no spaces: no length rule, ever
])
def test_a_real_claim_is_never_turned_away(text):
    assert not nothing_to_check(text)


def test_a_greeting_costs_nothing_and_uses_no_slot(client, monkeypatch):
    import scripts.fake_stages as F
    from app.api import limits

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    resp = client.post("/api/v1/verify/text", json={"text": "hi 🙏"})
    assert resp.status_code == 422
    assert "greeting" in resp.json()["detail"]
    assert limits.used_today() == 0
    assert F.CALLS["answer"] == 0


def test_a_short_real_claim_still_goes_through(client):
    import scripts.fake_stages as F

    resp = client.post("/api/v1/verify/text", json={"text": "5G causes covid"})
    assert resp.status_code == 202
    client.get(f"/api/v1/reports/{resp.json()['job_id']}")
    assert F.CALLS["answer"] == 1


# -- a link nobody can open (2026-11-18) ----------------------------------------
# Friends reported answers that "say can't read link": a link to a site the
# engine cannot open, sent as text, bought a check (~$0.04) whose whole answer
# was that it could not open it. Said for free now, with what works instead.
# Still narrow: any words beyond a greeting or "is this true?" are checked.

@pytest.mark.parametrize("text", [
    "https://www.ndtv.com/india-news/free-laptop-scheme-12345",
    "Is this true? https://x.com/someone/status/1890",
    "Kya ye sach hai?? https://t.me/somechannel/42",
    "क्या यह सच है? https://example.com/news",
    "hi https://www.whatsapp.com/channel/abc",
    "www.ndtv.com/india-news/abc",
    "check this https://news.example/a 🙏",
])
def test_only_a_link_nobody_can_open_is_nothing_to_check(text):
    assert only_unopenable_links(text)


@pytest.mark.parametrize("text", [
    "https://www.instagram.com/p/DXyZ12abc/",           # a link the app reads
    "Is this true? https://youtu.be/abc",
    "5G causes covid",                                  # no link at all
    "https://www.ndtv.com/x Modi announced free laptops for every student",
    "Modi ne kaha sabko laptop milega https://www.ndtv.com/x",
    "Is this true that 5G spreads corona? https://example.com/a",
])
def test_a_link_with_a_claim_or_a_readable_link_is_not_turned_away(text):
    assert not only_unopenable_links(text)


def test_a_link_nobody_can_open_costs_nothing_and_says_what_works(client, monkeypatch):
    import scripts.fake_stages as F
    from app.api import limits

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    resp = client.post("/api/v1/verify/text",
                       json={"text": "Is this true? https://x.com/someone/status/1890"})
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "screenshot" in detail and "Instagram" in detail
    assert limits.used_today() == 0
    assert F.CALLS["answer"] == 0
