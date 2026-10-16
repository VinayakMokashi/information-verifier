"""The owner hears about trouble on Telegram — not only a console nobody watches. Free.

docs/research/2026-10-15/audit-ops.md OPS-19: nothing told the owner about a
spend limit refusing every check, the day's budget running out, an error
storm, or a restart that failed checks mid-flight — only the app window,
which on a 24/7 PC nobody is looking at. Alerts go through the bot token the
app already has, to OWNER_CHAT_ID (empty = off), each kind at most once an
hour, never raising and never printing the token (every Bot API URL carries
it — the 63f8049 lesson). Telegram is faked here: no test sends a message.
"""
import asyncio
import json
import threading

import httpx
import pytest

from app.config import settings
from app.providers import alerts

_TOKEN = "123456:PLANTED-token-must-never-print"


@pytest.fixture()
def telegram(monkeypatch):
    sent, answer = [], {"status": 200}

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(answer["status"], json={"ok": answer["status"] == 200})

    clock = [1000.0]
    monkeypatch.setattr(alerts, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(alerts, "_now", lambda: clock[0])
    monkeypatch.setattr(alerts, "_sent", {})
    monkeypatch.setattr(settings, "owner_chat_id", "4242")
    monkeypatch.setattr(settings, "telegram_bot_token", _TOKEN)
    return sent, answer, clock


async def _settled():
    for _ in range(100):
        if not alerts._tasks:
            return
        await asyncio.sleep(0.01)


def _run(*calls):
    async def go():
        alerts.attach(asyncio.get_running_loop())
        for kind, text in calls:
            alerts.notify(kind, text)
        await _settled()

    asyncio.run(go())


def test_an_alert_reaches_the_owner_once_an_hour_per_kind(telegram):
    sent, _, clock = telegram
    _run(("paused", "a"), ("paused", "b"), ("budget", "c"))
    assert [m["text"].split(": ", 1)[1] for m in sent] == ["a", "c"]
    assert all(m["chat_id"] == "4242" for m in sent)
    clock[0] += 3601
    _run(("paused", "d"))
    assert sent[-1]["text"].endswith("d")


def test_no_owner_means_no_alert(telegram, monkeypatch):
    sent, _, _ = telegram
    monkeypatch.setattr(settings, "owner_chat_id", "")
    _run(("paused", "a"))
    assert sent == []


def test_a_refused_alert_never_raises_and_never_prints_the_token(telegram, capsys):
    sent, answer, _ = telegram
    answer["status"] = 403
    _run(("paused", "a"))
    out = capsys.readouterr().out
    assert "403" in out and _TOKEN not in out


def test_an_alert_from_a_worker_thread_still_goes(telegram):
    """The budget mode is decided on the limiter's pool, a thread with no
    event loop: the alert is handed to the app's loop."""
    sent, _, _ = telegram

    async def go():
        alerts.attach(asyncio.get_running_loop())
        worker = threading.Thread(target=alerts.notify, args=("budget", "from a thread"))
        worker.start()
        worker.join(5)
        for _ in range(100):
            if sent:
                break
            await asyncio.sleep(0.01)

    asyncio.run(go())
    assert sent and sent[0]["text"].endswith("from a thread")


def test_paused_for_money_tells_the_owner(telegram):
    from app.providers.llm import tell_owner_paused

    sent, _, _ = telegram

    async def go():
        alerts.attach(asyncio.get_running_loop())
        tell_owner_paused("HTTP 400: You have reached your specified API usage limits")
        await _settled()

    asyncio.run(go())
    assert len(sent) == 1 and "usage limits" in sent[0]["text"]


def test_three_failed_checks_in_a_row_tell_the_owner_and_a_success_resets(telegram):
    import app.api.routes as R

    sent, _, _ = telegram

    async def go():
        alerts.attach(asyncio.get_running_loop())
        R._failures[0] = 0
        for status in ("FAILED", "FAILED", "COMPLETE", "FAILED", "FAILED", "FAILED"):
            R._count_outcome(status, "The checking service couldn't be reached.")
        await _settled()

    asyncio.run(go())
    assert len(sent) == 1 and "3 checks in a row" in sent[0]["text"]


def test_the_bot_tells_anyone_their_own_chat_id():
    import scripts.telegram_bot as B
    from tests.test_telegram_bot import StubApp, StubTG

    assert B.classify_message({"chat": {"id": 7}, "text": "/id"})[0] == "id"
    assert B.classify_message({"chat": {"id": 7}, "text": "/idea for a check"})[0] != "id"
    tg = StubTG()
    asyncio.run(B.handle_message({"chat": {"id": 4242}, "text": "/id"}, StubApp(), tg))
    assert tg.sent == [(4242, "Your chat id: 4242")]
