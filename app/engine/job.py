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


def cache_key(text: str) -> str:
    """Key an answer by everything that decides it, not just the text.

    Model, effort and the prompt all change the answer, and the whitelist
    changes what could be found — so editing any of them must miss rather
    than keep serving prose written under the old rules. Same discipline the
    translation cache's fingerprint earned.
    """
    blob = json.dumps([
        PROMPT_FINGERPRINT,
        settings.chat_model,
        settings.chat_effort,
        sorted(SEARCH_DOMAINS),
        settings.web_tier_enabled,
        _normalize_input(text),
    ], ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


async def run_check(job_id: str, text: str, repo, stream=None, *,
                    derived_text: str | None = None,
                    meter: UsageMeter | None = None,
                    kind: str = "text") -> None:
    """Check `text`, stream it, store it. Never raises."""
    answer = await asyncio.to_thread(repo.get, job_id)
    if answer is None:                      # defensive: the row is made first
        return

    meter = meter or UsageMeter()

    async def emit(kind: str, data: dict) -> None:
        if stream is not None:
            await stream.publish(kind, data)

    try:
        answer.status = JobStatus.PROCESSING
        answer.input_text = text
        answer.source_text = derived_text
        await asyncio.to_thread(repo.save, answer)
        await emit("status", {"text": "Reading what you sent…"})

        key = cache_key(text)
        cached = await safe_cache_call(repo.cache.get, key)
        if cached:
            try:
                previous = Answer.model_validate_json(cached)
            except Exception as exc:  # noqa: BLE001 — a bad row costs one recheck
                print(f"[job] discarding a bad cached answer: {exc}")
            else:
                answer.sections = previous.sections
                answer.sources = previous.sources
                answer.confidence = previous.confidence
                answer.tier = previous.tier
                answer.truncated = previous.truncated
                answer.cached = True
                answer.status = JobStatus.COMPLETE
                answer.completed_at = datetime.now(timezone.utc)
                answer.usage = meter.snapshot()      # honestly $0
                await asyncio.to_thread(repo.save, answer)
                for section in answer.sections:
                    await emit("text", {"text": section.markdown,
                                        "tier": section.tier})
                for source in answer.sources:
                    await emit("source", source.model_dump())
                await emit("done", {"cached": True})
                return

        with meter.activate():
            result = await chat.answer(text, heard=derived_text, emit=emit)

        answer.sections = result.sections
        answer.sources = result.sources
        answer.confidence = result.confidence
        answer.tier = result.tier
        answer.truncated = result.truncated
        answer.status = JobStatus.COMPLETE

        if result.sections:
            answer.usage = meter.snapshot()
            await safe_cache_call(repo.cache.put, key, result.tier,
                                  answer.model_dump_json())
    except chat.CheckUnavailable as exc:
        # Its message is written for the reader by contract (see chat.py).
        print(f"[job] no answer produced: {exc}")
        answer.status = JobStatus.FAILED
        answer.error = str(exc)
    except chat.AnswerRefused as exc:
        answer.status = JobStatus.FAILED
        answer.error = ("This one can't be checked here — it was declined for "
                        f"safety reasons ({exc}).")
    except Exception as exc:  # noqa: BLE001 — every failure reaches the reader
        print(f"[job] check failed: {type(exc).__name__}: {exc}")
        answer.status = JobStatus.FAILED
        answer.error = "Something went wrong checking this. Please try again."
    finally:
        # Failures cost money too — the bill is attached either way.
        answer.usage = meter.snapshot()
        answer.completed_at = datetime.now(timezone.utc)
        await asyncio.to_thread(repo.save, answer)
        # The spend ledger outlives the answer (which is deleted after
        # answer_retention_days). A ledger failure must not lose the answer.
        await safe_cache_call(repo.ledger.record, answer, kind)
        if answer.status is JobStatus.FAILED:
            await emit("error", {"message": answer.error})
        else:
            await emit("done", {"cached": answer.cached})
