"""FREE offline demo — runs the REAL pipeline with FAKE (simulated) LLM stages.

No API key, no cost, no network. It swaps the paid stages
(normalize / extract / retrieve / adjudicate) for canned responses, then runs
the genuine pipeline, cache, aggregation, storage, and Truth Report exactly as
production would. Proves the plumbing and shows the shape of a real report.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\demo_offline.py
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

# Make `app` and `scripts` importable no matter how this is launched.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DB_PATH", "./data/demo.db")
os.environ.setdefault("SEMANTIC_CACHE_ENABLED", "false")  # demo stays model-free

from app.engine import pipeline as P  # noqa: E402
from app.models.report import JobStatus, TruthReport  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.store.repository import ReportRepository  # noqa: E402
from scripts.fake_stages import CALLS, apply_fake_stages  # noqa: E402
from scripts.render import print_report  # noqa: E402

apply_fake_stages()


async def main() -> None:
    db = os.environ["DB_PATH"]
    if os.path.exists(db):
        os.remove(db)  # fresh cache so RUN 1 is always "cold"
    init_db()
    repo = ReportRepository()

    text = ("WHO ne kaha hai ki 5G se coronavirus phailta hai. "
            "5G se immunity bhi kamzor hoti hai.")

    def new_job() -> TruthReport:
        r = TruthReport(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                        created_at=datetime.now(timezone.utc))
        repo.save(r)
        return r

    print("\n########## RUN 1  (cold - simulated adjudication runs) ##########")
    j1 = new_job()
    await P.run_pipeline(j1.job_id, text, repo)
    print_report(repo.get(j1.job_id))
    print(f"[simulated adjudication calls so far: {CALLS['adjudicate']}]")

    print("\n########## RUN 2  (same claims - should hit the cache) ##########")
    j2 = new_job()
    await P.run_pipeline(j2.job_id, text, repo)
    print_report(repo.get(j2.job_id))
    print(f"[simulated adjudication calls so far: {CALLS['adjudicate']}]"
          "  <- unchanged => cache served the verdicts, no new work")


if __name__ == "__main__":
    asyncio.run(main())
