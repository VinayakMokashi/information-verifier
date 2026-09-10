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
import asyncio
import hashlib
import json
import threading
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

from pydantic import ValidationError

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


# Zero-width and BOM characters: invisible, and a full cache miss if left in.
# Indic keyboards emit ZWJ/ZWNJ routinely and a copy-paste can carry a BOM.
_INVISIBLE = {"​", "‌", "‍", "﻿", "­", "⁠"}


def _norm_key(text: str) -> str:
    return " ".join(text.lower().split())


async def safe_cache_call(fn, *args):
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


class CacheCandidate(NamedTuple):
    """A near-neighbour from the vector index — must be confirmed, not served."""

    text: str          # the cached claim's normalized text
    verdict: Verdict
    distance: float    # cosine distance to the queried claim


# A transient hiccup on the first lazy model load (the gated HF download) must
# not cost the semantic tier for the life of the process, but a genuinely
# missing model shouldn't be retried on every claim forever either.
_MAX_EMBED_FAILURES = 3
# Short enough that separate user requests (seconds apart) still accumulate
# toward the budget, long enough that one report's concurrent fan-out — which
# fails within milliseconds of itself — counts once.
_FAILURE_WINDOW_S = 1.0
_RETRY_AFTER_S = 300.0      # give a paused tier another chance rather than
                            # staying off until the process restarts


class ClaimCache:
    def __init__(self, embedder=None) -> None:
        self._embedder = embedder
        self._embed_failures = 0
        self._last_failure_at = -_FAILURE_WINDOW_S
        self._fail_lock = threading.Lock()

    # -- embedding helpers ---------------------------------------------------
    def _semantic_on(self) -> bool:
        if not vec_enabled():
            return False
        if self._embed_failures < _MAX_EMBED_FAILURES:
            return True
        # Paused, not dead: an outage (or a slow first download) should not
        # cost per-rumour pricing for the life of the server.
        if time.monotonic() - self._last_failure_at >= _RETRY_AFTER_S:
            self._embed_failures = 0
            return True
        return False

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
            self._note_failure()
            note = (
                f"semantic tier paused for {_RETRY_AFTER_S:.0f}s"
                if self._embed_failures >= _MAX_EMBED_FAILURES
                else f"attempt {self._embed_failures}/{_MAX_EMBED_FAILURES}"
            )
            print(f"[cache] embedding failed ({note}): {type(exc).__name__}: {exc}")
            return None

    def _note_failure(self) -> None:
        """Count failure EVENTS, not calls.

        A report fans out up to max_claims_per_report claims concurrently, so
        one cold-start hiccup produces N simultaneous exceptions. Counting
        each would burn the whole budget on a single event — measured: one
        8-claim report exhausted a 3-failure budget during a 1s model load.
        """
        now = time.monotonic()
        with self._fail_lock:
            # >=, not >: time.monotonic() has ~15 ms resolution on Windows, so
            # two failures in the same tick would otherwise never separate.
            if now - self._last_failure_at >= _FAILURE_WINDOW_S:
                self._embed_failures += 1
            self._last_failure_at = now

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
            if not vec_enabled():
                return
            # Keyed by claim_cache.rowid (preserved by the upsert above), so a
            # KNN result joins straight back to its verdict.
            rowid = conn.execute(
                "SELECT rowid FROM claim_cache WHERE norm_key = ?", (key,)
            ).fetchone()["rowid"]
            # Always clear first: an alias written over a row that used to be
            # an anchor must not inherit the old vector, or "unindexed" would
            # be true only for rows that happened to be new.
            conn.execute("DELETE FROM claim_vecs WHERE rowid = ?", (rowid,))
            if vec is not None:
                conn.execute(
                    "INSERT INTO claim_vecs (rowid, embedding) VALUES (?, ?)",
                    (rowid, serialize_float32(vec)),
                )


def _content_key(fields: tuple[str, ...]) -> str:
    """Address a translation by the exact English text it was made from.

    JSON rather than a concatenation because ("ab", "c") and ("a", "bc")
    must not hash into one another's translation — a cache that can serve
    the wrong claim's answer is the worst failure this system has.
    """
    blob = json.dumps(fields, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class TranslationCache:
    """Caches a translation, keyed by the exact English text it came from.

    Without this the claim cache's economics invert. One viral Hindi forward
    reaching a thousand readers is a single $0.05 check — and then a
    thousand separate $0.01 translations of the same cached verdict, i.e.
    back to per-USER pricing, which is precisely what the claim cache
    exists to avoid.

    Content-addressed, so nothing ever needs invalidating: re-adjudicate a
    claim and its prose changes, so the key changes and the stale
    translation is simply never looked up again.
    """

    def get(self, language: str, source: tuple[str, ...]) -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT payload FROM translation_cache "
                "WHERE source_hash = ? AND language = ?",
                (_content_key(source), language),
            ).fetchone()
        return row["payload"] if row else None

    def put(self, language: str, source: tuple[str, ...], payload: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO translation_cache "
                "(source_hash, language, payload, created_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(source_hash, language) DO UPDATE "
                "SET payload = excluded.payload, created_at = excluded.created_at",
                (_content_key(source), language, payload, _now_iso()),
            )


def _normalize_input(text: str) -> str:
    """Fold a submitted message to a cache key.

    Harder than the claim cache's lowercase-and-collapse, because that keyed
    on ONE atomic claim while this keys on a whole forward — and forwards
    arrive with invisible junk: zero-width joiners from Indic keyboards, a
    BOM from a copy-paste, NBSPs from a web page, decomposed vs composed
    Devanagari. All of those would be a full miss and a full re-bill.

    Deliberately nothing lossier than that. Merging two genuinely different
    messages onto one key is the worst failure this cache can have, so
    punctuation, digits and emoji all still count as content.
    """
    folded = unicodedata.normalize("NFKC", text)
    folded = "".join(ch for ch in folded if ch not in _INVISIBLE)
    return " ".join(folded.split()).casefold()


class AnswerCache:
    """Exact-match cache of whole answers, keyed by everything that decides one.

    The old semantic tier is deliberately gone: its 0.20 distance threshold
    was calibrated on atomic English claims, and a whole multilingual forward
    is a different distribution entirely. Exact match hits far less often —
    an extra emoji is a miss — but it never serves a stranger's answer for
    your message, which is the failure that actually matters.

    Because it is exact-match only, a TTL is MANDATORY rather than optional.
    A per-claim FALSE verdict aged well; "no fact-checker has covered this"
    is wrong the day one does.
    """

    def get(self, key: str) -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT tier, payload, created_at FROM answer_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        hours = (settings.answer_cache_ttl_trusted_h
                 if row["tier"] == "trusted" else settings.answer_cache_ttl_web_h)
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])
        except ValueError:
            return None                      # unparseable stamp: treat as stale
        if age > timedelta(hours=hours):
            return None
        return row["payload"]

    def put(self, key: str, tier: str, payload: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO answer_cache (key, tier, payload, created_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(key) DO UPDATE SET "
                "tier = excluded.tier, payload = excluded.payload, "
                "created_at = excluded.created_at",
                (key, tier, payload, _now_iso()),
            )

    def prune(self) -> int:
        """Drop entries past the longest TTL. Nothing was ever pruned before
        (backlog item 13); an answer cache of strangers' messages should not
        grow forever."""
        cutoff = (datetime.now(timezone.utc)
                  - timedelta(hours=max(settings.answer_cache_ttl_trusted_h,
                                        settings.answer_cache_ttl_web_h)))
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM answer_cache WHERE created_at < ?",
                               (cutoff.isoformat(),))
            return cur.rowcount or 0


class AnswerRepository:
    """Job rows. The payload is opaque JSON, so the Answer model can evolve."""

    def __init__(self) -> None:
        self.cache = AnswerCache()

    def save(self, answer) -> None:
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO answers (job_id, status, payload, created_at) "
                "VALUES (?, ?, ?, ?)",
                (answer.job_id, answer.status.value, answer.model_dump_json(),
                 answer.created_at.isoformat()),
            )

    def get(self, job_id: str):
        from app.models.answer import Answer

        with get_conn() as conn:
            row = conn.execute(
                "SELECT payload FROM answers WHERE job_id = ?", (job_id,)
            ).fetchone()
        return Answer.model_validate_json(row["payload"]) if row else None

    def sweep_orphans(self) -> int:
        """Fail jobs left mid-flight by a restart.

        BackgroundTasks die with the process, so a QUEUED/PROCESSING row at
        startup is dead by definition — it would otherwise sit there forever
        while the page politely polled it.
        """
        from app.models.answer import Answer, JobStatus

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT payload FROM answers WHERE status IN ('QUEUED', 'PROCESSING')"
            ).fetchall()
        healed = 0
        for row in rows:
            try:
                answer = Answer.model_validate_json(row["payload"])
            except ValidationError:
                continue
            answer.status = JobStatus.FAILED
            answer.error = "The server restarted while this check was running."
            answer.completed_at = datetime.now(timezone.utc)
            self.save(answer)
            healed += 1
        return healed


class ReportRepository:
    def __init__(self) -> None:
        self.cache = ClaimCache()
        self.translations = TranslationCache()

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
