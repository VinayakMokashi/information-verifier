"""REAL end-to-end test — one claim through the live pipeline. COSTS MONEY.

Needs ANTHROPIC_API_KEY in .env. Calls Opus/Haiku + web search (a few cents).

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\smoke_test.py
    .venv\\Scripts\\python.exe scripts\\smoke_test.py "your claim here"
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.engine.pipeline import run_pipeline  # noqa: E402
from app.models.report import JobStatus, TruthReport  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.store.repository import ReportRepository  # noqa: E402
from scripts.render import render_report  # noqa: E402


async def main() -> None:
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY found in .env. Add it first. Aborting (no cost).")
        return

    claim = sys.argv[1] if len(sys.argv) > 1 else \
        "WHO ne kaha hai ki 5G se coronavirus phailta hai."

    print(">> This calls the PAID Anthropic API + web search (a few cents).")
    print(f">> Checking: {claim}\n")

    init_db()
    repo = ReportRepository()
    report = TruthReport(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                         created_at=datetime.now(timezone.utc))
    repo.save(report)

    await run_pipeline(report.job_id, claim, repo)
    print(render_report(repo.get(report.job_id)))


if __name__ == "__main__":
    asyncio.run(main())
