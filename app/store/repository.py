"""Persistence for reports and the claim cache.

The claim cache is what turns a per-user cost into a per-rumour cost: one
viral WhatsApp forward reaches millions, and each hit would otherwise
re-run the full pipeline.

Phase 1 uses an EXACT normalized-text match (lowercased, whitespace-
collapsed). That catches literal re-forwards but not paraphrases. The
Phase 2 upgrade is semantic: embed each claim and do a pgvector similarity
lookup so near-duplicates also hit. (Note: Anthropic has no embeddings
endpoint — that step needs an embedding model such as Voyage.)
"""
from datetime import datetime, timezone

from app.models.report import TruthReport
from app.models.verdict import Verdict
from app.store.db import get_conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_key(text: str) -> str:
    return " ".join(text.lower().split())


class ClaimCache:
    def get(self, claim_text: str) -> Verdict | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT verdict FROM claim_cache WHERE norm_key = ?",
                (_norm_key(claim_text),),
            ).fetchone()
        return Verdict.model_validate_json(row["verdict"]) if row else None

    def put(self, claim_text: str, verdict: Verdict) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO claim_cache (norm_key, verdict, created_at) "
                "VALUES (?, ?, ?)",
                (_norm_key(claim_text), verdict.model_dump_json(), _now_iso()),
            )


class ReportRepository:
    def __init__(self) -> None:
        self.cache = ClaimCache()

    def save(self, report: TruthReport) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO reports (job_id, status, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (
                    report.job_id,
                    report.status.value,
                    report.model_dump_json(),
                    report.created_at.isoformat(),
                ),
            )

    def get(self, job_id: str) -> TruthReport | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT payload FROM reports WHERE job_id = ?", (job_id,)
            ).fetchone()
        return TruthReport.model_validate_json(row["payload"]) if row else None
