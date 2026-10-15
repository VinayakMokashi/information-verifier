"""The spending dashboard — for the person paying the bill, on this machine only.

    http://127.0.0.1:8000/dashboard

Everything here comes from the spend ledger (costs and kinds, never a message)
and the persisted daily-cap counter. It is the app's own record: what each
check measured from the API's usage fields, priced at list prices. The
Anthropic console remains the source of truth for the invoice.

LOCAL ONLY, and deliberately so. `share_demo.ps1` puts this app on a public
URL, and what the owner spends is nobody else's business. A request is served
only when app/api/local.py says it came from this machine (loopback, no proxy
header, a local Host — the tunnel and DNS rebinding are explained there).
Anything else gets a 404 — not a 403, which would announce that something is
here.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.api import limits
from app.api.local import is_this_machine
from app.config import settings
from app.store.repository import SpendLedger, operator_day

router = APIRouter()
_ledger = SpendLedger()
_PAGE = Path(__file__).resolve().parent / "dashboard.html"


def _local_only(request: Request) -> None:
    if not is_this_machine(request):
        raise HTTPException(404, "Not Found")


def _day_minus(day: str, n: int) -> str:
    return (datetime.fromisoformat(day) - timedelta(days=n)).date().isoformat()


@router.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request) -> HTMLResponse:
    _local_only(request)
    return HTMLResponse(_PAGE.read_text(encoding="utf-8"),
                        headers={"Cache-Control": "no-store"})


@router.get("/api/v1/admin/spend", include_in_schema=False)
def spend(request: Request, days: int = 30) -> dict:
    """A plain `def`, so FastAPI runs it on its thread pool: every line below
    is a SQLite read, and on the event loop a slow one held up every page,
    poll and live stream (measured: the loop stood still 1.04 s behind a
    1 s read; R15's rule)."""
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
    # The day's MONEY (Vinayak, 2026-10-15: $1 a day, cheaper as it drains):
    # settled costs plus what running checks hold. The count above is only
    # a backstop since then.
    try:
        committed = round(limits._budget.committed(today), 6)
        mode = limits.budget_mode(today)
    except Exception:  # noqa: BLE001 — the page still shows spend without it
        committed, mode = None, None

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "today": today,
        "days": days,
        "cap": {"used": cap_used, "limit": settings.max_checks_per_day,
                "enforced": settings.rate_limit_enabled,
                "resets": limits._reset_label()},
        "budget": {"limit_usd": settings.daily_budget_usd, "committed_usd": committed,
                   "mode": mode, "paused": limits.paused(),
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
