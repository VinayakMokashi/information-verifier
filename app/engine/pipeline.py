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

from app.config import settings
from app.engine.adjudicate import adjudicate
from app.engine.aggregate import build_summary, overall_rating
from app.engine.equivalence import claims_equivalent
from app.engine.extract import extract_claims
from app.engine.normalize import normalize
from app.engine.retrieve import gather_evidence
from app.engine.translate import localize
from app.models.claim import Claim
from app.models.report import ClaimVerdict, JobStatus, TruthReport
from app.models.verdict import Rating, Verdict
from app.store.repository import ReportRepository, safe_cache_call as _cache_call


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


async def run_pipeline(
    job_id: str,
    raw_text: str,
    repo: ReportRepository,
    derived_text: str | None = None,
) -> None:
    """`derived_text` is set when a machine produced the text (ASR/OCR), so the
    report can show the user what was actually read."""
    # Report reads/writes are synchronous SQLite; keep them off the event loop
    # so a contended write stalls this job only, not the whole server.
    report = await asyncio.to_thread(repo.get, job_id)
    if report is None:  # defensive: job row should already exist
        return

    try:
        report.status = JobStatus.PROCESSING
        report.source_text = derived_text
        await asyncio.to_thread(repo.save, report)

        norm = await normalize(raw_text)
        report.input_language = norm.detected_language

        claims = await extract_claims(norm.english_text)
        checkworthy = [c for c in claims if c.checkworthy]

        # Each claim costs a paid retrieval + adjudication and they all run
        # concurrently, so one submission's spend is bounded here. Never drop
        # claims silently — the report says what was left unchecked.
        dropped = 0
        if len(checkworthy) > settings.max_claims_per_report:
            dropped = len(checkworthy) - settings.max_claims_per_report
            checkworthy = checkworthy[: settings.max_claims_per_report]
            print(f"[pipeline] {dropped} claim(s) over the per-report cap were not checked")

        results = await asyncio.gather(
            *(_process_claim(c, repo) for c in checkworthy),
            return_exceptions=True,
        )
        verdicts = [r for r in results if isinstance(r, ClaimVerdict)]

        report.claim_verdicts = verdicts
        report.overall_rating = overall_rating(verdicts)
        report.summary = build_summary(verdicts, report.overall_rating)
        if dropped:
            report.summary += (
                f" Note: this message contained more checkable claims than this "
                f"service checks at once, so {dropped} were not verified."
            )

        # Answer in the language it arrived in — last, so the summary above
        # (including the dropped-claims note) is part of what gets translated.
        # Guarded for the same reason cache calls are: the English report is
        # complete and already paid for, and a translator being down must
        # cost the reader a translation, never the verdict.
        try:
            report.localized = await localize(report, getattr(repo, "translations", None))
        except Exception as exc:  # noqa: BLE001 — see above
            print(f"[translate] localization skipped: {type(exc).__name__}: {exc}")

        report.status = JobStatus.COMPLETE
    except Exception as exc:  # noqa: BLE001 — surface any failure into the report
        report.status = JobStatus.FAILED
        report.error = f"{type(exc).__name__}: {exc}"
    finally:
        report.completed_at = datetime.now(timezone.utc)
        await asyncio.to_thread(repo.save, report)
