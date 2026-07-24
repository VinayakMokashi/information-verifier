"""FREE offline demo — runs the REAL pipeline with FAKE (simulated) LLM stages.

No API key, no cost, no network. It swaps the four paid stages
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

from app.engine import pipeline as P  # noqa: E402
from app.models.claim import Claim  # noqa: E402
from app.models.evidence import Evidence, Source  # noqa: E402
from app.models.report import JobStatus, TruthReport  # noqa: E402
from app.models.verdict import Rating, Verdict  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.store.repository import ReportRepository  # noqa: E402
from scripts.render import render_report  # noqa: E402

CALLS = {"adjudicate": 0}  # counts simulated "LLM" adjudications to prove caching


# ---------------------------------------------------------------------------
# Fake stages — stand in for the paid Opus/Haiku calls.
# ---------------------------------------------------------------------------
class _Norm:
    detected_language = "hi"
    english_text = (
        "The World Health Organization stated that 5G technology spreads the "
        "coronavirus. 5G radiation also weakens the human immune system."
    )


async def fake_normalize(text: str) -> _Norm:
    return _Norm()


async def fake_extract(english_text: str) -> list[Claim]:
    return [
        Claim(
            text="The World Health Organization stated that 5G technology spreads the coronavirus.",
            subject="World Health Organization",
            claim_type="attribution",
            checkworthy=True,
        ),
        Claim(
            text="5G radiation weakens the human immune system.",
            subject="5G technology",
            claim_type="causal",
            checkworthy=True,
        ),
        Claim(  # non-checkworthy -> pipeline should drop it
            text="People should stay away from 5G towers to be safe.",
            subject="people",
            claim_type="other",
            checkworthy=False,
        ),
    ]


async def fake_gather(claim: Claim) -> Evidence:
    return Evidence(
        summary=(
            "Trusted fact-checkers and the WHO found no link between 5G and COVID-19. "
            "The virus spreads via respiratory droplets, not radio waves."
        ),
        sources=[
            Source(
                url="https://www.boomlive.in/health/5g-coronavirus-fake",
                title="No, 5G Does Not Spread Coronavirus",
                publisher="boomlive.in",
            ),
            Source(
                url="https://www.reuters.com/article/factcheck-5g-covid",
                title="Fact check: 5G does not cause or spread COVID-19",
                publisher="reuters.com",
            ),
        ],
    )


async def fake_adjudicate(claim: Claim, evidence: Evidence) -> Verdict:
    CALLS["adjudicate"] += 1
    return Verdict(
        rating=Rating.FALSE,
        confidence=97,
        reasoning=(
            "Multiple trusted fact-checkers and the WHO confirm there is no link "
            "between 5G and the coronavirus; viruses cannot travel on radio waves."
        ),
        correction=(
            "COVID-19 is caused by the SARS-CoV-2 virus and spreads through "
            "respiratory droplets. 5G is radio-frequency radiation and plays no "
            "role in its transmission."
        ),
        citations=[
            {"url": "https://www.boomlive.in/health/5g-coronavirus-fake",
             "title": "No, 5G Does Not Spread Coronavirus", "publisher": "boomlive.in"},
            {"url": "https://www.reuters.com/article/factcheck-5g-covid",
             "title": "Fact check: 5G does not cause or spread COVID-19", "publisher": "reuters.com"},
        ],
    )


# Patch the four seams the pipeline calls.
P.normalize = fake_normalize
P.extract_claims = fake_extract
P.gather_evidence = fake_gather
P.adjudicate = fake_adjudicate


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
    print(render_report(repo.get(j1.job_id)))
    print(f"[simulated adjudication calls so far: {CALLS['adjudicate']}]")

    print("\n########## RUN 2  (same claims - should hit the cache) ##########")
    j2 = new_job()
    await P.run_pipeline(j2.job_id, text, repo)
    print(render_report(repo.get(j2.job_id)))
    print(f"[simulated adjudication calls so far: {CALLS['adjudicate']}]"
          "  <- unchanged => cache served the verdicts, no new work")


if __name__ == "__main__":
    asyncio.run(main())
