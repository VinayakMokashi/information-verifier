"""A spending guard for the public share link.

`share_demo.ps1` puts this app on a public URL, and every check spends real
money. Anyone with the link — or anyone a friend forwards it to — can submit
claims, so the limiter caps how much a single visitor, and the deployment as
a whole, can spend before someone has to intervene.

Two counters, deliberately stored differently:

  * **The daily cap** (deployment-wide) is the SPEND guard, so it lives in
    SQLite and survives restarts. It used to be in memory, and under
    `--reload` every saved file refilled it; a "2 checks a day" cap (Vinayak,
    2026-09-22) that a restart quietly tops up is not a cap.
  * **The hourly cap** (per visitor IP) is an ABUSE guard, so it stays in
    memory. Losing it on restart costs nothing, and a visitor's IP is personal
    data this app has no reason to write to disk.
"""
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.config import settings
from app.store.repository import DailyQuota, operator_day

_MAX_TRACKED_CLIENTS = 512

_lock = threading.Lock()
_per_client: dict[str, list[float]] = {}
_daily = DailyQuota()

# Claiming a slot is a blocking SQLite WRITE, so it runs off the event loop —
# a contended write there froze every request and every live stream. It does
# NOT run in asyncio's default pool either: MEASURED, a burst of claims while
# another writer held the database filled all of its workers, and
# GET /reports (a thread call too, and the only way an answer reaches anyone)
# stalled for the full 30 s busy timeout. Two workers is plenty — claims are
# tiny, and they serialize on `_lock` anyway.
_POOL_WORKERS = 2
_pool = ThreadPoolExecutor(max_workers=_POOL_WORKERS, thread_name_prefix="quota")


def _rollback(request: Request, future) -> None:
    """Hand back a slot whose claimant is already gone. Runs in the pool."""
    try:
        day = future.result()
    except Exception:       # noqa: BLE001 — it never got a slot to give back
        return
    if day:
        print("[limits] the caller went away before its slot arrived; returning it")
        refund(request, day)


async def claim(request: Request) -> str | None:
    """reserve(), off the loop and out of the shared pool. -> the day charged.

    A plain thread future, not run_in_executor, so that a caller cancelled
    while the claim is in flight (a shutdown, mostly) still gives its slot
    back: the claim finishes in the pool either way, and the callback runs
    there too, beyond the reach of the dying event loop. Found by review,
    measured — a cancelled submission silently spent one of the day's two
    checks, with no job row to show for it.
    """
    future = _pool.submit(reserve, request)
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.add_done_callback(lambda done: _rollback(request, done))
        raise


async def give_back(request: Request, day: str | None) -> None:
    """refund(), on the same pool."""
    await asyncio.get_running_loop().run_in_executor(_pool, refund, request, day)


async def give_back_day(day: str | None) -> None:
    """refund_daily(), on the same pool."""
    await asyncio.get_running_loop().run_in_executor(_pool, refund_daily, day)


def today() -> str:
    """The operator's calendar day, as the daily cap counts it — the same
    definition the spending dashboard uses (store.operator_day)."""
    return operator_day(datetime.now(timezone.utc))


def _reset_label() -> str:
    minutes = settings.day_boundary_utc_offset_min
    if minutes == 330:
        return "midnight India time"
    sign = "+" if minutes >= 0 else "-"
    return f"midnight UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def _daily_refusal() -> HTTPException:
    return HTTPException(
        429,
        f"This service has reached its daily limit of "
        f"{settings.max_checks_per_day} check"
        f"{'' if settings.max_checks_per_day == 1 else 's'}. "
        f"It resets at {_reset_label()} — please try again tomorrow.",
    )


def used_today() -> int:
    """Checks consumed today, across everyone."""
    return _daily.used(today())


def _prune(stamps: list[float], window_s: float, now: float) -> list[float]:
    return [t for t in stamps if now - t < window_s]


def _client_of(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def reserve(request: Request) -> str | None:
    """Claim one check, or raise 429. -> the day charged (None if disabled).

    Checking and claiming MUST be atomic. An earlier version checked here and
    consumed later, after the upload had been read and transcoded — 30
    simultaneous uploads from one IP all saw an empty counter and all passed
    a 2/day cap (measured). Rejected submissions get their claim back via
    refund() instead, so nothing is charged for work that never happened.

    The daily slot is taken by a single conditional UPSERT, so the DATABASE
    refuses slot 3 even if two processes ever raced here. Anything that stops
    the counter being recorded refuses the check: this guard fails closed.
    """
    if not settings.rate_limit_enabled:
        return None
    now = time.monotonic()
    client = _client_of(request)
    day = today()
    with _lock:
        try:
            # Fast path, for the clearer message: a visitor over BOTH limits
            # should hear "try tomorrow", not "try in an hour".
            if _daily.used(day) >= settings.max_checks_per_day:
                raise _daily_refusal()
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — see "fails closed" above
            print(f"[limits] daily counter unreadable: {type(exc).__name__}: {exc}")
            raise HTTPException(503, "The service is busy right now. "
                                     "Please try again in a minute.") from exc

        mine = _prune(_per_client.get(client, []), 3600, now)
        if len(mine) >= settings.max_checks_per_hour:
            _per_client[client] = mine
            raise HTTPException(
                429,
                f"You've used {settings.max_checks_per_hour} checks this hour — "
                "that's the limit for this demo. Please try again later.",
            )

        try:
            granted = _daily.take(day, settings.max_checks_per_day)
        except Exception as exc:  # noqa: BLE001 — fail closed, never open
            print(f"[limits] daily counter unwritable: {type(exc).__name__}: {exc}")
            raise HTTPException(503, "The service is busy right now. "
                                     "Please try again in a minute.") from exc
        if not granted:
            raise _daily_refusal()

        _per_client[client] = mine + [now]
        if len(_per_client) > _MAX_TRACKED_CLIENTS:
            # Expired visitors first...
            for ip in [k for k, v in _per_client.items() if not _prune(v, 3600, now)]:
                del _per_client[ip]
            # ...then the least-recently-seen, so a flood of distinct IPs
            # cannot grow this table without bound. Evicting only weakens the
            # per-visitor limit for a stale IP; the daily cap still bounds
            # total spend, and the caller we just recorded is never evicted.
            overflow = len(_per_client) - _MAX_TRACKED_CLIENTS
            if overflow > 0:
                oldest = sorted(_per_client.items(), key=lambda kv: kv[1][-1])
                for ip, _ in oldest[:overflow]:
                    del _per_client[ip]
    return day


def refund_daily(day: str | None) -> None:
    """Give back ONE day's slot — for a check that turned out to cost nothing.

    Takes the day the slot was charged to rather than recomputing it, so a
    check that straddles midnight refunds the day it actually used. A failed
    refund is logged and swallowed: it over-counts, the safe direction.
    """
    if day is None or not settings.rate_limit_enabled:
        return
    try:
        _daily.give_back(day)
    except Exception as exc:  # noqa: BLE001 — over-counting is the safe side
        print(f"[limits] refund not recorded: {type(exc).__name__}: {exc}")


def refund(request: Request, day: str | None) -> None:
    """Give back a reservation for a submission that never reached paid work.

    `day` is what reserve() returned. It used to be recomputed here, and a
    rejection that straddled midnight gave its slot back to the NEXT day,
    which then granted one check over the cap (found by review, reproduced).
    """
    if not settings.rate_limit_enabled:
        return
    refund_daily(day)
    with _lock:
        mine = _per_client.get(_client_of(request))
        if mine:
            mine.pop()


def drain(timeout: float = 10.0) -> bool:
    """Test helper — wait until every claim already on the pool has finished,
    the slot-returning callbacks included. False if that took too long.

    MEASURED 2026-10-11: a test that cancels claims left them settling on this
    pool after it ended — in the NEXT tests' databases. One took a slot inside
    another test's 2-slot cap (a random 429), and one refund hit a database so
    new it had no tables yet. The pool is FIFO: once one barrier task per
    worker is running at the same moment, everything queued before them has
    finished, and a future's callbacks run in its worker before it moves on.
    """
    import concurrent.futures

    barrier = threading.Barrier(_POOL_WORKERS)
    marks = [_pool.submit(barrier.wait, timeout) for _ in range(_POOL_WORKERS)]
    done, pending = concurrent.futures.wait(marks, timeout=timeout)
    return not pending and all(f.exception() is None for f in done)


def reset() -> None:
    """Test helper — clears the IN-MEMORY counters only.

    It deliberately never touches the database: the autouse fixture calls it
    before any test has pointed `db_path` at a temporary file, so a DB reset
    here would zero the REAL counter. Each test's database starts empty anyway.
    """
    with _lock:
        _per_client.clear()
