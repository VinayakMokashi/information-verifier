"""A check is counted per PERSON, not per connection. Free.

REPRODUCED 2026-10-15 (docs/research/2026-10-15/audit-security.md):
- every Telegram user reached the API as ONE client — the bot, on
  127.0.0.1 — so the per-visitor limit was one bucket for all of them;
- a refunded attempt erased its own hourly stamp, so it never counted;
- five concurrent slow link resolves from one visitor held all five daily
  slots while they ran, then were refunded: a free, repeatable lockout of
  everyone, leaving no job, no ledger row and no trace.

Now a check belongs to a SUBJECT: the person the bot names (honoured only
from this machine, the dashboard's own rule), else the visitor's address —
an IPv6 /64, which is one phone on Jio and Airtel. One check in flight per
subject, from the claim until the check ends, however it ends.
"""
import threading

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import limits
from app.config import settings


def _req(peer="203.0.113.7", headers=None, host="127.0.0.1:8000"):
    raw = [(b"host", host.encode())]
    raw += [(k.encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request({"type": "http", "client": (peer, 5555), "headers": raw})


def _bot(user_id):
    return _req("127.0.0.1", {"x-verifier-subject": f"tg:{user_id}"})


@pytest.fixture()
def limiting(client, monkeypatch):
    """The real limiter on this test's own database (the `client` fixture
    creates and points at it)."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_day", 50)
    monkeypatch.setattr(settings, "max_checks_per_hour", 10)
    limits.reset()
    return client


# -- who is asking -------------------------------------------------------------

def test_the_bot_names_the_person_and_only_this_machine_may():
    assert limits.subject_of(_bot(42)) == "tg:42"
    # From anywhere else the header is ignored: a visitor cannot pick a bucket.
    assert (limits.subject_of(_req("203.0.113.7", {"x-verifier-subject": "tg:42"}))
            == "ip:203.0.113.7")
    # Through the tunnel: a loopback peer, but a proxy header says "visitor".
    assert limits.subject_of(_req("127.0.0.1", {"x-verifier-subject": "tg:42",
                                                "cf-connecting-ip": "198.51.100.1"})) != "tg:42"
    # DNS rebinding: loopback and no proxy header, but someone else's Host.
    assert limits.subject_of(_req("127.0.0.1", {"x-verifier-subject": "tg:42"},
                                  host="evil.example")) != "tg:42"


@pytest.mark.parametrize("bad", ["tg:abc", "admin", "tg:1 tg:2", "ip:1.2.3.4", "tg:"])
def test_only_a_well_formed_subject_is_honoured(bad):
    assert limits.subject_of(_req("127.0.0.1", {"x-verifier-subject": bad})) == "ip:127.0.0.1"


def test_an_ipv6_visitor_is_one_bucket_per_64():
    a = limits.subject_of(_req("2401:4900:1c2a:5b10::1"))
    b = limits.subject_of(_req("2401:4900:1c2a:5b10:abcd::9"))
    c = limits.subject_of(_req("2401:4900:1c2a:5b11::1"))
    assert a == b != c
    assert limits.subject_of(_req("::ffff:203.0.113.7")) == "ip:203.0.113.7"


# -- one check in flight per person -------------------------------------------

def test_one_check_in_flight_per_person(limiting):
    assert limits.reserve(_bot(1))
    with pytest.raises(HTTPException) as busy:
        limits.reserve(_bot(1))
    assert busy.value.status_code == 429 and "already" in busy.value.detail
    assert limits.used_today() == 1             # the refusal took no slot
    assert limits.reserve(_bot(2))              # one person never blocks another
    limits.release("tg:1")
    assert limits.reserve(_bot(1))              # done -> the next may start


def test_a_check_that_never_ends_does_not_block_its_owner_forever(limiting, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(limits, "_now", lambda: clock[0])
    assert limits.reserve(_bot(1))
    clock[0] += settings.in_flight_ttl_s + 1    # a hung check, never released
    assert limits.reserve(_bot(1))


def test_a_refunded_attempt_still_counts_toward_the_hour(limiting, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_hour", 3)
    r = _req("198.51.100.4")
    for _ in range(3):
        day = limits.reserve(r)
        limits.refund(r, day)
        limits.release(limits.subject_of(r))
    with pytest.raises(HTTPException) as hour:
        limits.reserve(r)
    assert "this hour" in hour.value.detail
    assert limits.used_today() == 0             # the day's slots did come back


def test_slow_refunded_links_cannot_hold_everyones_slots(limiting, monkeypatch):
    """The reproduced lockout, end to end through the real route."""
    import app.api.routes as R

    import time

    monkeypatch.setattr(settings, "max_checks_per_day", 5)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    gate, guard = threading.Event(), threading.Lock()
    inside = [0]

    def slow_then_refused(url):
        with guard:
            inside[0] += 1
        gate.wait(30)
        raise R.LinkError("unsupported", "That video is too long.")   # refunded

    monkeypatch.setattr(R, "resolve_link", slow_then_refused)
    url = "https://www.youtube.com/watch?v=aaaaaaaaaaa"
    codes, details = [], []

    def submit():
        resp = limiting.post("/api/v1/verify/link", json={"url": url})
        codes.append(resp.status_code)
        details.append(resp.json().get("detail", ""))

    def wait_for(condition):                    # a condition, not a duration
        deadline = time.monotonic() + 15
        while not condition() and time.monotonic() < deadline:
            time.sleep(0.01)

    threads = [threading.Thread(target=submit) for _ in range(5)]
    threads[0].start()
    wait_for(lambda: inside[0] == 1)            # the first one is resolving
    for t in threads[1:]:
        t.start()
    # Before the fix all five claim a slot and sit in the resolve; after it,
    # the other four are refused at once. Measure at whichever comes first.
    wait_for(lambda: len(codes) == 4 or inside[0] == 5)
    held = limits.used_today()
    try:
        victim_got_in = limits.reserve(_req("198.51.100.99")) is not None
    except HTTPException:
        victim_got_in = False
    gate.set()
    for t in threads:
        t.join(15)

    assert held == 1, f"one visitor held {held} of the day's 5 slots"
    assert victim_got_in, "someone else was locked out while they were held"
    assert codes.count(429) == 4
    assert all("already" in d for c, d in zip(codes, details) if c == 429)


def test_a_check_that_fails_in_the_background_still_frees_its_person(limiting, monkeypatch):
    import app.api.routes as R

    async def unreadable(info):
        raise R.LinkError("other", "No speech or text could be read from that post.")

    monkeypatch.setattr(R, "gather_link_text", unreadable)
    url = "https://www.youtube.com/watch?v=bbbbbbbbbbb"
    assert limiting.post("/api/v1/verify/link", json={"url": url}).status_code == 202
    # The job failed behind the 202; the same visitor may send the next one.
    assert limiting.post("/api/v1/verify/link", json={"url": url}).status_code == 202


def test_the_tables_are_cleared_with_the_rest():
    limits._in_flight["tg:9"] = [1.0]
    limits.reset()
    assert limits._in_flight == {}
