"""Persistence for reports and the claim cache.

The claim cache is what turns a per-user cost into a per-rumour cost: one
viral WhatsApp forward reaches millions, and each hit would otherwise
re-run the full pipeline.

Two cache tiers:
  1. EXACT normalized-text match (lowercased, whitespace-collapsed) — free,
     catches literal re-forwards. `get()`.
  2. SEMANTIC nomination — the claim is embedded locally (EmbeddingGemma,
     $0) and looked up in a sqlite-vec KNN index. `nearest()` returns a
     CANDIDATE, never a verdict: calibration showed one-token-different
     claims embed closer than real paraphrases, so no distance threshold is
     safe to serve from directly. The pipeline confirms every candidate
     with a cheap Haiku equivalence check before using it, then stores the
     confirmed phrasing as an UNINDEXED alias (see `put`), so every future
     nomination is still measured against a claim that was really checked.

The semantic tier degrades to a no-op (with one warning) if sqlite-vec or
the embedding model is unavailable — the engine never breaks over it.
"""
from datetime import datetime, timezone
from typing import NamedTuple

from app.config import settings
from app.models.report import TruthReport
from app.models.verdict import Verdict
from app.store.db import get_conn, vec_enabled

try:
    from sqlite_vec import serialize_float32
except ImportError:  # pragma: no cover — VEC_AVAILABLE is False in this case
    serialize_float32 = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _norm_key(text: str) -> str:
    return " ".join(text.lower().split())


class CacheCandidate(NamedTuple):
    """A near-neighbour from the vector index — must be confirmed, not served."""

    text: str          # the cached claim's normalized text
    verdict: Verdict
    distance: float    # cosine distance to the queried claim


# A transient hiccup on the first lazy model load (the gated HF download) must
# not cost the semantic tier for the life of the process, but a genuinely
# missing model shouldn't be retried on every claim forever either.
_MAX_EMBED_FAILURES = 3


class ClaimCache:
    def __init__(self, embedder=None) -> None:
        self._embedder = embedder
        self._embed_failures = 0

    # -- embedding helpers ---------------------------------------------------
    def _semantic_on(self) -> bool:
        return vec_enabled() and self._embed_failures < _MAX_EMBED_FAILURES

    def _embed(self, text: str) -> list[float] | None:
        if not self._semantic_on():
            return None
        try:
            if self._embedder is None:
                from app.providers.embeddings import get_embedder

                self._embedder = get_embedder()
            vec = self._embedder.embed(text)
            self._embed_failures = 0  # a success clears earlier transient errors
            return vec
        except Exception as exc:  # noqa: BLE001 — cache must never sink a claim
            self._embed_failures += 1
            note = (
                "disabling semantic tier until restart"
                if self._embed_failures >= _MAX_EMBED_FAILURES
                else f"attempt {self._embed_failures}/{_MAX_EMBED_FAILURES}"
            )
            print(f"[cache] embedding failed ({note}): {type(exc).__name__}: {exc}")
            return None

    # -- public API ----------------------------------------------------------
    def get(self, claim_text: str) -> Verdict | None:
        """Exact-match tier only: this exact wording was checked or confirmed."""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT verdict FROM claim_cache WHERE norm_key = ?",
                (_norm_key(claim_text),),
            ).fetchone()
        return Verdict.model_validate_json(row["verdict"]) if row else None

    def nearest(self, claim_text: str) -> CacheCandidate | None:
        """Nominate the closest cached claim within the candidate distance."""
        vec = self._embed(claim_text)
        if vec is None:
            return None
        with get_conn() as conn:
            hit = conn.execute(
                "SELECT c.norm_key, c.verdict, v.distance "
                "FROM (SELECT rowid, distance FROM claim_vecs "
                "      WHERE embedding MATCH ? AND k = 1) v "
                "JOIN claim_cache c ON c.rowid = v.rowid",
                (serialize_float32(vec),),
            ).fetchone()
        if hit and hit["distance"] <= settings.semantic_candidate_distance:
            return CacheCandidate(
                text=hit["norm_key"],
                verdict=Verdict.model_validate_json(hit["verdict"]),
                distance=hit["distance"],
            )
        return None

    def put(self, claim_text: str, verdict: Verdict, index: bool = True) -> None:
        """Store a verdict. `index=False` stores it WITHOUT a vector.

        Aliases learned from a confirmed near-match are stored unindexed on
        purpose: if an alias could itself be nominated, a chain of hops would
        drift arbitrarily far from the claim that was actually adjudicated,
        with each hop only ever confirmed against the previous one. Only
        genuinely adjudicated claims become nomination anchors.
        """
        key = _norm_key(claim_text)
        vec = self._embed(claim_text) if index else None
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO claim_cache (norm_key, verdict, created_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(norm_key) DO UPDATE "
                "SET verdict = excluded.verdict, created_at = excluded.created_at",
                (key, verdict.model_dump_json(), _now_iso()),
            )
            if vec is not None:
                # Keyed by claim_cache.rowid (preserved by the upsert above),
                # so the KNN result joins straight back to its verdict.
                rowid = conn.execute(
                    "SELECT rowid FROM claim_cache WHERE norm_key = ?", (key,)
                ).fetchone()["rowid"]
                conn.execute("DELETE FROM claim_vecs WHERE rowid = ?", (rowid,))
                conn.execute(
                    "INSERT INTO claim_vecs (rowid, embedding) VALUES (?, ?)",
                    (rowid, serialize_float32(vec)),
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
