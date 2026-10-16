"""The privacy notice and the terms of use — public pages with no script.

Served by the app rather than from static/, because what they say must stay
true of what the code does: how long things are kept is read from the same
settings the deleting code reads, so changing a period changes the notice.
Who runs the service and where to write come from .env (OPERATOR_NAME,
CONTACT_EMAIL): publishing a person's name and address is the owner's
decision, not the repo's. Everything substituted is escaped.

The drafting rules are docs/research/2026-10-15/policy-legal.md's
recommendation as its verification corrected it (PROJECT_PLAN §7, 2026-10-16).
"""
import html
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.config import settings

router = APIRouter()
_HERE = Path(__file__).resolve().parent

NO_CONTACT = ("the contact address, which is published here before the service "
              "opens to the public")


def _count(n: int, unit: str) -> str:
    return f"{n} {unit}" if n == 1 else f"{n} {unit}s"


def _span(hours: int) -> str:
    """A lifetime in hours as a reader says it: 168 is "7 days", 36 stays
    "36 hours" — rounding it to a day and a half's "2 days" would overstate,
    and to "1 day" would promise a deletion that has not happened."""
    return _count(hours // 24, "day") if hours % 24 == 0 else _count(hours, "hour")


def _contact() -> str:
    email = settings.contact_email.strip()
    if not email:
        return f"<em>{NO_CONTACT}</em>"
    shown = html.escape(email, quote=True)
    return f'<a href="mailto:{shown}">{shown}</a>'


def _operator() -> str:
    return html.escape(settings.operator_name.strip()) or "an individual"


def render(name: str) -> str:
    page = (_HERE / name).read_text(encoding="utf-8")
    values = {
        "operator": _operator(),
        "contact": _contact(),
        "retention": _count(settings.answer_retention_days, "day"),
        # AnswerCache.prune deletes at the LONGER of its two lifetimes.
        "cache": _span(max(settings.answer_cache_ttl_trusted_h,
                           settings.answer_cache_ttl_web_h)),
        "transcripts": _count(settings.transcript_cache_ttl_days, "day"),
    }
    for key, value in values.items():
        page = page.replace("{{" + key + "}}", value)
    return page


# Plain `def`s: reading the file is blocking I/O, so it belongs on the thread
# pool, not on the event loop every check's stream shares (review R15).
@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
def privacy() -> HTMLResponse:
    return HTMLResponse(render("privacy.html"))


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
def terms() -> HTMLResponse:
    return HTMLResponse(render("terms.html"))
