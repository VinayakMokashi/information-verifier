"""A dollar budget a day, not a count of checks. Free.

DECIDED 2026-10-15 (Vinayak): strangers share a $1-a-day ceiling. A count
was a poor proxy for money — a day of reels costs three times a day of
covered hoaxes. Each check RESERVES its worst case before any spend and
SETTLES at what it really cost when it ends; the database itself refuses a
reservation that would cross the day's budget (one conditional statement,
as for the count). A refusal or a free cache hit gives its reservation back;
a check whose cost is unknown keeps it — over-counting is the safe side.
"""
import pytest
from fastapi import HTTPException
from starlette.requests import Request

import app.api.routes as R
from app.api import limits
from app.config import settings
from app.store.repository import DailyBudget


def _req(peer="203.0.113.7"):
    return Request({"type": "http", "client": (peer, 5555),
                    "headers": [(b"host", b"127.0.0.1:8000")]})


@pytest.fixture()
def budgeted(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_day", 1000)
    monkeypatch.setattr(settings, "max_checks_per_hour", 1000)
    monkeypatch.setattr(settings, "person_daily_limits", {"ip": 1000, "ip6": 1000})
    monkeypatch.setattr(settings, "daily_budget_usd", 0.50)
    monkeypatch.setattr(settings, "budget_reserve_usd",
                        {"text": 0.20, "image": 0.25, "media": 0.30, "link": 0.30})
    limits.reset()
    return client


def committed():
    return DailyBudget().committed(limits.today())


# -- the store: one conditional statement ----------------------------------------

def test_the_database_refuses_a_reservation_past_the_budget(budgeted):
    b, day = DailyBudget(), "2099-01-01"
    assert b.reserve(day, 0.20, 0.50) and b.reserve(day, 0.20, 0.50)
    assert not b.reserve(day, 0.20, 0.50)           # 0.60 > 0.50
    assert b.committed(day) == pytest.approx(0.40)  # the refusal added nothing
    b.settle(day, reserved=0.20, actual=0.05)       # one check ended at $0.05
    assert b.committed(day) == pytest.approx(0.25)
    assert b.reserve(day, 0.20, 0.50)               # 0.45 fits now
    assert not b.reserve("2099-01-02", 0.60, 0.50)  # more than the whole budget
    b.settle(day, reserved=0.20, actual=0.0)
    b.settle(day, reserved=5.00, actual=0.0)
    assert b.committed(day) == 0                    # never below zero


# -- the limiter -------------------------------------------------------------------

def test_claims_stop_at_the_budget_not_at_a_count(budgeted):
    assert limits.reserve(_req("198.51.100.1"), kind="text")
    assert limits.reserve(_req("198.51.100.2"), kind="text")
    with pytest.raises(HTTPException) as spent:
        limits.reserve(_req("198.51.100.3"), kind="text")
    assert spent.value.status_code == 429 and "budget" in spent.value.detail
    assert limits.used_today() == 2                 # the refusal took no slot


def test_a_refused_submission_gives_its_reservation_back(budgeted):
    r = _req("198.51.100.1")
    day = limits.reserve(r, kind="link")
    assert committed() == pytest.approx(0.30)
    limits.refund(r, day, kind="link")
    assert committed() == 0


# -- end to end, through the routes ----------------------------------------------

def test_a_check_settles_at_what_it_really_cost(budgeted, monkeypatch):
    from app.providers import usage

    async def costs_something(text, **kw):
        usage.note_asr(600)                           # a real line on the bill
        import scripts.fake_stages as F
        return await F.fake_answer(text, **kw)

    monkeypatch.setattr(R, "run_check", R.run_check)  # the real one, faked engine:
    import app.engine.chat as C
    monkeypatch.setattr(C, "answer", costs_something)
    job = budgeted.post("/api/v1/verify/text", json={"text": "5G spreads corona"}).json()
    bill = budgeted.get(f"/api/v1/reports/{job['job_id']}").json()["usage"]["estimated_usd"]
    assert bill > 0
    assert committed() == pytest.approx(bill)         # not the $0.20 reserved


def test_a_rejection_before_any_spend_costs_the_budget_nothing(budgeted):
    resp = budgeted.post("/api/v1/verify/image",
                         files={"file": ("notes.txt", b"hi", "text/plain")})
    assert resp.status_code == 415
    assert committed() == 0


def test_a_free_cache_hit_costs_nothing_and_takes_no_slot(budgeted):
    budgeted.post("/api/v1/verify/text", json={"text": "The same forward"})
    used, spent = limits.used_today(), committed()
    budgeted.post("/api/v1/verify/text", json={"text": "The same forward"})
    assert limits.used_today() == used and committed() == pytest.approx(spent)


def test_a_check_whose_cost_is_unknown_keeps_its_reservation(budgeted, monkeypatch):
    """Over-counting is the safe direction: a check that died without a bill
    may still have been billed."""
    async def no_bill(job_id, text, repo, stream=None, **kw):
        if stream is not None:
            await stream.close()      # ends without ever writing a usage line

    monkeypatch.setattr(R, "run_check", no_bill)
    budgeted.post("/api/v1/verify/text", json={"text": "a claim with no bill"})
    assert committed() == pytest.approx(0.20)


def test_the_budget_is_the_decision():
    """Pinned: Vinayak's number (2026-10-15), not a tuning knob. The count of
    checks is now only a backstop above it."""
    assert settings.daily_budget_usd == 1.0
    assert settings.max_checks_per_day >= 30
