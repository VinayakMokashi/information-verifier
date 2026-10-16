"""Delete a check on request, before its retention period is up. Free, local.

The privacy notice and the bot's /delete promise it: a person writes to the
contact address with the answer page's address (it ends in #job=...) or with
the message and the day they sent it, and the owner deletes it — with this.

    .venv\\Scripts\\python.exe scripts\\forget.py --job 3f2a9c...
    .venv\\Scripts\\python.exe scripts\\forget.py --text "words from the message" --day 2026-10-16

It lists what matches and deletes nothing until run again with --yes. What
goes: the check's row (the message, what a machine read from it, the answer)
and every cached answer to the same message. What stays: the spend ledger's
row, which never held the message (invariant 10). A check still running is
left alone — the job saves its row again when it ends — so run this again
once it has finished. Uses DB_PATH from .env, like the app; it can run while
the app is up.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.models.answer import JobStatus  # noqa: E402
from app.store.repository import AnswerRepository, operator_day  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402

_FINISHED = (JobStatus.COMPLETE, JobStatus.FAILED)
_SNIPPET = 60


def _snippet(answer) -> str:
    said = " ".join((answer.input_text or answer.source_text or "").split())
    return said if len(said) <= _SNIPPET else said[:_SNIPPET - 1] + "…"


def main(argv: list[str] | None = None) -> int:
    """0: listed or deleted; 1: nothing matched; 2: no database there."""
    parser = argparse.ArgumentParser(description="Delete a check on request.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--job", help="the id after #job= in the answer page's address")
    which.add_argument("--text", help="words from the message, or from what was read from it")
    parser.add_argument("--day", help="YYYY-MM-DD: the day it was sent, India time")
    parser.add_argument("--yes", action="store_true", help="delete what is listed")
    args = parser.parse_args(argv)
    force_utf8_stdout()          # messages are often in Hindi

    if not os.path.exists(settings.db_path):
        # Never create one: a mistyped DB_PATH would "succeed" on an empty file.
        print(f"No database at {settings.db_path} — check DB_PATH in .env.")
        return 2
    repo = AnswerRepository()
    if args.job:
        answer = repo.get(args.job.strip())
        found = [answer] if answer else []
    else:
        found = repo.find(args.text, day=args.day)
    if not found:
        print("No check matches (deleted already, or older than "
              f"{settings.answer_retention_days} days and so gone anyway?).")
        return 1

    print(f"{len(found)} check{'' if len(found) == 1 else 's'} match:")
    for answer in found:
        print(f"  {answer.job_id}  {operator_day(answer.created_at)}  "
              f"{answer.status.value:<10}  {_snippet(answer)}")
    finished = [a for a in found if a.status in _FINISHED]
    running = [a for a in found if a.status not in _FINISHED]
    if running:
        print(f"{len(running)} still running: left alone (a running check saves "
              "itself again when it ends) — run this again once it has finished.")
    if not args.yes:
        print("Nothing deleted. Run again with --yes to delete the finished ones, "
              "with every cached answer to the same message.")
        return 0
    gone, copies = repo.forget(finished)
    print(f"Deleted {gone} check{'' if gone == 1 else 's'} and {copies} cached "
          f"cop{'y' if copies == 1 else 'ies'}. The spend ledger keeps its rows: "
          "they never held a message.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
