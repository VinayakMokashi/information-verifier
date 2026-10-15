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
  * **The hourly cap** (per person) is an ABUSE guard, so it stays in
    memory. Losing it on restart costs nothing, and who someone is (an IP, a
    Telegram id) is personal data this app has no reason to write to disk.

Both count PEOPLE, not connections (2026-10-15, reproduced): every Telegram
user used to reach this as ONE client — the bot, on 127.0.0.1 — so one
bucket held them all. See subject_of. And each person runs one check at a
time, from the claim until the check ends (release): five concurrent slow
link resolves from one visitor used to hold all five daily slots and then
be refunded — a free, traceless lockout of everyone.
"""
import asyncio
import ipaddress
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.api.local import is_this_machine
from app.config import settings
from app.store.repository import DailyBudget, DailyQuota, operator_day

_MAX_TRACKED_CLIENTS = 512

# The bot submits for many people over ONE connection; it names the person
# here. Honoured only from this machine (app/api/local.py), so a visitor can
# never pick a fresh bucket. Shape-checked, so it can be nothing but an id.
SUBJECT_HEADER = "x-verifier-subject"
_SUBJECT = re.compile(r"(?:tg|tgchat):-?\d{1,20}|wa:[0-9a-f]{16,64}")

_BUSY = ("You already have a check running. Wait for its answer, then send "
         "the next one.")

_lock = threading.Lock()
_per_client: dict[str, list[float]] = {}      # subject -> this hour's attempts
_in_flight: dict[str, list[float]] = {}       # subject -> start of each running check
# subject -> paid checks today. Holds ONE day at a time: the first claim of a
# new day clears it, so it never outgrows a day's visitors. A restart resets
# it — the price of never writing who someone is to disk; the money is
# guarded by the persisted daily cap, not by this.
_person_today: dict[str, int] = {}
_person_day = [""]
_daily = DailyQuota()
_budget = DailyBudget()
_now = time.monotonic                         # a seam: tests move the clock


def reserve_usd(kind: str, mode: str = "full") -> float:
    """What a check of this kind reserves of the day's budget before it
    spends anything, in this budget mode; it settles at its real cost when
    it ends."""
    if mode == "shortcut":
        return settings.budget_shortcut_reserve_usd
    table = settings.budget_reserve_usd
    full = table.get(kind, max(table.values()))
    return full / 2 if mode == "vetted" else full


def budget_mode(day: str) -> str:
    """What the day's money still buys: "full", then "vetted" (no open-web
    pass), then "shortcut" (published fact-checks only) as it drains —
    Vinayak's "$1 a day ... gets cheaper as it runs low" (2026-10-15).

    A soft guide read without the lock: two claims at once may both see
    "full". The HARD guard is the reservation, which the database refuses
    past the budget whatever mode a claim believed it was in.
    """
    if not settings.rate_limit_enabled or settings.daily_budget_usd <= 0:
        return "full"
    left = (settings.daily_budget_usd - _budget.committed(day)) / settings.daily_budget_usd
    if left >= settings.budget_vetted_below:
        return "full"
    if left >= settings.budget_shortcut_below:
        return "vetted"
    return "shortcut"


_NEARLY_SPENT = (
    "Today's budget for this service is nearly used up. Screenshots, voice "
    "notes and links can be checked again after midnight India time; a "
    "forwarded TEXT can still be checked against published fact-checks.")


def _claim_now(request: Request, subject: str, kind: str) -> tuple[str | None, str]:
    """On the pool: decide what the day's money buys, then reserve it."""
    mode = budget_mode(today())
    if mode == "shortcut" and kind != "text":
        # Its OCR or transcription alone could outrun what is left, and it
        # would end in a shortcut-only answer anyway.
        raise HTTPException(429, _NEARLY_SPENT)
    return reserve(request, subject, kind, mode), mode

# Claiming a slot is a blocking SQLite WRITE, so it runs off the event loop —
# a contended write there froze every request and every live stream. It does
# NOT run in asyncio's default pool either: MEASURED, a burst of claims while
# another writer held the database filled all of its workers, and
# GET /reports (a thread call too, and the only way an answer reaches anyone)
# stalled for the full 30 s busy timeout. Two workers is plenty — claims are
# tiny, and they serialize on `_lock` anyway.
_POOL_WORKERS = 2
_pool = ThreadPoolExecutor(max_workers=_POOL_WORKERS, thread_name_prefix="quota")


def _rollback(request: Request, subject: str, kind: str, future) -> None:
    """Hand back a slot whose claimant is already gone. Runs in the pool."""
    try:
        day, mode = future.result()
    except Exception:       # noqa: BLE001 — it never got a slot to give back
        return
    if day:
        print("[limits] the caller went away before its slot arrived; returning it")
        refund(request, day, kind, mode)
        release(subject)


def _ip_subject(host: str) -> str:
    """A visitor's bucket: IPv6 by its /64 — one phone on Jio and Airtel,
    90%+ IPv6 (APNIC, October 2026) — and IPv4 by address, which carrier
    NAT shares between many people."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return f"ip:{host}"
    if ip.version == 6:
        if ip.ipv4_mapped is not None:
            return f"ip:{ip.ipv4_mapped}"
        return f"ip6:{ipaddress.ip_network((ip, 64), strict=False)}"
    return f"ip:{ip}"


def subject_of(request: Request) -> str:
    """Whose check this is: the person the bot names, else the visitor."""
    claimed = request.headers.get(SUBJECT_HEADER, "")
    if claimed and _SUBJECT.fullmatch(claimed) and is_this_machine(request):
        return claimed
    return _ip_subject(_client_of(request))


async def claim(request: Request, subject: str | None = None,
                kind: str = "text") -> tuple[str | None, str]:
    """reserve(), off the loop and out of the shared pool. -> the day charged.

    A plain thread future, not run_in_executor, so that a caller cancelled
    while the claim is in flight (a shutdown, mostly) still gives its slot
    back: the claim finishes in the pool either way, and the callback runs
    there too, beyond the reach of the dying event loop. Found by review,
    measured — a cancelled submission silently spent one of the day's two
    checks, with no job row to show for it.
    """
    subject = subject or subject_of(request)
    future = _pool.submit(_claim_now, request, subject, kind)
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.add_done_callback(lambda done: _rollback(request, subject, kind, done))
        raise


async def give_back(request: Request, day: str | None, kind: str = "text",
                    mode: str = "full") -> None:
    """refund(), on the same pool."""
    await asyncio.get_running_loop().run_in_executor(_pool, refund, request, day,
                                                     kind, mode)


async def settle(day: str | None, kind: str, actual: float | None,
                 mode: str = "full") -> None:
    """settle_budget(), on the same pool."""
    await asyncio.get_running_loop().run_in_executor(_pool, settle_budget,
                                                     day, kind, actual, mode)


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


def reserve(request: Request, subject: str | None = None,
            kind: str = "text", mode: str = "full") -> str | None:
    """Claim one check, or raise 429. -> the day charged (None if disabled).

    Checking and claiming MUST be atomic. An earlier version checked here and
    consumed later, after the upload had been read and transcoded — 30
    simultaneous uploads from one IP all saw an empty counter and all passed
    a 2/day cap (measured). Rejected submissions get their claim back via
    refund() instead, so nothing is charged for work that never happened.

    The daily slot is taken by a single conditional UPSERT, so the DATABASE
    refuses slot 3 even if two processes ever raced here. Anything that stops
    the counter being recorded refuses the check: this guard fails closed.

    A granted claim also starts the person's check IN FLIGHT; whoever ends
    the check — the route on a refusal, the background job otherwise — calls
    release(). Until then the same person is refused, without a slot taken.
    """
    if not settings.rate_limit_enabled:
        return None
    now = _now()
    client = subject or subject_of(request)
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

        running = _prune(_in_flight.get(client, []), settings.in_flight_ttl_s, now)
        if len(running) >= settings.max_in_flight_per_person:
            _in_flight[client] = running
            raise HTTPException(429, _BUSY)

        if _person_day[0] != day:
            _person_today.clear()
            _person_day[0] = day
        allowance = _person_limit(client)
        if _person_today.get(client, 0) >= allowance:
            raise HTTPException(
                429,
                f"You've used your {allowance} check{'' if allowance == 1 else 's'} "
                f"for today. It resets at {_reset_label()} — please come back then.",
            )

        try:
            granted = _daily.take(day, settings.max_checks_per_day)
        except Exception as exc:  # noqa: BLE001 — fail closed, never open
            print(f"[limits] daily counter unwritable: {type(exc).__name__}: {exc}")
            raise HTTPException(503, "The service is busy right now. "
                                     "Please try again in a minute.") from exc
        if not granted:
            raise _daily_refusal()

        # The MONEY (2026-10-15: $1 a day): this check's worst case, reserved
        # by one conditional statement; the database refuses it past the
        # budget. Settled at the real cost when the check ends.
        try:
            funded = _budget.reserve(day, reserve_usd(kind, mode),
                                     settings.daily_budget_usd)
        except Exception as exc:  # noqa: BLE001 — fail closed, never open
            print(f"[limits] budget unwritable: {type(exc).__name__}: {exc}")
            _give_back_quietly(day)
            raise HTTPException(503, "The service is busy right now. "
                                     "Please try again in a minute.") from exc
        if not funded:
            _give_back_quietly(day)
            raise HTTPException(
                429,
                "Today's checking budget has been used up. It resets at "
                f"{_reset_label()} — please come back then.",
            )

        _per_client[client] = mine + [now]
        _in_flight[client] = running + [now]
        _person_today[client] = _person_today.get(client, 0) + 1
        if len(_in_flight) > _MAX_TRACKED_CLIENTS:
            # Only checks that hung past the TTL can pile up here.
            for key in [k for k, v in _in_flight.items()
                        if not _prune(v, settings.in_flight_ttl_s, now)]:
                del _in_flight[key]
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


def _give_back_quietly(day: str) -> None:
    """The slot just taken, returned because the money was not there."""
    try:
        _daily.give_back(day)
    except Exception as exc:  # noqa: BLE001 — over-counting is the safe side
        print(f"[limits] slot not returned: {type(exc).__name__}: {exc}")


def settle_budget(day: str | None, kind: str, actual: float | None,
                  mode: str = "full") -> None:
    """A check ended: its reservation becomes what it really cost.

    `actual` None means the cost is not known — the reservation is KEPT:
    a check that died mid-answer may have been billed without its usage
    ever being recorded, and over-counting is the safe side. A failed
    settle is logged and swallowed for the same reason.
    """
    if day is None or actual is None or not settings.rate_limit_enabled:
        return
    try:
        _budget.settle(day, reserve_usd(kind, mode), actual)
    except Exception as exc:  # noqa: BLE001 — over-counting is the safe side
        print(f"[limits] budget settle not recorded: {type(exc).__name__}: {exc}")


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


def refund(request: Request, day: str | None, kind: str = "text",
           mode: str = "full") -> None:
    """Give back a reservation for a submission that never reached paid work.

    `day` is what reserve() returned. It used to be recomputed here, and a
    rejection that straddled midnight gave its slot back to the NEXT day,
    which then granted one check over the cap (found by review, reproduced).

    The day's SLOT comes back; the person's hourly ATTEMPT stays counted. It
    used to be erased too, so a loop of refunded rejections never met the
    hourly limit at all (reproduced 2026-10-15, the refunded-link lockout).
    """
    if not settings.rate_limit_enabled:
        return
    refund_daily(day)
    settle_budget(day, kind, 0.0, mode)    # nothing was spent
    give_back_person(subject_of(request), day)


def _person_limit(subject: str) -> int:
    table = settings.person_daily_limits
    return table.get(subject.split(":", 1)[0], table.get("ip", 20))


def give_back_person(subject: str | None, day: str | None) -> None:
    """A check that cost nothing — refused before any spend, or a free cache
    hit — gives the person's daily check back, as it gives the day's slot."""
    if not subject or day is None or not settings.rate_limit_enabled:
        return
    with _lock:
        if _person_day[0] == day and _person_today.get(subject, 0) > 0:
            _person_today[subject] -= 1


def release(subject: str | None) -> None:
    """The person's check has ended — answered, failed, refused or refunded —
    so their next one may start. Safe to call for a subject with nothing
    running (rate limiting off, or already released)."""
    if not subject:
        return
    with _lock:
        running = _in_flight.get(subject)
        if running:
            running.pop(0)
            if not running:
                del _in_flight[subject]


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
        _in_flight.clear()
        _person_today.clear()
        _person_day[0] = ""
