"""The spending guard on the public share link."""
import pytest

from app.api import limits
from app.config import settings


@pytest.fixture()
def limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_hour", 3)
    monkeypatch.setattr(settings, "max_checks_per_day", 5)
    limits.reset()
    return client


_n = iter(range(10**9))


def _check(client, text=None):
    # A DIFFERENT message each time by default: since 2026-09-22 a repeat is a
    # free cache hit that hands its daily slot back, so identical submissions
    # no longer use the cap up — which is the point of the cache.
    return client.post("/api/v1/verify/text",
                       json={"text": text or f"5G claim number {next(_n)}"})


def test_per_visitor_hourly_limit(limited):
    for _ in range(3):
        assert _check(limited).status_code == 202
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "this hour" in blocked.json()["detail"]


def test_daily_limit_across_everyone(limited, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    for _ in range(5):
        assert _check(limited).status_code == 202
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "daily limit" in blocked.json()["detail"]


def test_reading_a_report_is_never_rate_limited(limited):
    job_id = _check(limited).json()["job_id"]
    for _ in range(20):
        assert limited.get(f"/api/v1/reports/{job_id}").status_code == 200


def test_disabled_by_default_for_local_use(client):
    # The `client` fixture leaves rate_limit_enabled False (see conftest).
    for _ in range(15):
        assert _check(client).status_code == 202


def test_a_rejection_that_came_after_paying_still_burns_quota(client, monkeypatch):
    """The hole this closes: /verify/image raises 422 ("no text in this image")
    AFTER a paid Opus vision call, and the refund handed the slot straight
    back — so a loop of blank images could bill all day with the counter
    still reading zero. A refund is only honest when nothing was bought."""
    from app.api import limits, routes as R

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_day", 100)
    limits.reset()

    async def ocr_that_costs_money_and_finds_nothing(image_bytes, media_type):
        return ""      # paid for, no text found -> the 422 below

    monkeypatch.setattr(R, "ocr_image", ocr_that_costs_money_and_finds_nothing)

    resp = client.post("/api/v1/verify/image",
                       files={"file": ("blank.png", b"\x89PNG", "image/png")})
    assert resp.status_code == 422
    assert limits.used_today() == 1, "a paid-for request must consume its quota slot"


def test_a_rejection_before_any_spending_is_refunded(client, monkeypatch):
    """The other direction still holds — a 415 costs nothing, so it is free."""
    from app.api import limits

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()

    resp = client.post("/api/v1/verify/image",
                       files={"file": ("notes.txt", b"hi", "text/plain")})
    assert resp.status_code == 415
    assert limits.used_today() == 0


def test_rejected_submissions_do_not_burn_quota(limited, monkeypatch):
    """A too-long paste costs nothing, so it must not consume a check."""
    monkeypatch.setattr(settings, "max_input_chars", 10)
    for _ in range(5):
        assert limited.post("/api/v1/verify/text",
                            json={"text": "x" * 100}).status_code == 413
    # Quota untouched: all 3 real checks still available (short, distinct
    # texts — the 10-char cap above applies to these too).
    for i in range(3):
        assert _check(limited, f"claim {i}").status_code == 202


def test_visitor_table_does_not_grow_without_bound(limited, monkeypatch):
    """Many one-off visitors must not leak memory on a long-running server."""
    from starlette.requests import Request

    monkeypatch.setattr(settings, "max_checks_per_day", 10_000)
    monkeypatch.setattr(settings, "daily_budget_usd", 10_000.0)   # memory, not money

    def fake_request(ip):
        return Request({"type": "http", "client": (ip, 1234), "headers": []})

    for i in range(600):
        limits.reserve(fake_request(f"10.0.{i // 256}.{i % 256}"))
    assert len(limits._per_client) <= 512


def test_concurrent_submissions_cannot_all_pass_the_same_empty_counter(limited, monkeypatch):
    """The cap must hold under parallel uploads, not just sequential ones.

    About the COUNTER's atomicity, so one-check-in-flight-per-person (which
    since 2026-10-15 refuses most of this burst on its own) is lifted here;
    tests/test_per_person.py covers that rule."""
    import concurrent.futures

    monkeypatch.setattr(settings, "max_in_flight_per_person", 100)

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        codes = [f.result().status_code
                 for f in [pool.submit(_check, limited) for _ in range(20)]]

    # 3 allowed per hour (see the `limited` fixture); the rest must be refused.
    assert codes.count(202) == 3
    assert codes.count(429) == 17


# -- the 2-a-day decision (Vinayak, 2026-09-22) -------------------------------

def test_the_daily_cap_is_now_a_backstop_under_the_dollar_budget():
    """Pinned because it is a DECISION, not a tuning knob: "lower it for now
    and do only 2 checks per day, just to be safe" (2026-09-22), raised to 5
    for quality testing on 2026-09-29 ("use 5 or even more if you want"), and
    replaced on 2026-10-15 by Vinayak's $1-a-day DOLLAR budget for strangers
    (tests/test_budget.py pins that). The count stays only as a backstop
    above it. Changing either should be a deliberate edit here AND in
    config.py, recorded in PROJECT_PLAN §7."""
    from app.config import Settings

    assert Settings.model_fields["max_checks_per_day"].default == 40
    assert Settings.model_fields["daily_budget_usd"].default == 1.0


def test_the_daily_cap_survives_a_restart(limited, monkeypatch):
    """The in-memory counter reset on every restart — under `--reload`, every
    saved file. Simulate one by wiping all in-process state: the count must
    still be there, and the cap must still hold."""
    monkeypatch.setattr(settings, "max_checks_per_day", 2)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    assert _check(limited).status_code == 202
    assert _check(limited).status_code == 202

    limits.reset()                       # everything a restart would lose

    assert limits.used_today() == 2
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "daily limit of 2 checks" in blocked.json()["detail"]


def test_the_refusal_says_when_it_resets(limited, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_day", 1)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    assert _check(limited).status_code == 202
    detail = _check(limited).json()["detail"]
    assert "daily limit of 1 check." in detail          # no "1 checks"
    assert "midnight India time" in detail


def test_a_day_is_the_operators_day_not_utcs(monkeypatch):
    """7 pm UTC on the 22nd is already 12:30 am on the 23rd in India. "2 a
    day" means his day."""
    import datetime as real

    class FrozenClock(real.datetime):
        @classmethod
        def now(cls, tz=None):
            return real.datetime(2026, 9, 22, 19, 0, tzinfo=real.timezone.utc)

    monkeypatch.setattr(limits, "datetime", FrozenClock)
    monkeypatch.setattr(settings, "day_boundary_utc_offset_min", 330)
    assert limits.today() == "2026-09-23"
    monkeypatch.setattr(settings, "day_boundary_utc_offset_min", 0)
    assert limits.today() == "2026-09-22"


def test_a_refund_goes_back_to_the_day_it_was_charged(limited, monkeypatch):
    """Found by review, reproduced: the rejection refund recomputed today(),
    so a bad link whose resolve straddled midnight took a slot from day D and
    gave one back to D+1 — and D+1 then granted 3 checks against a cap of 2.
    The day reserve() charged is the only day a refund may touch."""
    import datetime as real

    from app.api import routes
    from app.providers.links import LinkError
    from app.store.repository import DailyQuota

    now = {"t": real.datetime(2026, 9, 22, 18, 29, 58, tzinfo=real.timezone.utc)}

    class Clock(real.datetime):           # 23:59:58 in India when it arrives
        @classmethod
        def now(cls, tz=None):
            return now["t"]

    monkeypatch.setattr(limits, "datetime", Clock)
    monkeypatch.setattr(settings, "day_boundary_utc_offset_min", 330)
    quota = DailyQuota()

    def resolve_across_midnight(url):
        now["t"] = real.datetime(2026, 9, 22, 18, 30, 3, tzinfo=real.timezone.utc)
        assert quota.take("2026-09-23", 5)          # someone's check, new day
        raise LinkError("not_found", "No public post was found at that link.")

    monkeypatch.setattr(routes, "resolve_link", resolve_across_midnight)
    resp = limited.post("/api/v1/verify/link",
                        json={"url": "https://www.instagram.com/reel/abc/"})
    assert resp.status_code == 422
    assert quota.used("2026-09-22") == 0, "the slot it took was not given back"
    assert quota.used("2026-09-23") == 1, "the refund landed on the wrong day"


def test_claiming_a_slot_never_freezes_the_server(limited):
    """Found by review, measured: the daily slot was claimed by a SQLite
    write ON the event loop, so while any other writer held the database
    lock — a housekeeping DELETE, say — every request and every live answer
    stream froze with it (2 s in the review's run; up to the busy timeout in
    principle). Here a writer holds the lock for 0.8 s while a check is
    submitted; the loop has to keep running the whole time."""
    import asyncio
    import sqlite3
    import threading
    import time

    import httpx

    from app.main import app

    held = threading.Event()

    def hold_write_lock():
        conn = sqlite3.connect(settings.db_path, timeout=30)
        conn.execute("BEGIN IMMEDIATE")
        held.set()
        time.sleep(0.8)
        conn.commit()
        conn.close()

    async def scenario():
        threading.Thread(target=hold_write_lock, daemon=True).start()
        await asyncio.to_thread(held.wait, 5)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as http:
            submit = asyncio.create_task(
                http.post("/api/v1/verify/text", json={"text": "a claim, mid-lock"}))
            ticks, until = 0, time.monotonic() + 0.4
            while time.monotonic() < until:          # the lock is held throughout
                await asyncio.sleep(0.01)
                ticks += 1
            resp = await submit
        return ticks, resp.status_code

    ticks, status = asyncio.run(scenario())
    assert status == 202
    assert ticks >= 10, f"the event loop froze: {ticks} ticks in 0.4 s"


def test_a_burst_of_claims_cannot_stall_the_answers(limited):
    """Found by the review of that fix, measured: moving the claim into
    asyncio's DEFAULT pool traded a frozen loop for a full pool. A burst of
    claims while a writer held the database filled every worker, and
    GET /reports — the only way an answer reaches the page or the bot — is a
    thread call too, so answers stalled for the whole 30 s busy timeout."""
    import asyncio
    import sqlite3
    import threading
    import time

    import httpx

    from app.main import app

    held = threading.Event()

    def hold_write_lock():
        conn = sqlite3.connect(settings.db_path, timeout=30)
        conn.execute("BEGIN IMMEDIATE")
        held.set()
        time.sleep(2.5)
        conn.commit()
        conn.close()

    async def scenario():
        threading.Thread(target=hold_write_lock, daemon=True).start()
        await asyncio.to_thread(held.wait, 5)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as http:
            burst = [asyncio.create_task(
                http.post("/api/v1/verify/text", json={"text": f"claim {i}"}))
                for i in range(25)]
            await asyncio.sleep(0)                   # let them reach the claim
            started = time.monotonic()
            report = await http.get("/api/v1/reports/" + "0" * 32)
            took = time.monotonic() - started
            for task in burst:
                task.cancel()
            await asyncio.gather(*burst, return_exceptions=True)
        return took, report.status_code

    took, status = asyncio.run(scenario())
    assert status == 404                             # the read itself ran
    assert took < 1.0, f"reading an answer waited {took:.1f}s behind the claims"


def test_a_crash_that_never_spent_anything_gives_the_slot_back(limited, monkeypatch):
    """Found by review, measured: only an HTTPException was refunded. A
    database error inside the route — or a request cancelled at shutdown —
    burned half the day's budget with nothing bought, no job row, and no
    line in the log to explain where the check went."""
    from app.api import routes

    async def boom(*a, **kw):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(routes, "_new_job", boom)
    with pytest.raises(RuntimeError):
        limited.post("/api/v1/verify/text", json={"text": "a claim"})
    assert limits.used_today() == 0


def test_a_submission_cancelled_mid_claim_gives_its_slot_back(limited, monkeypatch):
    """The cancellation lands while the claim is still in flight, so the
    route body never runs and cannot refund. The claim finishes in the
    limiter's pool anyway — and hands the slot straight back from there,
    beyond the reach of the dying event loop (found by review, measured:
    a cancelled submission silently spent one of the day's two checks)."""
    import asyncio
    import time

    import httpx

    from app.api import limits as L
    from app.main import app

    real = L.reserve

    def slow_reserve(request, subject=None, kind="text", mode="full", token=None):
        time.sleep(0.4)                  # a contended write
        return real(request, subject, kind, mode, token)

    monkeypatch.setattr(L, "reserve", slow_reserve)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as http:
            task = asyncio.create_task(
                http.post("/api/v1/verify/text", json={"text": "cancelled claim"}))
            await asyncio.sleep(0.1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        for _ in range(50):              # the rollback runs in the pool thread
            if limits.used_today() == 0 and not limits._in_flight:
                return 0
            await asyncio.sleep(0.05)
        return limits.used_today()

    assert asyncio.run(scenario()) == 0
    # ...and the person is not left "in flight" for the TTL: a cancelled
    # submission must not lock its own sender out of the next check.
    assert limits._in_flight == {}


@pytest.mark.parametrize("phase", ["claim", "fund"])
def test_a_cancelled_claims_rollback_never_runs_on_the_event_loop(limited, monkeypatch,
                                                                  phase):
    """R15's rule — no SQLite write on the event loop — broken a second way,
    found re-checking R15: when the claim had ALREADY finished in the pool at
    the instant its caller was cancelled, add_done_callback ran the rollback
    INLINE, in the cancelled caller's thread — the loop, where the refund's
    writes wait out any contended write. Deterministic: the loop is held
    until the pool has finished, and only then is the caller cancelled."""
    import asyncio
    import threading
    import time

    from starlette.requests import Request

    submitted, refunded_in = [], []
    real_pool, real_refund = limits._pool, limits.refund

    class Recording:
        def submit(self, fn, *args, **kwargs):
            future = real_pool.submit(fn, *args, **kwargs)
            submitted.append(future)
            return future

    def refund(*args, **kwargs):
        refunded_in.append(threading.current_thread().name)
        return real_refund(*args, **kwargs)

    monkeypatch.setattr(limits, "_pool", Recording())
    monkeypatch.setattr(limits, "refund", refund)
    request = Request({"type": "http", "client": ("198.51.100.60", 1),
                       "headers": [(b"host", b"127.0.0.1:8000")]})
    subject = "ip:198.51.100.60"

    async def scenario():
        if phase == "claim":
            call = limits.claim(request, subject, "text", "tok")
        else:
            limits.admit(request, subject, "tok")
            call = limits.fund_async(request, subject, "link")
        task = asyncio.create_task(call)
        await asyncio.sleep(0)                    # it submits to the pool, then waits
        deadline = time.monotonic() + 10
        while not (submitted and submitted[0].done()):
            assert time.monotonic() < deadline, "the claim never finished in the pool"
            time.sleep(0.005)                     # hold the LOOP until the pool is done
        task.cancel()                             # ...so the loop never saw the result
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())
    assert limits.drain()
    assert refunded_in, "the slot was never given back"
    assert all(name.startswith("quota") for name in refunded_in), refunded_in
    assert limits.used_today() == 0


def test_an_unwritable_counter_refuses_rather_than_waves_through(limited, monkeypatch):
    """The guard fails CLOSED. A locked or broken database must not become an
    unlimited budget."""
    def broken(*a, **kw):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(limits._daily, "take", broken)
    resp = _check(limited)
    assert resp.status_code == 503
    assert "busy" in resp.json()["detail"]


def test_the_database_itself_refuses_a_slot_past_the_cap(client):
    """The guarantee does not rest on the Python lock: the UPSERT's WHERE is
    what refuses slot 3, even for two processes racing."""
    from app.store.repository import DailyQuota

    quota = DailyQuota()
    assert [quota.take("2026-01-01", 2) for _ in range(5)] == [True, True, False, False, False]
    assert quota.used("2026-01-01") == 2
    assert quota.take("2026-01-02", 0) is False       # a zero cap grants nothing


# -- a free check hands its slot back (2026-09-22) ----------------------------

def test_the_same_forward_twice_uses_one_slot_not_two(limited, monkeypatch):
    """With 2 checks a day, a message sent twice would otherwise spend half
    the day's allowance on an answer served from cache for $0."""
    monkeypatch.setattr(settings, "max_checks_per_day", 2)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    first = _check(limited, "The same forward")
    second = _check(limited, "The same forward")
    assert first.status_code == second.status_code == 202
    assert limited.get(f"/api/v1/reports/{second.json()['job_id']}").json()["cached"]
    assert limits.used_today() == 1
    # ...so a different message still fits today.
    assert _check(limited, "A different forward").status_code == 202


def test_a_paid_step_keeps_its_slot_even_on_a_cache_hit(limited, monkeypatch):
    """An image's OCR is a paid vision call. If the text it read then hits
    the answer cache, the ANSWER was free but the check was not."""
    from app.api import routes as R
    from app.providers.usage import note_llm

    monkeypatch.setattr(settings, "max_checks_per_hour", 100)

    async def metered_ocr(image_bytes, media_type):
        note_llm("claude-sonnet-5", type("U", (), {
            "input_tokens": 1500, "output_tokens": 40,
            "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0,
            "server_tool_use": None})())
        return "WHO ne kaha 5G se corona"

    monkeypatch.setattr(R, "ocr_image", metered_ocr)
    _check(limited, "WHO ne kaha 5G se corona")          # primes the cache
    before = limits.used_today()
    resp = limited.post("/api/v1/verify/image",
                        files={"file": ("m.png", b"\x89PNG", "image/png")})
    report = limited.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["cached"] and report["usage"]["estimated_usd"] > 0
    assert limits.used_today() == before + 1, "a paid OCR must keep its slot"


def test_a_failed_check_keeps_its_slot(limited, monkeypatch):
    """A stream that dies mid-answer may have been billed without its usage
    ever being recorded. Refunding failures would let exactly the unmeasured
    cases spend past the cap."""
    from app.engine import chat as C

    async def broken(text, *, heard=None, emit=None, language=None):
        raise C.CheckUnavailable("The checking service couldn't be reached.")

    monkeypatch.setattr(C, "answer", broken)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    before = limits.used_today()
    _check(limited)
    assert limits.used_today() == before + 1
