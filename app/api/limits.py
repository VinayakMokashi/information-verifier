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

_lock = threading.Lock()
_per_client: dict[str, list[float]] = {}
_day: list[float] = []


def _prune(stamps: list[float], window_s: float, now: float) -> list[float]:
    return [t for t in stamps if now - t < window_s]


def check_and_count(request: Request) -> None:
    """Raise 429 if this submission would exceed a limit; else count it."""
    if not settings.rate_limit_enabled:
        return
    client = request.client.host if request.client else "unknown"
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
        mine = _prune(_per_client.get(client, []), 3600, now)
        if len(mine) >= settings.max_checks_per_hour:
            raise HTTPException(
                429,
                f"You've used {settings.max_checks_per_hour} checks this hour — "
                "that's the limit for this demo. Please try again later.",
            )
        mine.append(now)
        _per_client[client] = mine
        _day.append(now)


def reset() -> None:
    """Test helper — clears all counters."""
    with _lock:
        _per_client.clear()
        _day.clear()
