"""A spending guard for the public share link.

`share_demo.ps1` puts this app on a public URL, and every check spends real
money. Anyone with the link — or anyone a friend forwards it to — can submit
claims, so an in-process limiter caps how much a single visitor, and the
deployment as a whole, can spend before someone has to intervene.

Deliberately simple: an in-memory counter, no Redis, reset on restart. It
protects a wallet on a laptop, not a datacentre.
"""
import threading
import time

from fastapi import HTTPException, Request

from app.config import settings

_MAX_TRACKED_CLIENTS = 512

_lock = threading.Lock()
_per_client: dict[str, list[float]] = {}
_day: list[float] = []


def _prune(stamps: list[float], window_s: float, now: float) -> list[float]:
    return [t for t in stamps if now - t < window_s]


def _client_of(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check_limit(request: Request) -> None:
    """Raise 429 if this visitor has no quota left. Does NOT consume any."""
    if not settings.rate_limit_enabled:
        return
    now = time.monotonic()
    with _lock:
        global _day
        _day = _prune(_day, 86400, now)
        if len(_day) >= settings.max_checks_per_day:
            raise HTTPException(
                429,
                "This demo has reached its daily limit of "
                f"{settings.max_checks_per_day} checks. Please try tomorrow.",
            )
        mine = _prune(_per_client.get(_client_of(request), []), 3600, now)
        if len(mine) >= settings.max_checks_per_hour:
            raise HTTPException(
                429,
                f"You've used {settings.max_checks_per_hour} checks this hour — "
                "that's the limit for this demo. Please try again later.",
            )


def count(request: Request) -> None:
    """Consume one check. Called only once a submission reaches paid work,
    so a rejected upload (wrong type, too big) never costs someone's quota."""
    if not settings.rate_limit_enabled:
        return
    now = time.monotonic()
    client = _client_of(request)
    with _lock:
        global _day
        _day = _prune(_day, 86400, now)
        _day.append(now)
        _per_client[client] = _prune(_per_client.get(client, []), 3600, now) + [now]
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


def reset() -> None:
    """Test helper — clears all counters."""
    with _lock:
        _per_client.clear()
        _day.clear()
