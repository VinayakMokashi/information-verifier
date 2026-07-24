"""The orchestrator: raw text -> Truth Report.

Flow: normalize -> extract -> (cache gate -> retrieve -> adjudicate) per
claim, fanned out concurrently -> aggregate -> persist. Claims are checked
in parallel, so a 5-claim submission takes roughly the time of one.

Runs inside a FastAPI BackgroundTask. Any failure marks the job FAILED and
records the error rather than crashing the worker; a single bad claim can't
sink the whole report.
"""
import asyncio
from datetime import datetime, timezone

from app.engine.adjudicate import adjudicate
from app.engine.aggregate import build_summary, overall_rating
from app.engine.extract import extract_claims
from app.engine.normalize import normalize
from app.engine.retrieve import gather_evidence
from app.models.claim import Claim
from app.models.report import ClaimVerdict, JobStatus, TruthReport
from app.models.verdict import Rating, Verdict
from app.store.repository import ReportRepository


async def _process_claim(claim: Claim, repo: ReportRepository) -> ClaimVerdict:
    cached = repo.cache.get(claim.text)
    if cached is not None:
        return ClaimVerdict(claim=claim, verdict=cached, cache_hit=True)

    try:
        evidence = await gather_evidence(claim)
        verdict = await adjudicate(claim, evidence)
    except Exception as exc:  # noqa: BLE001 — a claim failure must stay visible
        # Surface the failure as an explicit UNVERIFIED verdict rather than
        # dropping the claim (which would masquerade as "no claims found").
        # Not cached: a transient error shouldn't poison future runs.
        return ClaimVerdict(
            claim=claim,
            verdict=Verdict(
                rating=Rating.UNVERIFIED,
                confidence=0,
                reasoning=f"This claim could not be checked due to a processing "
                f"error ({type(exc).__name__}). Please retry.",
                correction="",
                citations=[],
            ),
            cache_hit=False,
        )

    repo.cache.put(claim.text, verdict)
    return ClaimVerdict(claim=claim, verdict=verdict, cache_hit=False)


async def run_pipeline(job_id: str, raw_text: str, repo: ReportRepository) -> None:
    report = repo.get(job_id)
    if report is None:  # defensive: job row should already exist
        return

    try:
        report.status = JobStatus.PROCESSING
        repo.save(report)

        norm = await normalize(raw_text)
        report.input_language = norm.detected_language

        claims = await extract_claims(norm.english_text)
        checkworthy = [c for c in claims if c.checkworthy]

        results = await asyncio.gather(
            *(_process_claim(c, repo) for c in checkworthy),
            return_exceptions=True,
        )
        verdicts = [r for r in results if isinstance(r, ClaimVerdict)]

        report.claim_verdicts = verdicts
        report.overall_rating = overall_rating(verdicts)
        report.summary = build_summary(verdicts, report.overall_rating)
        report.status = JobStatus.COMPLETE
    except Exception as exc:  # noqa: BLE001 — surface any failure into the report
        report.status = JobStatus.FAILED
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.completed_at = datetime.now(timezone.utc)
        repo.save(report)
