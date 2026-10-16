"""One check, end to end: cache -> engine -> persist. The old run_pipeline's job.

Everything that made the old orchestrator survivable is kept, because those
lessons were paid for: a failure becomes a FAILED row with readable words
rather than a job stuck at PROCESSING forever, the bill is attached even when
the check failed (failures cost money), and a cache fault degrades to doing
the real work instead of discarding an answer.
"""
import asyncio
import hashlib
import json
from datetime import datetime, timezone

from app.config import settings
from app.engine import chat
from app.engine.chat_prompts import PROMPT_FINGERPRINT
from app.models.answer import Answer, JobStatus
from app.providers.usage import UsageMeter
from app.store.repository import _normalize_input, safe_cache_call
from app.trusted_sources import SEARCH_DOMAINS


def cache_key(text: str, language: str | None = None) -> str:
    """Key an answer by everything that decides it, not just the text.

    Model, effort and the prompt all change the answer, and the whitelist
    changes what could be found — so editing any of them must miss rather
    than keep serving prose written under the old rules. Same discipline the
    translation cache's fingerprint earned. The reply LANGUAGE counts too:
    the same claim in Tamil and in English are different answers.
    """
    blob = json.dumps([
        PROMPT_FINGERPRINT,
        settings.chat_model,
        settings.chat_effort,
        sorted(SEARCH_DOMAINS),
        settings.web_tier_enabled,
        (chat._chosen_language(language) or "").casefold(),   # "Tamil" == "tamil"
        _normalize_input(text),
    ], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_NO_LONGER_CACHED = ("That answer is no longer available. Please send the "
                     "message again.")
_NOT_SAVED = ("This check finished but could not be saved. Please send the "
              "message again.")
_NOT_STARTED = "This check couldn't be started. Please send the message again."
_SAVE_RETRY_S = (1.0, 3.0)   # waits between the finishing save's three attempts


async def _save_finished(repo, answer) -> bool:
    """The save that makes a finished check visible, tried three times.

    REPRODUCED (docs/research/2026-10-15/audit-ops.md OPS-06): unguarded, one
    "database is locked" here — an owner's DB browser holding a lock past the
    30 s busy timeout, a full disk — lost the answer just paid for, skipped
    its ledger row, and never ended its stream. -> False if it never took.
    """
    for wait in (*_SAVE_RETRY_S, None):
        try:
            await asyncio.to_thread(repo.save, answer)
            return True
        except Exception as exc:  # noqa: BLE001 — retried, then reported
            print(f"[job] saving the finished check failed: {type(exc).__name__}: {exc}")
            if wait is None:
                return False
            await asyncio.sleep(wait)


async def run_check(job_id: str, text: str, repo, stream=None, *,
                    derived_text: str | None = None,
                    meter: UsageMeter | None = None,
                    kind: str = "text",
                    language: str | None = None,
                    mode: str = "full",
                    cache_only: bool = False,
                    on_finished=None) -> None:
    """Check `text`, stream it, store it. Never raises.

    `mode` is what the day's budget still buys (chat.answer). `cache_only`:
    the route served a repeat for free, with no slot and no reservation, on
    the strength of a cache hit — so a miss here (it expired in between)
    must FAIL rather than buy an unbudgeted check.

    `on_finished()` runs right BEFORE the finished answer is saved — so
    before anyone polling can see it (review R6: the person was released
    only after the ledger and the settling, and a client that saw COMPLETE
    and sent its next message was told it "already had a check running").
    It must be safe to call twice.
    """
    try:
        answer = await asyncio.to_thread(repo.get, job_id)
    except Exception as exc:  # noqa: BLE001 — "never raises"
        print(f"[job] could not read the job: {type(exc).__name__}: {exc}")
        answer = None
    if answer is None:
        # Nothing to check — but the stream must still END, or its reader
        # waits on heartbeats forever (OPS-06). The row, if any, is failed
        # later by the stale sweep (repository.sweep_stale).
        if stream is not None:
            await stream.publish("error", {"message": _NOT_STARTED})
        return

    def finished() -> None:
        if on_finished is not None:
            try:
                on_finished()
            except Exception as exc:  # noqa: BLE001 — never costs the answer
                print(f"[job] on_finished failed: {type(exc).__name__}: {exc}")

    meter = meter or UsageMeter()

    async def emit(kind: str, data: dict) -> None:
        if stream is not None:
            await stream.publish(kind, data)

    saved_early = False
    try:
        answer.status = JobStatus.PROCESSING
        # What the person SENT stays as the route stored it: for a reel, its
        # link — what a deletion request names (review S5-7: overwritten
        # with the gathered words, the check could not be found). A voice
        # note's row starts empty; then what was heard is all there is.
        if not answer.input_text:
            answer.input_text = text
        answer.source_text = derived_text
        await asyncio.to_thread(repo.save, answer)
        await emit("status", {"text": "Reading what you sent…"})

        key = cache_key(text, language)
        cached = await safe_cache_call(repo.cache.get, key)
        if cached:
            try:
                previous = Answer.model_validate_json(cached)
            except Exception as exc:  # noqa: BLE001 — a bad row costs one recheck
                print(f"[job] discarding a bad cached answer: {exc}")
            else:
                answer.sections = previous.sections
                answer.summary = previous.summary
                answer.sources = previous.sources
                answer.confidence = previous.confidence
                answer.tier = previous.tier
                answer.truncated = previous.truncated
                answer.cached = True
                answer.status = JobStatus.COMPLETE
                answer.completed_at = datetime.now(timezone.utc)
                answer.usage = meter.snapshot()      # honestly $0
                finished()
                if await _save_finished(repo, answer):
                    saved_early = True
                    for section in answer.sections:
                        await emit("text", {"text": section.markdown,
                                            "tier": section.tier})
                    for source in answer.sources:
                        await emit("source", source.model_dump())
                    if answer.summary:
                        await emit("summary", {"text": answer.summary})
                    await emit("done", {"cached": True})
                # else: the finally tries once more and tells the reader.
                return

        if cache_only:
            answer.status = JobStatus.FAILED
            answer.error = _NO_LONGER_CACHED
            return

        with meter.activate():
            result = await chat.answer(text, heard=derived_text, emit=emit,
                                       language=language, mode=mode)

        answer.sections = result.sections
        answer.summary = result.summary
        answer.sources = result.sources
        answer.confidence = result.confidence
        answer.tier = result.tier
        answer.truncated = result.truncated
        answer.status = JobStatus.COMPLETE

        # Never an answer the day's budget cut short: the same message after
        # midnight deserves the full check, not this one served for days.
        if result.sections and not result.degraded:
            answer.usage = meter.snapshot()
            await safe_cache_call(repo.cache.put, key, result.tier,
                                  answer.model_dump_json())
    except chat.CheckUnavailable as exc:
        # Its message is written for the reader by contract (see chat.py).
        print(f"[job] no answer produced: {exc}")
        answer.status = JobStatus.FAILED
        answer.error = str(exc)
    except chat.AnswerRefused as exc:
        # The category ("cyber", "bio", ...) is for the log, not the reader.
        print(f"[job] declined by the model: {exc}")
        answer.status = JobStatus.FAILED
        answer.error = ("This one can't be checked here. If it is a claim you "
                        "saw somewhere, try sending just the part you want "
                        "checked.")
    except Exception as exc:  # noqa: BLE001 — every failure reaches the reader
        print(f"[job] check failed: {type(exc).__name__}: {exc}")
        answer.status = JobStatus.FAILED
        answer.error = "Something went wrong checking this. Please try again."
    finally:
        # Failures cost money too — the bill is attached either way.
        answer.usage = meter.snapshot()
        if not saved_early:
            answer.completed_at = datetime.now(timezone.utc)
        finished()
        # Saved ONCE. A repeat from the cache had already saved its finished
        # row, and a second INSERT OR REPLACE brought back a row deleted in
        # between (review S5-8: forget.py runs beside the app).
        saved = saved_early or await _save_finished(repo, answer)
        # The spend ledger outlives the answer (which is deleted after
        # answer_retention_days) — and is written even when the answer could
        # not be: the money was spent either way. A ledger failure must not
        # lose the answer.
        await safe_cache_call(repo.ledger.record, answer, kind)
        # The stream ALWAYS ends, with the truth: an unsaved answer is not
        # "done" — the page would re-read it from a row still PROCESSING.
        if not saved:
            await emit("error", {"message": _NOT_SAVED})
        elif saved_early:
            pass                     # the cache branch has already said "done"
        elif answer.status is JobStatus.FAILED:
            await emit("error", {"message": answer.error})
        else:
            await emit("done", {"cached": answer.cached})
