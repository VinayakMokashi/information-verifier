"""Delete a check on request, before its retention period is up. Free, local.

The privacy notice and the bot's /delete promise it: a person writes to the
contact address with the answer page's address (it ends in #job=...) or with
the message and the day they sent it, and the owner deletes it — with this.

    .venv\\Scripts\\python.exe scripts\\forget.py --job "<the address they sent, or its id>"
    .venv\\Scripts\\python.exe scripts\\forget.py --text "words, or the reel link" --day 2026-10-16

It lists what matches, with each one's time, and deletes nothing until run
again with --yes. One forward is often checked by many people (review
S5-18): when words match several checks, --yes deletes none of them — pick
the person's own with --job and its time, or add --all to mean all of them.

What goes: the check's row (what was sent, what a machine read from it, the
answer), every cached answer to the same message, and what a public post
said when one was checked. What stays: the spend ledger's row, which never
held the message (invariant 10). A check still running is left alone — the
job saves its row again when it ends — so run this again once it has
finished. Uses DB_PATH from .env, like the app; it can run while the app is
up.
"""
import argparse
import os
import re
import sys
from datetime import timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.models.answer import JobStatus  # noqa: E402
from app.store.repository import AnswerRepository  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402

_FINISHED = (JobStatus.COMPLETE, JobStatus.FAILED)
_SNIPPET = 60
# The page's own rule for a job id in its address (static/index.html).
_JOB_IN_ADDRESS = re.compile(r"job=([a-f0-9]{8,64})", re.IGNORECASE)


def _snippet(answer) -> str:
    said = " ".join((answer.input_text or answer.source_text or "").split())
    return said if len(said) <= _SNIPPET else said[:_SNIPPET - 1] + "…"


def _when(answer) -> str:
    """Day and time as the person would say them: India's (the operator's)."""
    local = (answer.created_at.astimezone(timezone.utc)
             + timedelta(minutes=settings.day_boundary_utc_offset_min))
    return local.strftime("%Y-%m-%d %H:%M")


def _job_id(given: str) -> str:
    """An id, or the whole address it came in (review S5-7: pasted as sent,
    the address matched nothing)."""
    found = _JOB_IN_ADDRESS.search(given)
    return found.group(1).lower() if found else given.strip()


def main(argv: list[str] | None = None) -> int:
    """0: listed or deleted; 1: nothing matched; 2: no database there."""
    parser = argparse.ArgumentParser(description="Delete a check on request.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--job", help="the answer page's address, or the id after #job=")
    which.add_argument("--text", help="words from the message, the reel link, or words "
                                      "read from a voice note or screenshot")
    parser.add_argument("--day", help="YYYY-MM-DD: the day it was sent, India time")
    parser.add_argument("--yes", action="store_true", help="delete what is listed")
    parser.add_argument("--all", action="store_true",
                        help="with --text: delete every match, not only a single one")
    args = parser.parse_args(argv)
    force_utf8_stdout()          # messages are often in Hindi

    if not os.path.exists(settings.db_path):
        # Never create one: a mistyped DB_PATH would "succeed" on an empty file.
        print(f"No database at {settings.db_path} — check DB_PATH in .env.")
        return 2
    repo = AnswerRepository()
    if args.job:
        answer = repo.get(_job_id(args.job))
        found = [answer] if answer else []
    else:
        found = repo.find(args.text, day=args.day)
    if not found:
        print("No check matches. A reel is found by its link; a voice note or a "
              "screenshot by the words read from it; any check by its #job= address "
              f"(paste it whole). After {settings.answer_retention_days} days a check "
              "is deleted anyway.")
        return 1

    print(f"{len(found)} check{'' if len(found) == 1 else 's'} match:")
    for answer in found:
        print(f"  {answer.job_id}  {_when(answer)}  {answer.status.value:<10}  "
              f"{_snippet(answer)}")
    finished = [a for a in found if a.status in _FINISHED]
    running = [a for a in found if a.status not in _FINISHED]
    if running:
        print(f"{len(running)} still running: left alone (a running check saves "
              "itself again when it ends) — run this again once it has finished.")
    if not args.yes:
        print("Nothing deleted. Run again with --yes to delete the finished ones, "
              "with every cached answer to the same message.")
        return 0
    if args.text and len(finished) > 1 and not args.all:
        # Strangers often send the same forward: deleting every match would
        # delete their checks too, with no request from them.
        print("Nothing deleted: these may be different people's checks of the same "
              "message. Delete the person's own with --job <id> (match the time), "
              "or add --all to delete every one listed.")
        return 0
    gone = repo.forget(finished)
    print(f"Deleted {gone.answers} check{'' if gone.answers == 1 else 's'}, "
          f"{gone.cached} cached cop{'y' if gone.cached == 1 else 'ies'} and "
          f"{gone.transcripts} transcript{'' if gone.transcripts == 1 else 's'} of a "
          "public post. The spend ledger keeps its rows: they never held a message.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
