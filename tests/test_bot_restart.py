"""A restarted bot still delivers the checks it was waiting for. Free.

docs/research/2026-10-15/audit-ops.md OPS-07, and the review's R12: the bot
kept which chat waits for which job only in memory, and it confirms
Telegram's offset BEFORE doing the work (so a crash can never re-bill a
redelivered message). Restart it mid-check — its window closed, a reboot —
and the check still completed and was billed, but no reply was ever sent;
the person's "kya hua?" got the small-talk reply, and a resend was refused
by the API as "you already have a check running" — an answer promised by
nobody (R12).
"""
import asyncio
import json
import time

import scripts.telegram_bot as B
from tests.test_telegram_bot import StubApp, StubTG


class _OutlivesTheBot(StubApp):
    """The first bot's wait: the check takes longer than the bot lives."""

    async def wait_for_report(self, job_id, attempts=None):
        await asyncio.Event().wait()


def _first_life(store):
    """A message, a submission, a wait — and the process dies mid-wait."""
    async def life():
        bot = B.Dispatcher(_OutlivesTheBot(), StubTG(), pending_path=store)
        bot.dispatch({"chat": {"id": 7}, "text": "WHO ne kaha 5G se corona"})
        for _ in range(500):
            if bot.pending:
                break
            await asyncio.sleep(0.01)
        for task in list(bot._tasks):                # killed: nothing delivered
            task.cancel()
        await asyncio.gather(*list(bot._tasks), return_exceptions=True)
        return dict(bot.pending)

    return asyncio.run(life())


def _second_life(store, app):
    tg = StubTG()

    async def life():
        bot = B.Dispatcher(app, tg, pending_path=store)
        await bot.resume()
        await bot.drain()
        return dict(bot.pending), bot.prompted

    pending, prompted = asyncio.run(life())
    return tg.sent, pending, prompted


def test_a_restarted_bot_delivers_the_answer_it_was_waiting_for(tmp_path):
    store = str(tmp_path / "bot_pending.json")
    assert _first_life(store) == {7: "job123"}
    sent, pending, _ = _second_life(store, StubApp())
    texts = [text for chat, text in sent if chat == 7]
    assert any("pura hua" in t for t in texts), f"nothing was delivered: {sent}"
    assert len(texts) == 2                                 # the note + the report
    assert pending == {} and json.loads(open(store, encoding="utf-8").read()) == {}


def test_a_check_still_running_after_the_restart_is_said_so(tmp_path):
    class StillRunning(StubApp):
        async def wait_for_report(self, job_id, attempts=None):
            return None

    store = str(tmp_path / "bot_pending.json")
    _first_life(store)
    sent, pending, prompted = _second_life(store, StillRunning())
    assert pending == {7: "job123"}, "the job was forgotten"
    assert 7 in prompted and "chal raha" in sent[-1][1]


def test_a_job_that_no_longer_exists_is_dropped_quietly(tmp_path):
    class Gone(StubApp):
        async def wait_for_report(self, job_id, attempts=None):
            raise B.JobGone(job_id)

    store = str(tmp_path / "bot_pending.json")
    _first_life(store)
    sent, pending, _ = _second_life(store, Gone())
    assert pending == {} and sent == []


def test_a_day_old_entry_is_forgotten(tmp_path):
    """A job id opens the person's message (OPS-11): nothing keeps one
    longer than it can still be delivered."""
    store = tmp_path / "bot_pending.json"
    store.write_text(json.dumps({"7": {"job": "old", "at": time.time() - 2 * 86400},
                                 "8": {"job": "new", "at": time.time()}}),
                     encoding="utf-8")
    assert dict(B.PendingStore(str(store))) == {8: "new"}


def test_a_damaged_file_never_stops_the_bot(tmp_path):
    store = tmp_path / "bot_pending.json"
    store.write_text("{not json", encoding="utf-8")
    assert dict(B.PendingStore(str(store))) == {}
