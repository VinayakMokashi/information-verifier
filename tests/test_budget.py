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


# -- cheaper as the day drains; repeats stay free (2026-10-15) ----------------

def test_the_mode_follows_what_is_left_of_the_day(budgeted, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    day = limits.today()
    assert limits.budget_mode(day) == "full"
    DailyBudget().reserve(day, 0.65, 1.0)           # 35% left
    assert limits.budget_mode(day) == "vetted"
    DailyBudget().reserve(day, 0.25, 1.0)           # 10% left
    assert limits.budget_mode(day) == "shortcut"


def test_a_cheaper_mode_reserves_less(budgeted):
    assert limits.reserve_usd("text", "vetted") < limits.reserve_usd("text", "full")
    assert limits.reserve_usd("text", "shortcut") <= 0.02


def test_near_the_end_of_the_day_only_text_can_still_be_checked(budgeted, monkeypatch):
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    DailyBudget().reserve(limits.today(), 0.90, 1.0)    # 10% left
    link = budgeted.post("/api/v1/verify/link",
                         json={"url": "https://www.youtube.com/watch?v=ccccccccccc"})
    assert link.status_code == 429 and "text" in link.json()["detail"].lower()
    assert budgeted.post("/api/v1/verify/text",
                         json={"text": "a fresh claim"}).status_code == 202


def test_the_engine_is_told_the_mode(budgeted, monkeypatch):
    import app.engine.chat as C
    import scripts.fake_stages as F

    seen = []

    async def spy(text, **kw):
        seen.append(kw.get("mode"))
        return await F.fake_answer(text, **kw)

    monkeypatch.setattr(C, "answer", spy)
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    DailyBudget().reserve(limits.today(), 0.65, 1.0)    # 35% left
    budgeted.post("/api/v1/verify/text", json={"text": "a vetted-only claim"})
    assert seen == ["vetted"]


def test_a_degraded_answer_is_never_cached(budgeted, monkeypatch):
    import app.engine.chat as C
    from app.engine.job import cache_key
    from app.models.answer import AnswerSection

    async def cut_short(text, **kw):
        return C.ChatAnswer(sections=[AnswerSection(tier="none", markdown="Budget.")],
                            tier="none", degraded=True)

    monkeypatch.setattr(C, "answer", cut_short)
    budgeted.post("/api/v1/verify/text", json={"text": "cut short today"})
    assert R._repo.cache.get(cache_key("cut short today")) is None


def test_a_repeat_is_served_free_even_when_the_day_is_spent(budgeted):
    first = budgeted.post("/api/v1/verify/text", json={"text": "The same forward"})
    assert first.status_code == 202                     # now in the cache
    DailyBudget().reserve(limits.today(), 0.50, 0.50)   # the rest of the day, gone
    fresh = budgeted.post("/api/v1/verify/text", json={"text": "A brand new forward"})
    assert fresh.status_code == 429
    again = budgeted.post("/api/v1/verify/text", json={"text": "The same forward"})
    assert again.status_code == 202
    report = budgeted.get(f"/api/v1/reports/{again.json()['job_id']}").json()
    assert report["cached"] is True and report["usage"]["estimated_usd"] == 0
