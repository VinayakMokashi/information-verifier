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


def operator_day(moment: datetime | None = None) -> str:
    """The calendar day as the person paying the bill counts it (IST default).

    ONE definition, shared by the daily cap and the spending dashboard — so
    "2 checks today" and "today's spend" can never disagree about when today
    began.
    """
    moment = moment or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    offset = timedelta(minutes=settings.day_boundary_utc_offset_min)
    return (moment.astimezone(timezone.utc) + offset).date().isoformat()


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


class TranscriptCache:
    """What a public post said, by (platform, video id). Saves ASR, not answers.

    The audio of a posted video does not change, so entries keep a while —
    but the caption can be edited, so they do expire. An empty text is never
    stored: a transcription that heard nothing must be retried next time, not
    remembered as the post's content.
    """

    def get(self, key: str) -> str | None:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT text, created_at FROM transcript_cache WHERE key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        try:
            age = datetime.now(timezone.utc) - datetime.fromisoformat(row["created_at"])
        except ValueError:
            return None
        if age > timedelta(days=settings.transcript_cache_ttl_days):
            return None
        return row["text"]

    def put(self, key: str, text: str) -> None:
        if not text or not text.strip():
            return
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO transcript_cache (key, text, created_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET text = excluded.text, "
                "created_at = excluded.created_at",
                (key, text, _now_iso()),
            )

    def prune(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.transcript_cache_ttl_days)
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM transcript_cache WHERE created_at < ?",
                               (cutoff.isoformat(),))
            return cur.rowcount or 0


def _provable_kind(answer) -> str:
    """What kind of check a stored answer was, as far as the row can PROVE.

    A live check records its kind as it finishes; this is for rows without
    one. The engine overwrites input_text with the text it gathered, so the
    old guess — "starts with https://" — never fired for a FINISHED link
    check, and every link and screenshot check came out as "media" (found by
    review). What the row does show: a job that failed before any text
    existed keeps what it was created with (a link's URL; a voice note's
    empty string), and a text check has no machine-read text. A finished
    link, screenshot or voice note looks the same — so it is "unknown".
    """
    if answer.source_text:
        return "unknown"
    if not answer.input_text:
        return "media"
    if answer.input_text.startswith("https://") and not any(
            c.isspace() for c in answer.input_text):
        return "link"
    return "text"


class SpendLedger:
    """What every finished check cost — and nothing the person sent.

    Answers hold messages and are deleted after `answer_retention_days`; this
    is what keeps the spending history once they are gone. Recording is
    idempotent (one row per job), and a failed write is the caller's to
    swallow: losing a ledger row must never lose the answer it describes.
    """

    def record(self, answer, kind: str) -> None:
        usage = answer.usage
        if usage is None:
            return
        from app.providers.usage import split_of

        finished = answer.completed_at or datetime.now(timezone.utc)
        models = usage.models or {}
        llm_usd, search_usd, asr_usd = split_of(usage)
        with get_conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO spend_ledger (job_id, day, finished_at, "
                "kind, status, tier, cached, usd, llm_usd, search_usd, asr_usd, "
                "input_tokens, output_tokens, cache_write_tokens, "
                "cache_read_tokens, web_searches, asr_seconds, models) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (answer.job_id, operator_day(finished), finished.isoformat(),
                 kind, answer.status.value, answer.tier, int(answer.cached),
                 usage.estimated_usd, llm_usd, search_usd, asr_usd,
                 sum(m.input_tokens for m in models.values()),
                 sum(m.output_tokens for m in models.values()),
                 sum(m.cache_write_tokens for m in models.values()),
                 sum(m.cache_read_tokens for m in models.values()),
                 usage.web_searches, usage.asr_seconds, ",".join(sorted(models))),
            )

    def backfill_from_answers(self) -> int:
        """Ledger rows for finished answers that predate the ledger.

        So the checks already run — including the first paid ones — appear on
        the dashboard the first time it opens, not only checks run after it
        existed. Their kind is inferred (a stored answer does not record it),
        and only as far as the row can prove it — see _provable_kind.
        """
        from app.models.answer import Answer

        with get_conn() as conn:
            rows = conn.execute(
                "SELECT a.payload FROM answers a LEFT JOIN spend_ledger s "
                "ON s.job_id = a.job_id WHERE s.job_id IS NULL "
                "AND a.status IN ('COMPLETE', 'FAILED')"
            ).fetchall()
        added = 0
        for row in rows:
            try:
                answer = Answer.model_validate_json(row["payload"])
            except ValidationError:
                continue
            if answer.usage is None:
                continue
            self.record(answer, _provable_kind(answer))
            added += 1
        return added

    # -- the dashboard's queries ---------------------------------------------

    # Operator experiments (A/B tests, probes) are real money — they count
    # toward every dollar total — but they are not anyone's check, so the
    # check counts and the per-check average leave them out.
    EXPERIMENTS = ("ab-test", "probe")

    def totals(self, since_day: str | None = None) -> dict:
        where, args = ("WHERE day >= ?", (since_day,)) if since_day else ("", ())
        exp = "kind IN ('ab-test', 'probe')"
        with get_conn() as conn:
            row = conn.execute(
                f"SELECT COALESCE(SUM(NOT {exp}), 0) AS checks, "
                f"COALESCE(SUM({exp}), 0) AS experiments, "
                f"COALESCE(SUM(CASE WHEN {exp} THEN 0 ELSE usd END), 0) AS check_usd, "
                "COALESCE(SUM(usd), 0) AS usd, "
                "COALESCE(SUM(llm_usd), 0) AS llm_usd, "
                "COALESCE(SUM(search_usd), 0) AS search_usd, "
                "COALESCE(SUM(asr_usd), 0) AS asr_usd, "
                f"COALESCE(SUM(cached AND NOT {exp}), 0) AS cached, "
                f"COALESCE(SUM(status = 'FAILED' AND NOT {exp}), 0) AS failed, "
                "COALESCE(SUM(web_searches), 0) AS searches, "
                "COALESCE(SUM(asr_seconds), 0) AS asr_seconds "
                f"FROM spend_ledger {where}", args,
            ).fetchone()
        return dict(row)

    def by_day(self, since_day: str) -> list[dict]:
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT day, SUM(kind NOT IN ('ab-test', 'probe')) AS checks, "
                "SUM(usd) AS usd, "
                "SUM(llm_usd) AS llm_usd, SUM(search_usd) AS search_usd, "
                "SUM(asr_usd) AS asr_usd, SUM(cached) AS cached "
                "FROM spend_ledger WHERE day >= ? GROUP BY day ORDER BY day",
                (since_day,),
            ).fetchall()
        return [dict(r) for r in rows]

    def recent(self, limit: int) -> list[dict]:
        """The latest rows, for the dashboard — WITHOUT job ids. A job id
        opens /reports/{id}, the full message, to anyone holding it; the
        dashboard never needed one (found by review)."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT finished_at, kind, status, tier, cached, usd, "
                "web_searches, asr_seconds, models FROM spend_ledger "
                "ORDER BY finished_at DESC LIMIT ?", (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


class DailyQuota:
    """The deployment-wide checks-per-day counter, in SQLite.

    `take` is ONE statement on purpose. A read-then-write pair would need a
    lock to be safe, and the earlier in-memory limiter measured exactly that
    window being exploited: 30 simultaneous uploads all saw an empty counter.
    The UPSERT's `WHERE used < cap` makes the database itself refuse the slot
    past the cap — measured on SQLite 3.45: rowcount is 0 once the cap is hit
    and `used` never exceeds it.
    """

    def used(self, day: str) -> int:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT used FROM daily_checks WHERE day = ?", (day,)
            ).fetchone()
        return row["used"] if row else 0

    def take(self, day: str, cap: int) -> bool:
        if cap <= 0:
            return False      # the INSERT branch would otherwise grant slot 1
        with get_conn() as conn:
            cur = conn.execute(
                "INSERT INTO daily_checks (day, used) VALUES (?, 1) "
                "ON CONFLICT(day) DO UPDATE SET used = used + 1 "
                "WHERE daily_checks.used < ?",
                (day, cap),
            )
            return cur.rowcount == 1

    def give_back(self, day: str) -> None:
        with get_conn() as conn:
            conn.execute(
                "UPDATE daily_checks SET used = used - 1 "
                "WHERE day = ? AND used > 0",
                (day,),
            )

    def history(self, days: int) -> list[tuple[str, int]]:
        """(day, used) for the most recent `days` days that saw any use."""
        with get_conn() as conn:
            rows = conn.execute(
                "SELECT day, used FROM daily_checks ORDER BY day DESC LIMIT ?",
                (days,),
            ).fetchall()
        return [(r["day"], r["used"]) for r in rows]


class AnswerRepository:
    """Job rows. The payload is opaque JSON, so the Answer model can evolve."""

    def __init__(self) -> None:
        self.cache = AnswerCache()
        self.transcripts = TranscriptCache()
        self.ledger = SpendLedger()

    def prune(self) -> int:
        """Delete finished answers older than answer_retention_days.

        Only finished ones: an in-flight job is never touched (and at startup
        sweep_orphans has already failed any the last process abandoned). The
        page treats a missing job as gone, so an old #job= link simply opens
        a fresh page. Costs survive in the spend ledger.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(
            days=settings.answer_retention_days)
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM answers WHERE created_at < ? "
                "AND status IN ('COMPLETE', 'FAILED')",
                (cutoff.isoformat(),))
            return cur.rowcount or 0

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


def housekeeping() -> dict[str, int]:
    """Everything that should not grow forever. Safe to run at any time.

    Runs at startup and every few hours while the server is up (see
    app/main.py): a long-running server must not depend on a restart to
    forget people's messages. Each step is independent — one failing must
    not stop the others — and the counts are logged by the caller.
    """
    repo = AnswerRepository()
    done: dict[str, int] = {}
    for name, step in (("ledger_backfilled", repo.ledger.backfill_from_answers),
                       ("answers_deleted", repo.prune),
                       ("answer_cache_expired", repo.cache.prune),
                       ("transcripts_expired", repo.transcripts.prune)):
        try:
            done[name] = step()
        except Exception as exc:  # noqa: BLE001 — see docstring
            print(f"[housekeeping] {name} failed: {type(exc).__name__}: {exc}")
            done[name] = -1
    return done
