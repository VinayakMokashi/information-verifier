"""FREE offline demo — the REAL engine plumbing with a SIMULATED Claude. $0.

No API key, no cost, no network. It swaps the one paid seam (`engine.chat.
answer`) for a canned reply that streams word-by-word, then runs the genuine
job runner, cache, storage and rendering exactly as production would. Proves
the plumbing and shows the shape of a real answer.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\demo_offline.py

RUN 1 streams (that is the pivot, visible); RUN 2 is served from the answer
cache, which is why the simulated-call counter does not move.
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Make `app` and `scripts` importable no matter how this is launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_PATH", "./data/demo.db")

from app.models.answer import Answer, JobStatus  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.store.repository import AnswerRepository  # noqa: E402
from scripts.fake_stages import CALLS, apply_fake_stages  # noqa: E402
from scripts.render import force_utf8_stdout, print_answer  # noqa: E402

apply_fake_stages()

from app.engine.job import run_check  # noqa: E402  (import after patching)


class ConsoleStream:
    """Enough of JobStream for the console: print the answer as it arrives.

    Only `publish` is used by `run_check`, so this stays a duck rather than a
    subclass — a demo must not be able to drift from the real stream's
    behaviour by inheriting half of it.
    """

    async def publish(self, kind: str, data: dict) -> None:
        if kind == "status":
            print(f"\n[{data.get('text', '')}]")
        elif kind == "text":
            print(data.get("text", ""), end="", flush=True)
        elif kind == "tier":
            print("\n\n--- no fact-checker covered this; general web below ---")
        elif kind == "source":
            print(f"\n  [source: {data.get('url', '')}]", end="", flush=True)
        elif kind == "done":
            print()


async def main() -> None:
    force_utf8_stdout()
    db = os.environ["DB_PATH"]
    if os.path.exists(db):
        os.remove(db)  # fresh cache so RUN 1 is always "cold"
    init_db()
    repo = AnswerRepository()

    text = ("WHO ne kaha hai ki 5G se coronavirus phailta hai. "
            "5G se immunity bhi kamzor hoti hai.")

    def new_job() -> Answer:
        a = Answer(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                   created_at=datetime.now(timezone.utc), input_text=text)
        repo.save(a)
        return a

    print("\n########## RUN 1  (cold - simulated answer streams in) ##########")
    j1 = new_job()
    await run_check(j1.job_id, text, repo, ConsoleStream())
    print_answer(repo.get(j1.job_id))
    print(f"[simulated engine calls so far: {CALLS['answer']}]")

    print("\n########## RUN 2  (same message - should hit the cache) ##########")
    j2 = new_job()
    await run_check(j2.job_id, text, repo)
    print_answer(repo.get(j2.job_id))
    print(f"[simulated engine calls so far: {CALLS['answer']}]"
          "  <- unchanged => the cache answered, no new work")


if __name__ == "__main__":
    asyncio.run(main())
