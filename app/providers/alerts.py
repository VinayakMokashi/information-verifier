"""Telling the OWNER, on Telegram, what the app window would show nobody.

REPRODUCED by reading (docs/research/2026-10-15/audit-ops.md OPS-19): nothing
told the owner about a spend limit refusing every check, the day's budget
running out, an error storm, or a restart that failed checks mid-flight —
only the console of a PC that runs 24/7 with nobody watching it.

Through the bot token the app already has, to settings.owner_chat_id (empty =
off; the bot's /id command tells anyone their own chat id). Each kind at most
once an hour. Fire and forget: an alert never raises, never delays a check,
and never prints the token — every Bot API URL carries it (63f8049).
Callable from any thread: the limiter decides the budget mode on its own
pool, so an alert from there is handed to the app's loop (attach()); a
script with no loop at all sends it there and then.
"""
import asyncio
import threading
import time

import httpx

from app.config import settings

_EVERY_S = 3600.0
_TRANSPORT = None          # a seam: tests hand in an httpx.MockTransport
_now = time.monotonic      # a seam: tests move the clock
_sent: dict[str, float] = {}
_lock = threading.Lock()
_tasks: set = set()
_loop: list = [None]       # the app's event loop, for alerts raised on threads


def attach(loop) -> None:
    """The app's event loop (its lifespan calls this at startup)."""
    _loop[0] = loop


def notify(kind: str, text: str) -> None:
    """Tell the owner `text`, unless a `kind` alert went out this hour."""
    if not (settings.owner_chat_id and settings.telegram_bot_token):
        return
    with _lock:
        last = _sent.get(kind)
        if last is not None and _now() - last < _EVERY_S:
            return
        _sent[kind] = _now()
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is not None:
        task = running.create_task(_send(text))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    elif _loop[0] is not None and not _loop[0].is_closed():
        asyncio.run_coroutine_threadsafe(_send(text), _loop[0])
    else:
        # No event loop anywhere: a plain script, such as the unattended
        # runner (scripts/serve_forever.py). It used to vanish without a word;
        # now it is sent before this returns (at most _send's 15 s timeout).
        asyncio.run(_send(text))


async def _send(text: str) -> None:
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=15, transport=_TRANSPORT) as client:
            resp = await client.post(url, json={
                "chat_id": settings.owner_chat_id,
                "text": f"⚠️ Information Verifier: {text}",
                "disable_web_page_preview": True})
        if resp.status_code != 200:
            print(f"[alert] Telegram refused the owner alert: HTTP {resp.status_code}")
    except Exception as exc:  # noqa: BLE001 — never the URL: it carries the token
        print(f"[alert] could not reach Telegram: {type(exc).__name__}")
