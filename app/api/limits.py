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
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app.api.device import device_of
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
# subject -> (start, token) of each running check. The token is the claim's
# own: a release removes exactly its own entry (review R11 — releasing by
# position let a check that outlived the TTL free the NEXT check's place).
_in_flight: dict[str, list[tuple[float, str]]] = {}
# subject -> paid checks today. Holds ONE day at a time: the first claim of a
# new day clears it, so it never outgrows a day's visitors. A restart resets
# it — the price of never writing who someone is to disk; the money is
# guarded by the persisted daily cap, not by this.
_person_today: dict[str, int] = {}
_person_day = [""]
_daily = DailyQuota()
_budget = DailyBudget()
_now = time.monotonic                         # a seam: tests move the clock
# Until when paid checks are refused because Anthropic refuses for money
# (pause(); app/providers/llm.paused_reason). In memory: a restart simply
# lets one check through to find out.
_paused_until = [0.0]


def pause() -> None:
    """Anthropic refused a check for MONEY: refuse new paid checks for
    settings.paused_retry_s, then let one through to see if it has cleared.
    Each refused one would only have failed after reserving, waiting and
    giving it all back — and taught the reader nothing."""
    _paused_until[0] = max(_paused_until[0], _now() + settings.paused_retry_s)


def paused() -> bool:
    return _now() < _paused_until[0]


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


def _mode_for(kind: str) -> str:
    mode = budget_mode(today())
    if mode == "shortcut" and kind != "text":
        # Its OCR or transcription alone could outrun what is left, and it
        # would end in a shortcut-only answer anyway.
        raise HTTPException(429, _NEARLY_SPENT)
    return mode


def _claim_now(request: Request, subject: str, kind: str,
               token: str | None) -> tuple[str | None, str]:
    """On the pool: decide what the day's money buys, then reserve it."""
    mode = _mode_for(kind)
    return reserve(request, subject, kind, mode, token), mode


def _fund_now(request: Request, subject: str, kind: str) -> tuple[str | None, str]:
    """On the pool: what the day's money buys, then fund it (phase 2)."""
    mode = _mode_for(kind)
    return fund(request, subject, kind, mode), mode


async def fund_async(request: Request, subject: str,
                     kind: str) -> tuple[str | None, str]:
    """fund(), off the loop and out of the shared pool, like claim()."""
    future = _pool.submit(_fund_now, request, subject, kind)
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.add_done_callback(
            lambda done: _off_the_loop(_rollback_funding, request, subject, kind, done))
        raise

# Claiming a slot is a blocking SQLite WRITE, so it runs off the event loop —
# a contended write there froze every request and every live stream. It does
# NOT run in asyncio's default pool either: MEASURED, a burst of claims while
# another writer held the database filled all of its workers, and
# GET /reports (a thread call too, and the only way an answer reaches anyone)
# stalled for the full 30 s busy timeout. Two workers is plenty — claims are
# tiny, and they serialize on `_lock` anyway.
_POOL_WORKERS = 2
_POOL_PREFIX = "quota"
_pool = ThreadPoolExecutor(max_workers=_POOL_WORKERS, thread_name_prefix=_POOL_PREFIX)


def _off_the_loop(rollback, *args) -> None:
    """Run a cancelled claim's rollback on the pool, never on the event loop.

    The callback normally runs in the worker that finishes the claim, and the
    rollback runs right there, so drain() still waits for it. But a claim
    that had ALREADY finished when its caller was cancelled makes
    add_done_callback run the callback INLINE, in the cancelled caller's
    thread — the event loop, where the rollback's SQLite writes would wait
    out any contended write (review R15's rule; reproduced re-checking it).
    """
    if threading.current_thread().name.startswith(_POOL_PREFIX):
        rollback(*args)
    else:
        _pool.submit(rollback, *args)


def _rollback(request: Request, subject: str, kind: str, token: str | None,
              future) -> None:
    """Hand back a slot whose claimant is already gone. Runs in the pool."""
    try:
        day, mode = future.result()
    except Exception:       # noqa: BLE001 — it never got a slot to give back
        return
    if day:
        print("[limits] the caller went away before its slot arrived; returning it")
        refund(request, day, kind, mode, subject)
        release(subject, token)


def _rollback_funding(request: Request, subject: str, kind: str, future) -> None:
    """Hand back money whose claimant is already gone. Runs in the pool. Not
    release(): the route that admitted the person is still unwinding, and
    releases them itself."""
    try:
        day, mode = future.result()
    except Exception:       # noqa: BLE001 — nothing was funded
        return
    if day:
        print("[limits] the caller went away before its money arrived; returning it")
        refund(request, day, kind, mode, subject)


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
    """Whose check this is: the person the bot names; else the web device a
    valid signed cookie proves (app/api/device.py — issued only after a
    Turnstile pass); else the visitor's address."""
    claimed = request.headers.get(SUBJECT_HEADER, "")
    if claimed and _SUBJECT.fullmatch(claimed) and is_this_machine(request):
        return claimed
    device_id = device_of(request)
    if device_id:
        return f"dev:{device_id}"
    return _ip_subject(_client_of(request))


async def claim(request: Request, subject: str | None = None,
                kind: str = "text", token: str | None = None) -> tuple[str | None, str]:
    """reserve(), off the loop and out of the shared pool. -> the day charged.

    A plain thread future, not run_in_executor, so that a caller cancelled
    while the claim is in flight (a shutdown, mostly) still gives its slot
    back: the claim finishes in the pool either way, and the callback runs
    there too, beyond the reach of the dying event loop. Found by review,
    measured — a cancelled submission silently spent one of the day's two
    checks, with no job row to show for it.
    """
    subject = subject or subject_of(request)
    token = token or uuid.uuid4().hex     # so a rollback releases exactly this claim
    future = _pool.submit(_claim_now, request, subject, kind, token)
    try:
        return await asyncio.wrap_future(future)
    except asyncio.CancelledError:
        future.add_done_callback(
            lambda done: _off_the_loop(_rollback, request, subject, kind, token, done))
        raise


async def give_back(request: Request, day: str | None, kind: str = "text",
                    mode: str = "full", subject: str | None = None) -> None:
    """refund(), on the same pool."""
    await asyncio.get_running_loop().run_in_executor(_pool, refund, request, day,
                                                     kind, mode, subject)


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


def _running(entries: list[tuple[float, str]], now: float) -> list[tuple[float, str]]:
    """The checks still in flight: not released, and not past the TTL."""
    return [e for e in entries if now - e[0] < settings.in_flight_ttl_s]


def _client_of(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _daily_full(day: str) -> bool:
    """The count is full — a fast read; the conditional take is the guard."""
    try:
        return _daily.used(day) >= settings.max_checks_per_day
    except Exception as exc:  # noqa: BLE001 — fail closed, never open
        print(f"[limits] daily counter unreadable: {type(exc).__name__}: {exc}")
        raise HTTPException(503, "The service is busy right now. "
                                 "Please try again in a minute.") from exc


def _others_running(client: str, now: float) -> bool:
    with _lock:
        return any(key != client and _running(entries, now)
                   for key, entries in _in_flight.items())


def _day_is_full(client: str, now: float, what: str) -> HTTPException:
    """The day's slots or money are gone. While OTHER checks are still
    running, much of what they hold comes back as they settle at their real
    cost — so say "busy", never "tomorrow" (review R1, 2026-10-15: held,
    refunded resolves told everyone "please try again tomorrow")."""
    if _others_running(client, now):
        return HTTPException(429, "The service is busy right now — please try "
                                  "again in a few minutes.")
    if what == "money":
        return HTTPException(
            429, "Today's checking budget has been used up. It resets at "
                 f"{_reset_label()} — please come back then.")
    return _daily_refusal()


def _hourly_locked(client: str, now: float) -> None:
    """This hour's attempt — the abuse guard — counted, or 429. The caller
    holds _lock."""
    mine = _prune(_per_client.get(client, []), 3600, now)
    if len(mine) >= settings.max_checks_per_hour:
        _per_client[client] = mine
        raise HTTPException(
            429,
            f"You've used {settings.max_checks_per_hour} checks this hour — "
            "that's the limit for this demo. Please try again later.",
        )
    _per_client[client] = mine + [now]


def attempt(request: Request, subject: str | None = None) -> None:
    """A FREE repeat: no money, no slot, no place in line — but still this
    hour's attempt. REPRODUCED (review R14): a cached answer was served
    before every per-person bound, and one visitor made 600 job rows and
    600 in-memory streams in 44 s."""
    if not settings.rate_limit_enabled:
        return
    client = subject or subject_of(request)
    with _lock:
        _hourly_locked(client, _now())


def _admit_locked(client: str, now: float, token: str) -> None:
    """The person's place in line — this hour's attempts, one check in
    flight, under this claim's own token — recorded on success. The caller
    holds _lock."""
    mine = _prune(_per_client.get(client, []), 3600, now)
    if len(mine) >= settings.max_checks_per_hour:
        _per_client[client] = mine
        raise HTTPException(
            429,
            f"You've used {settings.max_checks_per_hour} checks this hour — "
            "that's the limit for this demo. Please try again later.",
        )
    running = _running(_in_flight.get(client, []), now)
    kind = client.split(":", 1)[0]
    if len(running) >= settings.in_flight_by_kind.get(kind, settings.max_in_flight_per_person):
        _in_flight[client] = running
        raise HTTPException(429, _BUSY)
    _per_client[client] = mine + [now]
    _in_flight[client] = running + [(now, token)]
    if len(_in_flight) > _MAX_TRACKED_CLIENTS:
        # Only checks that hung past the TTL can pile up here.
        for key in [k for k, v in _in_flight.items() if not _running(v, now)]:
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


def _unadmit_locked(client: str, token: str | None) -> None:
    """Remove this token's in-flight entry, and nothing if it is already
    gone (pruned past the TTL, or released before) — never another claim's:
    "the oldest" was review R11's bug, and it survived the fix as the
    no-token call until re-checked. The hourly attempt stays counted. The
    caller holds _lock."""
    running = _in_flight.get(client)
    mine = [e for e in running or [] if e[1] == token]
    if not mine:
        return
    running.remove(mine[0])
    if not running:
        del _in_flight[client]


def _fund(client: str, day: str, now: float, kind: str, mode: str) -> None:
    """The day's slot, the person's daily allowance and the money — all of
    them, or none.

    `_lock` guards ONLY the in-memory allowance, never a database call.
    REPRODUCED (review R15, real uvicorn): a claim held the lock across its
    SQLite write, which waits up to the 30 s busy timeout behind another
    writer, while release() and admit() — called on the EVENT LOOP — took the
    same lock: every page, stream and poll froze (/health ~7 s). The slot and
    the money are each one conditional statement, atomic in the database on
    their own; the allowance is taken tentatively first and given back if
    either is refused.
    """
    if _daily_full(day):
        raise _day_is_full(client, now, "slots")
    with _lock:
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
        _person_today[client] = _person_today.get(client, 0) + 1
    try:
        try:
            granted = _daily.take(day, settings.max_checks_per_day)
        except Exception as exc:  # noqa: BLE001 — fail closed, never open
            print(f"[limits] daily counter unwritable: {type(exc).__name__}: {exc}")
            raise HTTPException(503, "The service is busy right now. "
                                     "Please try again in a minute.") from exc
        if not granted:
            raise _day_is_full(client, now, "slots")
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
            raise _day_is_full(client, now, "money")
    except BaseException:
        give_back_person(client, day)     # the tentative allowance
        raise


def admit(request: Request, subject: str | None = None,
          token: str | None = None) -> str | None:
    """Phase 1, before ANY work: the person's place in line, and nothing
    anyone else needs. -> True if recorded (False: rate limiting is off).

    For checks whose first steps are FREE but slow — a link's resolve, an
    upload's decode. REPRODUCED 2026-10-15 (review R1): while those held a
    daily slot (and, with the budget, $0.30 of the day's $1), five people
    with slow, refused links locked everyone else out, leaving no trace.
    In memory only, so it is safe to call on the event loop.
    """
    if not settings.rate_limit_enabled:
        return None
    client = subject or subject_of(request)
    token = token or uuid.uuid4().hex
    with _lock:
        _admit_locked(client, _now(), token)
    return token


def fund(request: Request, subject: str | None = None, kind: str = "text",
         mode: str = "full") -> str | None:
    """Phase 2, right before the first PAID step: the day's slot, the
    person's allowance and the money. -> the day charged (None if off).

    The slot is taken by a single conditional UPSERT and the money by
    another, so the DATABASE refuses past the cap or the budget even if two
    processes ever raced here. Anything that stops either being recorded
    refuses the check: this guard fails closed.
    """
    if not settings.rate_limit_enabled:
        return None
    client = subject or subject_of(request)
    day = today()
    _fund(client, day, _now(), kind, mode)
    return day


def reserve(request: Request, subject: str | None = None,
            kind: str = "text", mode: str = "full",
            token: str | None = None) -> str | None:
    """Both phases at once, for checks whose first step is already paid
    (text, image): claim one check, or raise 429. -> the day charged.

    Checking and claiming MUST be atomic. An earlier version checked here and
    consumed later, after the upload had been read and transcoded — 30
    simultaneous uploads from one IP all saw an empty counter and all passed
    a 2/day cap (measured). Rejected submissions get their claim back via
    refund() instead, so nothing is charged for work that never happened.

    A granted claim also starts the person's check IN FLIGHT; whoever ends
    the check — the route on a refusal, the background job otherwise — calls
    release(). Until then the same person is refused, without a slot taken.
    """
    if not settings.rate_limit_enabled:
        return None
    client = subject or subject_of(request)
    now, day = _now(), today()
    # A visitor over BOTH limits should hear "try tomorrow", not "try in an
    # hour". A database read: outside the lock (review R15).
    if _daily_full(day):
        raise _day_is_full(client, now, "slots")
    token = token or uuid.uuid4().hex
    with _lock:
        _admit_locked(client, now, token)
    try:
        _fund(client, day, now, kind, mode)
    except BaseException:
        with _lock:
            _unadmit_locked(client, token)
        raise
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
           mode: str = "full", subject: str | None = None) -> None:
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
    give_back_person(subject or subject_of(request), day)


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


def release(subject: str | None, token: str | None) -> None:
    """The person's check has ended — answered, failed, refused or refunded —
    so their next one may start. Exactly its claim's `token` entry goes, and
    a second release of the same token does nothing (the engine releases
    early, the job's `finally` again as a backstop). The token is REQUIRED:
    a release that names no claim cannot free one (review R11). Safe to call
    for a subject with nothing running."""
    if not subject:
        return
    with _lock:
        _unadmit_locked(subject, token)


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
        _paused_until[0] = 0.0
