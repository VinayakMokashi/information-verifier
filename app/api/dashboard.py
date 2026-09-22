"""The spending dashboard — for the person paying the bill, on this machine only.

    http://127.0.0.1:8000/dashboard

Everything here comes from the spend ledger (costs and kinds, never a message)
and the persisted daily-cap counter. It is the app's own record: what each
check measured from the API's usage fields, priced at list prices. The
Anthropic console remains the source of truth for the invoice.

LOCAL ONLY, and deliberately so. `share_demo.ps1` puts this app on a public
URL, and what the owner spends is nobody else's business. A request is served
only when it arrived from this machine AND carries no proxy header: the
cloudflared tunnel connects from 127.0.0.1 but always adds X-Forwarded-For /
CF-Connecting-IP (and uvicorn's default proxy handling rewrites the client to
the visitor's IP anyway). Anything else gets a 404 — not a 403, which would
announce that something is here.

The Host header is checked too. Found by review, reproduced: DNS rebinding —
a page the owner visits re-resolves its own name to 127.0.0.1, and its
same-origin fetch then arrives from this machine with no proxy header. The
connection cannot tell that apart; the Host header can, because the browser
still sends the attacker's name.
"""
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.api import limits
from app.config import settings
from app.store.repository import SpendLedger, operator_day

router = APIRouter()
_ledger = SpendLedger()
_PAGE = Path(__file__).resolve().parent / "dashboard.html"

_LOCAL_HOSTS = {"127.0.0.1", "::1"}
_PROXY_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip",
                  "cf-connecting-ip", "true-client-ip", "x-forwarded-host")
# The names this machine is asked for by, with an optional port. Exact match:
# anything a DNS name could be registered as must fail.
_LOCAL_HOST_HEADER = re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::\d{1,5})?",
                                re.IGNORECASE)


def _local_only(request: Request) -> None:
    peer = request.client.host if request.client else ""
    if (peer not in _LOCAL_HOSTS
            or any(h in request.headers for h in _PROXY_HEADERS)
            or not _LOCAL_HOST_HEADER.fullmatch(request.headers.get("host", ""))):
        raise HTTPException(404, "Not Found")


def _day_minus(day: str, n: int) -> str:
    return (datetime.fromisoformat(day) - timedelta(days=n)).date().isoformat()


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request) -> HTMLResponse:
    _local_only(request)
    return HTMLResponse(_PAGE.read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@router.get("/api/v1/admin/spend", include_in_schema=False)
async def spend(request: Request, days: int = 30) -> dict:
    _local_only(request)
    days = max(1, min(days, 366))
    today = operator_day(datetime.now(timezone.utc))
    since = _day_minus(today, days - 1)

    # Every day in the range, zero-filled, so the time axis is continuous — a
    # day with no checks is a real $0, not a missing column.
    spent = {row["day"]: row for row in _ledger.by_day(since)}
    series = []
    for i in range(days):
        day = _day_minus(today, days - 1 - i)
        row = spent.get(day) or {}
        series.append({"day": day, "checks": row.get("checks", 0),
                       "cached": row.get("cached", 0),
                       "usd": round(row.get("usd") or 0.0, 4),
                       "llm_usd": round(row.get("llm_usd") or 0.0, 4),
                       "search_usd": round(row.get("search_usd") or 0.0, 4),
                       "asr_usd": round(row.get("asr_usd") or 0.0, 4)})

    try:
        cap_used = limits.used_today()
    except Exception:  # noqa: BLE001 — the page still shows spend without it
        cap_used = None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": today,
        "days": days,
        "cap": {"used": cap_used, "limit": settings.max_checks_per_day,
                "enforced": settings.rate_limit_enabled,
                "resets": limits._reset_label()},
        "totals": {
            "today": _ledger.totals(today),
            "d7": _ledger.totals(_day_minus(today, 6)),
            "d30": _ledger.totals(_day_minus(today, 29)),
            "all": _ledger.totals(),
            "range": _ledger.totals(since),
        },
        "by_day": series,
        "recent": _ledger.recent(25),
        "retention_days": settings.answer_retention_days,
    }
