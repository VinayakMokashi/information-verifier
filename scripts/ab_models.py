r"""A/B two Claude models on the same real input. COSTS MONEY.

    .venv\Scripts\python.exe scripts\ab_models.py <reel url | "claim text">
    .venv\Scripts\python.exe scripts\ab_models.py <input> claude-sonnet-5 claude-opus-5

A link is resolved (free) and transcribed ONCE — through the transcript cache,
so a second A/B on the same reel pays for no ASR at all — and then every model
answers the IDENTICAL text through the real engine (both passes, real search).
Each model's bill is measured separately from the API's own usage fields.

This bypasses the answer cache on purpose (it calls the engine directly): an
A/B that served one model from a cached answer would compare nothing.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.models.answer import Answer, AnswerSection, JobStatus  # noqa: E402
from app.providers.usage import UsageMeter  # noqa: E402
from scripts.render import force_utf8_stdout, render_answer  # noqa: E402

DEFAULT_MODELS = ["claude-sonnet-5", "claude-opus-5"]


async def text_for(target: str) -> tuple[str, bool, float]:
    """-> (text to check, came_from_a_link, ASR dollars spent getting it)."""
    from app.api import routes as R
    from app.providers.links import allowed_link_host, resolve_link
    from app.store.db import init_db
    from app.store.repository import AnswerRepository

    if allowed_link_host(target) is None:
        return target, False, 0.0
    init_db()
    repo = AnswerRepository()
    info = await asyncio.to_thread(resolve_link, target)
    print(f">> Resolved: {info.platform} / {info.uploader} / {info.video_id}")
    key = R.transcript_key(info)
    cached = repo.transcripts.get(key) if key else None
    if cached:
        print(">> Transcript cache HIT — no download, no ASR.")
        return cached, True, 0.0
    meter = UsageMeter()
    with meter.activate():
        text = await R.gather_link_text(info)
    if key:
        repo.transcripts.put(key, text)
    bill = meter.snapshot()
    print(f">> Transcribed: {bill.asr_seconds:.1f}s of audio, ${bill.estimated_usd:.4f}")
    return text, True, bill.estimated_usd


async def run_one(model: str, text: str, from_link: bool) -> dict:
    from datetime import datetime, timezone

    from app.engine import chat

    settings.chat_model = model
    meter = UsageMeter()
    started = time.monotonic()
    error = None
    with meter.activate():
        try:
            result = await chat.answer(text, heard=text if from_link else None)
        except Exception as exc:  # noqa: BLE001 — an A/B reports failures, it does not stop
            result, error = None, f"{type(exc).__name__}: {exc}"
    elapsed = time.monotonic() - started
    bill = meter.snapshot()
    answer = Answer(
        job_id=f"ab-{model}", created_at=datetime.now(timezone.utc),
        status=JobStatus.COMPLETE if result else JobStatus.FAILED,
        input_text=text[:300], error=error,
        sections=result.sections if result else [AnswerSection(tier="none", markdown="")],
        sources=result.sources if result else [],
        confidence=result.confidence if result else None,
        tier=result.tier if result else "none",
        truncated=result.truncated if result else False,
        usage=bill,
    )
    return {"model": model, "answer": answer, "usd": bill.estimated_usd,
            "searches": bill.web_searches, "seconds": elapsed,
            "passes": len(answer.sections)}


async def main() -> None:
    force_utf8_stdout()
    if len(sys.argv) < 2:
        print(__doc__)
        return
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY in .env. Aborting (no cost).")
        return
    target, models = sys.argv[1], sys.argv[2:] or DEFAULT_MODELS
    print(f">> PAID A/B: {', '.join(models)}")
    text, from_link, asr_usd = await text_for(target)
    print(f">> Checking {len(text)} chars:\n   {text[:300]!r}\n")

    rows = []
    for model in models:
        print(f"\n{'#' * 74}\n#  {model}\n{'#' * 74}")
        row = await run_one(model, text, from_link)
        print(render_answer(row["answer"]))
        rows.append(row)

    print("\n" + "=" * 74)
    print(f"{'model':18} {'cost':>9} {'searches':>9} {'passes':>7} {'secs':>6} "
          f"{'tier':>8} {'conf':>5} {'sources':>8}")
    for r in rows:
        a = r["answer"]
        print(f"{r['model']:18} ${r['usd']:>8.4f} {r['searches']:>9} {r['passes']:>7} "
              f"{r['seconds']:>6.1f} {a.tier:>8} {str(a.confidence):>5} "
              f"{len(a.sources):>8}")
    if asr_usd:
        print(f"(+ ${asr_usd:.4f} of ASR, paid once for both)")


if __name__ == "__main__":
    asyncio.run(main())
