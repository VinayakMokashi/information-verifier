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
    # About PEOPLE, not money: the $1 budget would end these first (five
    # $0.20 reservations fill it). tests/test_budget.py covers the money.
    monkeypatch.setattr(settings, "daily_budget_usd", 1000.0)
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
    assert limits.reserve(_bot(1), token="first")
    with pytest.raises(HTTPException) as busy:
        limits.reserve(_bot(1))
    assert busy.value.status_code == 429 and "already" in busy.value.detail
    assert limits.used_today() == 1             # the refusal took no slot
    assert limits.reserve(_bot(2))              # one person never blocks another
    limits.release("tg:1", "first")
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
        day = limits.reserve(r, token="attempt")
        limits.refund(r, day)
        limits.release(limits.subject_of(r), "attempt")
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
    # all but this address's in-flight allowance (an IPv4 address is shared
    # under carrier NAT — review R9) are refused at once. Measure at
    # whichever comes first.
    running = settings.in_flight_by_kind["ip"]
    wait_for(lambda: len(codes) == 5 - running or inside[0] == 5)
    held = limits.used_today()
    try:
        victim_got_in = limits.reserve(_req("198.51.100.99")) is not None
    except HTTPException:
        victim_got_in = False
    gate.set()
    for t in threads:
        t.join(15)

    # Was `== 1` (one visitor, one held slot). Since review R1 a link's FREE
    # resolve holds no slot at all — only the person's place in line.
    assert held == 0, f"one visitor's pending resolve held {held} of the day's 5 slots"
    assert victim_got_in, "someone else was locked out while they were held"
    assert codes.count(429) == 5 - running
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


def test_a_release_must_name_its_claim(limiting):
    """R11's rule in the signature. Re-checking R11, the old call shape —
    release(subject), no token — still freed the OLDEST entry: a check past
    the TTL, ending late, freed the next check's place, and a third ran
    beside it (the reviewer's scenario, reproduced against the fix). Every
    caller passed a token, but one that forgot would bring R11 back without
    a sound; now it cannot be called that way. A None token frees nothing."""
    with pytest.raises(TypeError):
        limits.release("tg:1")
    assert limits.reserve(_bot(1), token="mine")
    limits.release("tg:1", None)
    assert limits._in_flight["tg:1"], "a release with no token freed someone's place"


def test_the_tables_are_cleared_with_the_rest():
    limits._in_flight["tg:9"] = [1.0]
    limits.reset()
    assert limits._in_flight == {}


# -- a daily allowance per person (Vinayak, 2026-10-15) ------------------------
# 5 paid checks a day per Telegram user (and per WhatsApp number, to come);
# web visitors by address until device cookies exist: an IPv6 /64 is one
# phone, an IPv4 address is shared by many under carrier NAT.

def _paid(request):
    """One check that went ahead and was paid for: claimed, then ended."""
    day = limits.reserve(request, token="paid")
    limits.release(limits.subject_of(request), "paid")
    return day


def test_a_telegram_user_gets_five_paid_checks_a_day(limiting):
    for _ in range(5):
        assert _paid(_bot(1))
    with pytest.raises(HTTPException) as today:
        limits.reserve(_bot(1))
    assert today.value.status_code == 429 and "today" in today.value.detail
    assert limits.used_today() == 5             # the refusal took no slot
    assert _paid(_bot(2))                       # everyone else keeps theirs


def test_a_refused_check_does_not_use_the_persons_allowance(limiting):
    for _ in range(5):
        request = _bot(1)
        day = limits.reserve(request, token="refused")
        limits.refund(request, day)             # refused before any spend
        limits.release("tg:1", "refused")
    assert _paid(_bot(1))


def test_a_free_cache_hit_gives_the_persons_check_back(limiting):
    for _ in range(5):
        day = _paid(_bot(1))
    limits.give_back_person("tg:1", day)        # the last one cost $0
    assert _paid(_bot(1))


def test_the_allowance_depends_on_who_is_asking(limiting, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_hour", 1000)
    v4 = _req("198.51.100.4")
    for _ in range(settings.person_daily_limits["ip"]):
        assert _paid(v4)
    with pytest.raises(HTTPException):
        limits.reserve(v4)
    v6 = _req("2401:4900:1c2a:5b10::1")
    for _ in range(settings.person_daily_limits["ip6"]):
        assert _paid(v6)
    with pytest.raises(HTTPException):
        limits.reserve(v6)


def test_a_new_day_brings_a_new_allowance(limiting, monkeypatch):
    for _ in range(5):
        assert _paid(_bot(1))
    monkeypatch.setattr(limits, "today", lambda: "2099-01-01")
    assert _paid(_bot(1))
    assert set(limits._person_today) == {"tg:1"}    # yesterday is forgotten


def test_the_allowances_match_the_decision():
    """Pinned: these are Vinayak's numbers (2026-10-15), not tuning knobs."""
    assert settings.person_daily_limits["tg"] == 5
    assert settings.person_daily_limits["wa"] == 5
    assert settings.person_daily_limits["dev"] == 3


# -- who asked is forgotten, not only never written down (2026-10-16) ---------
# The privacy notice says the counts behind the limits are cleared after the
# day they count. FOUND while drafting it: a subject's hourly record left
# memory only when 512 others pushed it out or the server restarted — weeks,
# for an IP address, on a server meant to stay up.

@pytest.fixture()
def clock(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(limits, "_now", lambda: now[0])
    return now


def test_idle_people_are_forgotten_after_their_day(limiting, clock, monkeypatch):
    _paid(_req("203.0.113.7"))
    _paid(_bot(1))
    limits.reserve(_bot(3), token="hung")        # never ended: past its TTL below
    assert limits._per_client and limits._person_today and limits._in_flight
    clock[0] += max(3601, settings.in_flight_ttl_s + 1)
    monkeypatch.setattr(limits, "today", lambda: "2099-01-01")
    assert limits.forget_idle() > 0
    assert (limits._per_client, limits._person_today, limits._in_flight) == ({}, {}, {})


def test_an_hour_later_only_the_hourly_record_goes(limiting, clock):
    _paid(_bot(1))
    clock[0] += 3601
    limits.forget_idle()
    assert "tg:1" not in limits._per_client
    assert limits._person_today.get("tg:1") == 1  # today's allowance still counts


def test_nothing_the_limits_still_use_is_forgotten(limiting, clock):
    _paid(_bot(1))
    limits.reserve(_bot(2), token="running")
    clock[0] += 60
    assert limits.forget_idle() == 0
    assert "tg:1" in limits._per_client and limits._person_today.get("tg:1") == 1
    assert limits._in_flight.get("tg:2")
    limits.release("tg:2", "running")


def test_the_housekeeping_loop_forgets_idle_people(monkeypatch):
    import asyncio
    import contextlib

    import app.main as M
    import app.store.repository as repository

    calls = []
    monkeypatch.setattr(M, "_HOUSEKEEPING_EVERY_S", 0)
    monkeypatch.setattr(repository, "housekeeping", lambda: {})
    monkeypatch.setattr(limits, "forget_idle", lambda: calls.append(1) or 0)

    async def one_round():
        task = asyncio.create_task(M._housekeeping_loop())
        for _ in range(200):                     # bounded: 2 s at most
            if calls:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(one_round())
    assert calls, "the housekeeping loop never forgot anyone"


# -- review R11, R6 (2026-10-15): release exactly one's own place, and in time --

def test_a_late_release_frees_only_its_own_place(limiting, monkeypatch):
    """REPRODUCED (review R11): check 1 hung past the TTL, check 2 was
    granted, and check 1's late release popped check 2's entry — so check 3
    ran beside check 2, the thing the rule forbids."""
    clock = [1000.0]
    monkeypatch.setattr(limits, "_now", lambda: clock[0])
    assert limits.reserve(_bot(1), token="first")
    clock[0] += settings.in_flight_ttl_s + 1
    assert limits.reserve(_bot(1), token="second")    # the first one hung
    clock[0] += 1
    limits.release("tg:1", "first")                   # ...and ends late
    with pytest.raises(HTTPException) as busy:
        limits.reserve(_bot(1), token="third")
    assert "already" in busy.value.detail             # the second still runs
    limits.release("tg:1", "second")
    assert limits.reserve(_bot(1), token="third")


def test_releasing_twice_is_harmless(limiting):
    assert limits.reserve(_bot(1), token="a")
    limits.release("tg:1", "a")
    limits.release("tg:1", "a")                       # the backstop, after the early one
    assert limits._in_flight == {}


def test_a_person_is_released_before_their_answer_becomes_visible():
    """REPRODUCED (review R6, real headless Chrome): run_check saved the
    COMPLETE answer, and the person was released only after the ledger and
    the settling — so a client that polled COMPLETE and sent its next
    message was told it "already had a check running"."""
    import asyncio

    import scripts.fake_stages as F
    from app.engine import chat as C
    from app.engine.job import run_check
    from app.models.answer import Answer, JobStatus

    order = []

    class Repo:
        class cache:
            @staticmethod
            def get(key):
                return None

            @staticmethod
            def put(*a):
                return None

        class ledger:
            @staticmethod
            def record(*a):
                return None

        def __init__(self):
            self.row = Answer(job_id="j", status=JobStatus.QUEUED,
                              created_at="2026-10-15T00:00:00Z")

        def get(self, job_id):
            return self.row

        def save(self, answer):
            order.append(("save", answer.status.value))

    async def go():
        real = C.answer
        C.answer = F.fake_answer
        try:
            await run_check("j", "5G spreads corona", Repo(),
                            on_finished=lambda: order.append(("released", None)))
        finally:
            C.answer = real

    asyncio.run(go())
    complete = order.index(("save", "COMPLETE"))
    assert ("released", None) in order[:complete]


# -- review R9, R14 (2026-10-15) ------------------------------------------------

def test_strangers_behind_one_ipv4_address_are_not_one_person(limiting):
    """REPRODUCED (review R9): under carrier NAT or office Wi-Fi many people
    share one public IPv4 address, and while one had a check running every
    other was told "you already have a check running" — false for them."""
    a, b, c, d = (_req("198.51.100.30") for _ in range(4))
    assert limits.reserve(a, token="a")
    assert limits.reserve(b, token="b")                 # someone else, same address
    assert limits.reserve(c, token="c")
    with pytest.raises(HTTPException):                  # still a brake
        limits.reserve(d, token="d")


def test_an_ipv6_64_is_still_one_phone(limiting):
    phone = "2401:4900:1c2a:5b10::1"
    assert limits.reserve(_req(phone), token="a")
    with pytest.raises(HTTPException) as busy:
        limits.reserve(_req(phone), token="b")
    assert "already" in busy.value.detail


def test_free_repeats_still_count_toward_the_hour(limiting, monkeypatch):
    """REPRODUCED (review R14): a cached answer was served before every
    per-person bound, so one visitor made 600 job rows and 600 in-memory
    streams in 44 s. Free of money, not of the abuse guard."""
    monkeypatch.setattr(settings, "max_checks_per_hour", 3)
    first = limiting.post("/api/v1/verify/text", json={"text": "The same forward"})
    assert first.status_code == 202
    codes = [limiting.post("/api/v1/verify/text", json={"text": "The same forward"}).status_code
             for _ in range(4)]
    assert codes == [202, 202, 429, 429]                # 3 an hour, the first included


# -- review R15 (2026-10-15): the limiter's lock guards memory, never the database

@pytest.mark.parametrize("claiming", ["reserve", "fund"])
def test_the_loop_never_waits_on_another_claims_database_write(limiting, monkeypatch,
                                                               claiming):
    """REPRODUCED (review R15, real uvicorn): a claim held limits._lock
    across its SQLite write, which waits up to the 30 s busy timeout when
    another writer has the database; release() and admit(), called ON THE
    EVENT LOOP, take the same lock — so every page, stream and poll froze
    (/health took ~7 s). Built so the old code FAILS in about a second
    rather than hanging for the busy timeout. Both claim paths — a text or
    image claims in one step (reserve), a link or upload funds after its
    free work (fund) — and every limiter call the routes make on the loop."""
    import sqlite3
    import threading

    in_the_write = threading.Event()
    real_take = limits._daily.take

    def take(day, cap):
        in_the_write.set()
        return real_take(day, cap)

    monkeypatch.setattr(limits._daily, "take", take)
    blocker = sqlite3.connect(settings.db_path, timeout=1)
    blocker.execute("BEGIN IMMEDIATE")          # another writer holds the database
    claimed = getattr(limits, claiming)
    claim = threading.Thread(
        target=lambda: _swallow(lambda: claimed(_req("198.51.100.40"))))
    claim.start()
    try:
        assert in_the_write.wait(10), "the claim never reached its write"
        done = threading.Event()

        def from_the_loop():
            limits.release("ip:203.0.113.9", "theirs")  # someone else's check ends
            limits.admit(_req("198.51.100.41"))  # someone sends a link
            limits.attempt(_req("198.51.100.42"))   # someone repeats a claim
            limits.give_back_person("ip:203.0.113.9", limits.today())  # a free hit
            done.set()

        threading.Thread(target=from_the_loop, daemon=True).start()
        in_time = done.wait(1.0)
    finally:
        blocker.rollback()                       # let everything finish, either way
        blocker.close()
        claim.join(40)
    assert in_time, "release()/admit() waited on another claim's database write"


def _swallow(call):
    try:
        call()
    except Exception:  # noqa: BLE001 — the claim's outcome is not the point
        pass
