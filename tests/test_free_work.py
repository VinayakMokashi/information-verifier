"""Free work holds nothing anyone else needs. Free.

REPRODUCED 2026-10-15 by the reviewer of the day's fixes (docs/research/
2026-10-15/review-blockers.md, R1): one check in flight per PERSON stopped
one visitor holding several slots — not five visitors holding one each.
Five people each sent a link whose free resolve hung and was then refused:
while it ran, every daily slot was held and everyone else was told "try
again tomorrow"; afterwards every slot was refunded — no job, no ledger row,
nothing on the dashboard. With the dollar budget, a pending reel also held
$0.30 of the day's $1.

So the money is claimed only right before the first PAID step. During the
free part — a link's resolve, an upload's decode — a person holds only their
own place in line (one check in flight, the hourly attempt).
"""
import threading
import time

import pytest

import app.api.routes as R
from app.api import limits
from app.config import settings
from app.store.repository import DailyBudget


@pytest.fixture()
def people(client, monkeypatch):
    """The real limiter, and a header that says who is asking (the
    TestClient's address is fixed; a real visitor's is their own)."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    monkeypatch.setattr(settings, "person_daily_limits", {"ip": 100})
    monkeypatch.setattr(R, "subject_of",
                        lambda request: request.headers.get("x-test-person", "ip:anon"))
    limits.reset()
    return client


def _wait_for(condition, seconds=15):
    deadline = time.monotonic() + seconds
    while not condition() and time.monotonic() < deadline:
        time.sleep(0.01)


@pytest.mark.parametrize("binding", ["count", "money"])
def test_five_people_with_slow_links_hold_nothing(people, monkeypatch, binding):
    if binding == "count":          # the reviewer's run: 5 checks a day
        monkeypatch.setattr(settings, "max_checks_per_day", 5)
        monkeypatch.setattr(settings, "daily_budget_usd", 100.0)
    else:                           # the dollar budget: two pending reels fill $0.60
        monkeypatch.setattr(settings, "max_checks_per_day", 100)
        monkeypatch.setattr(settings, "daily_budget_usd", 0.60)
    gate, guard, inside = threading.Event(), threading.Lock(), [0]

    def hangs_then_refused(url):
        with guard:
            inside[0] += 1
        gate.wait(30)
        raise R.LinkError("network", "The platform could not be reached right now.")

    monkeypatch.setattr(R, "resolve_link", hangs_then_refused)

    def submit(person):
        people.post("/api/v1/verify/link", headers={"x-test-person": person},
                    json={"url": "https://www.youtube.com/watch?v=ddddddddddd"})

    threads = [threading.Thread(target=submit, args=(f"ip6:2001:db8:0:{n}::/64",))
               for n in range(5)]
    for t in threads:
        t.start()
    _wait_for(lambda: inside[0] == 5)
    held_slots = limits.used_today()
    held_money = DailyBudget().committed(limits.today())
    victim = people.post("/api/v1/verify/text", headers={"x-test-person": "ip:victim"},
                         json={"text": "someone else's claim"})
    gate.set()
    for t in threads:
        t.join(30)

    assert inside[0] == 5, "a slow free resolve was refused before it ran"
    assert (held_slots, held_money) == (0, 0), "free work held the day's slots or money"
    assert victim.status_code == 202, victim.json()


def test_a_link_takes_its_slot_and_money_once_the_free_part_succeeds(people, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    resp = people.post("/api/v1/verify/link", headers={"x-test-person": "ip:a"},
                       json={"url": "https://www.youtube.com/watch?v=eeeeeeeeeee"})
    assert resp.status_code == 202
    assert limits.used_today() == 1


def test_a_link_cancelled_while_its_money_is_reserved_gives_it_all_back(people, monkeypatch):
    """The cancellation lands while fund() is still in the pool — after the
    free resolve, before the first paid step (a shutdown, mostly) — so the
    route never learns which day was charged and cannot give it back itself.
    The pool must hand back the slot, the money and the person's allowance
    (limits._rollback_funding), and the route the person's place in line.
    Unpinned until the reviewer's cancellation script was re-run against the
    two-phase claim and could no longer reach this path."""
    import asyncio

    import httpx

    from app.main import app

    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    real, funding = limits.fund, threading.Event()

    def slow_fund(request, subject=None, kind="text", mode="full"):
        funding.set()
        time.sleep(0.4)                       # a contended write
        return real(request, subject, kind, mode)

    monkeypatch.setattr(limits, "fund", slow_fund)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as http:
            task = asyncio.create_task(http.post(
                "/api/v1/verify/link", headers={"x-test-person": "ip:a"},
                json={"url": "https://www.youtube.com/watch?v=ggggggggggg"}))
            for _ in range(500):                 # bounded: a broken route FAILS here
                if funding.is_set() or task.done():
                    break
                await asyncio.sleep(0.01)
            assert funding.is_set(), f"the link never reached its money: {_ended(task)}"
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(scenario())
    assert limits.drain(), "the funding never finished in the pool"
    assert limits.used_today() == 0, "the day's slot was kept"
    assert DailyBudget().committed(limits.today()) == 0, "the money was kept"
    assert limits._person_today.get("ip:a", 0) == 0, "the person's allowance was kept"
    assert limits._in_flight == {}, "the person was left in flight"


def _ended(task) -> str:
    if not task.done():
        return "still running"
    if task.exception() is not None:
        return repr(task.exception())
    return f"{task.result().status_code} {task.result().text[:200]}"


def test_a_refused_link_never_took_a_slot(people, monkeypatch):
    def refused(url):
        raise R.LinkError("not_found", "No public post was found at that link.")

    monkeypatch.setattr(R, "resolve_link", refused)
    resp = people.post("/api/v1/verify/link", headers={"x-test-person": "ip:a"},
                       json={"url": "https://www.youtube.com/watch?v=fffffffffff"})
    assert resp.status_code == 422
    assert limits.used_today() == 0 and limits._in_flight == {}


def test_while_others_are_running_a_full_day_says_busy_not_tomorrow(people, monkeypatch):
    """The day is "used up" only by what has SETTLED; money held by checks
    still running mostly comes back as they settle at their real cost."""
    monkeypatch.setattr(settings, "daily_budget_usd", 0.20)
    from starlette.requests import Request

    def req(peer):
        return Request({"type": "http", "client": (peer, 1),
                        "headers": [(b"host", b"127.0.0.1:8000")]})

    assert limits.reserve(req("198.51.100.1"))          # running, holds the $0.20
    with pytest.raises(limits.HTTPException) as busy:
        limits.reserve(req("198.51.100.2"))
    assert "busy" in busy.value.detail and "tomorrow" not in busy.value.detail
    limits.settle_budget(limits.today(), "text", 0.20)   # it really cost all of it
    limits.release("ip:198.51.100.1")
    with pytest.raises(limits.HTTPException) as spent:
        limits.reserve(req("198.51.100.2"))
    assert "used up" in spent.value.detail
