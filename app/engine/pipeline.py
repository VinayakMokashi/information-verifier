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
from app.engine.equivalence import claims_equivalent
from app.engine.extract import extract_claims
from app.engine.normalize import normalize
from app.engine.retrieve import gather_evidence
from app.models.claim import Claim
from app.models.report import ClaimVerdict, JobStatus, TruthReport
from app.models.verdict import Rating, Verdict
from app.store.repository import ReportRepository


async def _cache_call(fn, *args):
    """Run a cache operation off the event loop, never letting it sink a claim.

    The cache is an optimization: a locked DB, a corrupt cached row, or a
    failed embedding must degrade to doing the real work — never discard a
    verdict we already paid for, and never surface as "no claims found".
    Cache calls also run in a worker thread because the semantic tier embeds
    on CPU (lazy-loading the model on first use), which would block the loop.
    """
    try:
        return await asyncio.to_thread(fn, *args)
    except Exception as exc:  # noqa: BLE001 — see above
        print(f"[cache] {getattr(fn, '__name__', fn)} failed: {type(exc).__name__}: {exc}")
        return None


async def _process_claim(claim: Claim, repo: ReportRepository) -> ClaimVerdict:
    cached = await _cache_call(repo.cache.get, claim.text)
    if cached is not None:
        return ClaimVerdict(claim=claim, verdict=cached, cache_hit=True)

    # Semantic tier: the vector index only NOMINATES a near-neighbour; a
    # cheap Haiku check must confirm it is the same claim before the cached
    # verdict is served (one-token-different claims embed deceptively close).
    candidate = await _cache_call(repo.cache.nearest, claim.text)
    if candidate is not None:
        try:
            if await claims_equivalent(claim.text, candidate.text):
                # Learn this phrasing so next time it's an exact (free) hit.
                # index=False: aliases must never become nomination anchors,
                # or hops would drift away from the adjudicated claim.
                await _cache_call(repo.cache.put, claim.text, candidate.verdict, False)
                return ClaimVerdict(claim=claim, verdict=candidate.verdict, cache_hit=True)
        except Exception as exc:  # noqa: BLE001 — confirmation is an optimization
            print(f"[cache] equivalence check failed, doing a full check: "
                  f"{type(exc).__name__}: {exc}")

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

    await _cache_call(repo.cache.put, claim.text, verdict)
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
