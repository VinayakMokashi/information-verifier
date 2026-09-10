"""Persistence: job rows and the answer cache.

The cache is what keeps cost per-RUMOUR rather than per-USER: one viral
forward reaches many people and each re-check would otherwise be a full
re-bill.

Exact-match only. The old semantic tier does not survive the chat pivot —
its distance threshold was calibrated on atomic English claims, and nothing
produces atomic claims any more. See app/store/db.py for the tables and
AnswerCache below for why a TTL is now mandatory rather than optional.
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
from app.store.db import get_conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Zero-width and BOM characters: invisible, and a full cache miss if left in.
# Indic keyboards emit ZWJ/ZWNJ routinely and a copy-paste can carry a BOM.
_INVISIBLE = {"​", "‌", "‍", "﻿", "­", "⁠"}


async def safe_cache_call(fn, *args):
    """Run a cache operation off the event loop, never letting it sink a claim.

    The cache is an optimization: a locked DB or a corrupt row must degrade
    to doing the real work — never discard an answer we already paid for.
    Off the event loop because SQLite is synchronous and can wait on a lock.
    """
    try:
        return await asyncio.to_thread(fn, *args)
    except Exception as exc:  # noqa: BLE001 — see above
        print(f"[cache] {getattr(fn, '__name__', fn)} failed: {type(exc).__name__}: {exc}")
        return None


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
