"""When Anthropic refuses for MONEY, checking pauses, and nothing is charged. Free.

A spend limit, the account tier's monthly cap, a billing problem or an
exhausted credit balance makes EVERY check fail until someone pays or the
month turns (docs/research/2026-10-15/limits-budget.verification.md), and
"failed requests aren't charged". Before 2026-10-16 each such check kept its
reservation like any failure whose cost is unknown — so a handful drained the
day's $1, and once credits were topped up everyone was still told the budget
was used up, until midnight. The reader was told to try again "in a few
minutes", which could not work.
"""
import pytest

import app.api.routes as R
from app.api import limits
from app.config import settings
from app.engine import chat as C
from app.providers.llm import PAUSED_MESSAGE, paused_reason
from app.store.repository import DailyBudget
from tests.test_chat_engine import _refused_for_money

_SPEND_LIMIT = _refused_for_money(
    400, "You have reached your specified API usage limits. You will regain "
         "access on 2026-11-01 at 00:00 UTC.")


@pytest.mark.parametrize("exc, paused", [
    (_SPEND_LIMIT, True),
    (_refused_for_money(400, "You have reached your specified workspace API usage "
                             "limits. You will regain access on 2026-11-01."), True),
    (_refused_for_money(400, "Your credit balance is too low to access the "
                             "Anthropic API."), True),
    (_refused_for_money(402, "There's an issue with your billing.", "billing_error"),
     True),
    (_refused_for_money(429, "Spend limit reached.", "rate_limit_error",
                        {"error_code": "enforced_spend_limit_reached"}), True),
    # Not money: an ordinary rate limit, a crawler-blocked domain, an overload.
    (_refused_for_money(429, "Number of request tokens has exceeded your "
                             "per-minute rate limit", "rate_limit_error"), False),
    (_refused_for_money(400, "The following domains are not accessible to our user "
                             "agent: ['x.com']"), False),
    (_refused_for_money(529, "Overloaded", "overloaded_error"), False),
    (_refused_for_money(500, "Internal server error", "api_error"), False),
    (RuntimeError("You have reached your specified API usage limits"), False),
])
def test_only_a_refusal_for_money_is_a_pause(exc, paused):
    assert (paused_reason(exc) is not None) is paused


@pytest.fixture()
def budgeted(client, monkeypatch):
    """The real limiter and the $1 budget, on this test's own database."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "daily_budget_usd", 1.0)
    limits.reset()
    return client


def _paused_engine(monkeypatch):
    async def refused(*args, **kwargs):
        raise C.ServicePaused(PAUSED_MESSAGE)    # what chat.answer raises

    monkeypatch.setattr(C, "answer", refused)


def _nothing_held(subject="ip:testclient"):
    day = limits.today()
    return (DailyBudget().committed(day), limits.used_today(),
            limits._person_today.get(subject, 0), limits._in_flight)


def test_a_check_paused_for_money_gives_everything_back(budgeted, monkeypatch):
    _paused_engine(monkeypatch)
    resp = budgeted.post("/api/v1/verify/text", json={"text": "5G spreads corona"})
    assert resp.status_code == 202
    report = budgeted.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "FAILED" and report["error"] == PAUSED_MESSAGE
    assert _nothing_held() == (0, 0, 0, {}), "a refusal that cost nothing kept the money"


def test_while_paused_new_checks_are_refused_up_front_until_it_may_have_cleared(
        budgeted, monkeypatch):
    import scripts.fake_stages as F

    clock = [1000.0]
    monkeypatch.setattr(limits, "_now", lambda: clock[0])
    _paused_engine(monkeypatch)
    budgeted.post("/api/v1/verify/text", json={"text": "5G spreads corona"})

    second = budgeted.post("/api/v1/verify/text", json={"text": "another claim"})
    assert second.status_code == 503 and second.json()["detail"] == PAUSED_MESSAGE
    assert _nothing_held() == (0, 0, 0, {}), "a refused check took something"

    clock[0] += settings.paused_retry_s + 1      # the owner may have paid by now
    monkeypatch.setattr(C, "answer", F.fake_answer)
    assert budgeted.post("/api/v1/verify/text",
                         json={"text": "a third claim"}).status_code == 202


def test_a_repeat_is_still_answered_free_while_paused(budgeted, monkeypatch):
    first = budgeted.post("/api/v1/verify/text", json={"text": "5G spreads corona"})
    assert first.status_code == 202                       # answered, and cached
    limits.pause()
    again = budgeted.post("/api/v1/verify/text", json={"text": "5G spreads corona"})
    assert again.status_code == 202
    report = budgeted.get(f"/api/v1/reports/{again.json()['job_id']}").json()
    assert report["status"] == "COMPLETE" and report["cached"] is True


def test_an_image_whose_reading_is_refused_for_money_gives_it_back(budgeted, monkeypatch,
                                                                   capsys):
    async def refused(images):
        raise _refused_for_money(402, "There's an issue with your billing.",
                                 "billing_error")

    monkeypatch.setattr(R, "ocr_images", refused)
    resp = budgeted.post("/api/v1/verify/image",
                         files={"file": ("shot.png", b"\x89PNG" + b"0" * 64, "image/png")})
    assert resp.status_code == 503 and resp.json()["detail"] == PAUSED_MESSAGE
    assert _nothing_held() == (0, 0, 0, {})
    assert limits.paused(), "the next check would be sent anyway"
    assert "[paused]" in capsys.readouterr().out, "the owner was not told"
