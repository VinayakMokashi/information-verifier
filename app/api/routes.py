"""HTTP endpoints — surface-agnostic.

A verify request creates the job row, returns a job_id immediately, and runs
the pipeline as a BackgroundTask (the pipeline can take several seconds).
Clients poll GET /reports/{job_id}. A web PWA and a WhatsApp webhook consume
the exact same two-call contract.
"""
import asyncio
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile

from app.api.limits import refund, reserve
from app.api.schemas import JobAccepted, VerifyLinkRequest, VerifyTextRequest
from app.config import settings
from app.engine.pipeline import enforce_trust_on_report, run_pipeline
from app.models.report import JobStatus, TruthReport
from app.providers.asr import get_asr_provider
from app.providers.links import (
    SUPPORTED_LINKS_MSG, LinkError, LinkInfo, allowed_link_host,
    download_link_audio, resolve_link, subtitle_text,
)
from app.providers.media import MediaError, MediaTooLong, normalize_to_wav, split_wav
from app.providers.usage import UsageMeter
from app.providers.vision import ocr_image
from app.store.repository import ReportRepository

router = APIRouter(prefix="/api/v1")
_repo = ReportRepository()

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
# ffmpeg sniffs the real container, so the type gate is deliberately loose —
# browsers label voice notes inconsistently (audio/ogg, application/ogg, …).
_ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")
_ALLOWED_MEDIA_TYPES = {"application/ogg", "application/octet-stream"}


class _Spend:
    """Whether this request has already cost money."""

    __slots__ = ("started",)

    def __init__(self) -> None:
        self.started = False

    def begin(self) -> None:
        """Call immediately BEFORE the first paid call of the request."""
        self.started = True


@contextmanager
def _quota(request: Request):
    """Claim a check up front; hand it back only if we never spent anything.

    Reserving first is what makes the cap real — checking now and consuming
    after an upload has been read leaves a window where any number of
    concurrent requests pass the same empty counter.

    The `started` flag is load-bearing, not bookkeeping: /verify/image raises
    422 ("no text in this image") AFTER a paid Opus vision call, and refunding
    that rejection handed the slot back — a loop of blank images could burn
    budget all day with the daily counter reading zero. A refund is only
    honest when nothing was bought. (The media ASR spend that used to share
    this trap now runs behind the 202, where no refund path exists at all.)
    """
    reserve(request)
    spend = _Spend()
    try:
        yield spend
    except HTTPException:
        if not spend.started:
            refund(request)
        raise


async def _new_job() -> TruthReport:
    report = TruthReport(
        job_id=uuid.uuid4().hex,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
    )
    # SQLite calls are synchronous and can wait on a write lock; off the loop
    # so one contended write cannot stall every other request in the server.
    await asyncio.to_thread(_repo.save, report)
    return report


async def transcribe_wav(wav: bytes, duration: float) -> str:
    """16 kHz WAV -> transcript. The single ASR tail both audio paths use.

    It was copy-pasted between the media route and the link path; a change
    to chunking (overlap, a language hint, per-chunk retry) had to be made
    twice or the two surfaces would transcribe the same audio differently.

    Chunks are transcribed CONCURRENTLY and reassembled by index. Sarvam
    bills audio seconds, not requests, so this costs nothing — but a 300 s
    clip is ~11 chunks, and serially that is minutes of pure network wait
    that pushed jobs past the page's and the bot's poll windows (whose
    expiry used to invite a fully re-billed resubmission).
    """
    if duration <= settings.asr_chunk_seconds:
        chunks = [wav]
    else:
        chunks = await asyncio.to_thread(split_wav, wav, settings.asr_chunk_seconds)
    asr = get_asr_provider()
    transcripts = await asyncio.gather(*(asr.transcribe(c) for c in chunks))
    return " ".join(t.text.strip() for t in transcripts if t.text and t.text.strip())


async def _run_media_job(
    job_id: str, wav: bytes, duration: float, repo: ReportRepository, meter: UsageMeter
) -> None:
    """Background half of /verify/media: chunk -> Sarvam -> pipeline.

    A failure here becomes a FAILED report with a readable error — the page
    renders those — never a silent PROCESSING-forever. The transcript passes
    through as derived_text so the report shows what was heard (invariant 4):
    ASR can drop a claim's key term, and a silent mis-hear would mean
    checking a different claim than the one the person sent.
    """
    async def fail(message: str) -> None:
        report = await asyncio.to_thread(repo.get, job_id)
        if report is not None:
            report.status = JobStatus.FAILED
            report.error = message
            report.usage = meter.snapshot()
            report.completed_at = datetime.now(timezone.utc)
            await asyncio.to_thread(repo.save, report)

    try:
        text = await transcribe_wav(wav, duration)
    except MediaError as exc:
        await fail(f"Could not process this audio ({exc}).")
        return
    except (httpx.HTTPError, RuntimeError) as exc:
        # Sarvam down, key rejected, timeout — say so plainly.
        print(f"[media] transcription failed: {type(exc).__name__}: {exc}")
        await fail("The transcription service is unavailable right now. "
                   "Please try again in a minute.")
        return
    except Exception as exc:  # noqa: BLE001 — nothing may die silently here
        print(f"[media] unexpected failure: {type(exc).__name__}: {exc}")
        await fail("Something went wrong reading this audio. Please try again.")
        return

    if not text:
        await fail("No speech could be transcribed from this audio.")
        return
    await run_pipeline(job_id, text, repo, derived_text=text, meter=meter)


@router.post("/verify/text", response_model=JobAccepted, status_code=202)
async def verify_text(
    req: VerifyTextRequest, background: BackgroundTasks, request: Request
) -> JobAccepted:
    with _quota(request):
        if len(req.text) > settings.max_input_chars:
            raise HTTPException(
                413,
                f"That message is {len(req.text)} characters; the limit is "
                f"{settings.max_input_chars}. Send the part you want checked.",
            )
        report = await _new_job()
        background.add_task(run_pipeline, report.job_id, req.text, _repo)
        return JobAccepted(job_id=report.job_id, status=report.status)


@router.post("/verify/image", response_model=JobAccepted, status_code=202)
async def verify_image(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    with _quota(request) as spend:
        if file.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, f"Unsupported image type: {file.content_type}")
        image_bytes = await file.read()
        # OCR is quick; do it inline so extracted text is captured even if the
        # heavier verification pipeline is deferred to the background.
        spend.begin()          # everything past here has been paid for
        meter = UsageMeter()   # starts at the first paid call, so the report's
        with meter.activate():  # bill includes route-level OCR, not just the pipeline
            extracted = await ocr_image(image_bytes, file.content_type)
        if not extracted:
            raise HTTPException(422, "No text or visual claim could be read from the image.")

        report = await _new_job()
        background.add_task(run_pipeline, report.job_id, extracted, _repo, extracted,
                            meter=meter)
        return JobAccepted(job_id=report.job_id, status=report.status)


@router.post("/verify/media", response_model=JobAccepted, status_code=202)
async def verify_media(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    with _quota(request) as spend:
        ctype = (file.content_type or "").lower()
        if not (ctype.startswith(_ALLOWED_MEDIA_PREFIXES) or ctype in _ALLOWED_MEDIA_TYPES):
            raise HTTPException(415, f"Unsupported media type: {file.content_type}")
        if not settings.sarvam_api_key:
            raise HTTPException(503, "Audio checking is not configured (SARVAM_API_KEY missing).")

        data = await file.read()
        if len(data) > settings.max_media_bytes:
            raise HTTPException(413, "File too large. Please send a shorter clip.")

        meter = UsageMeter()
        try:
            # The duration cap is passed IN so it is enforced from the source
            # header, before a low-bitrate hour of audio is decoded into RAM.
            with meter.activate():   # normalize notes the billable ASR seconds
                wav, duration = await asyncio.to_thread(
                    normalize_to_wav, data, file.filename or "media",
                    settings.max_media_seconds,
                )
        except MediaTooLong as exc:
            raise HTTPException(413, f"Audio is {exc.seconds:.0f}s long; the limit is "
                                     f"{settings.max_media_seconds}s. Send a shorter clip.")
        except MediaError as exc:
            raise HTTPException(422, f"Could not read audio from this file ({exc}).")

        # Everything free and fast has now run: the type gate, the byte cap
        # and the ffmpeg decode with its duration cap all reject with clear
        # HTTP errors. The SLOW, PAID part — the Sarvam loop — runs in the
        # background: the audit showed a proxy cutting long inline requests
        # at ~100 s while the server kept spending, and a 202-then-poll
        # contract survives that. Same trade as /verify/link, same documented
        # cost: the quota slot stays consumed even if transcription fails.
        report = await _new_job()
        background.add_task(_run_media_job, report.job_id, wav, duration, _repo, meter)
        return JobAccepted(job_id=report.job_id, status=report.status)


# LinkError.kind -> HTTP status. Everything the user can fix is 422; only a
# platform we could not reach is the server's fault (502).
_LINK_HTTP = {"network": 502}

# The post's own caption text is a supplement, not the main source — cap its
# contribution so a stuffed caption cannot inflate the extract call. (The
# spoken text is bounded by max_media_seconds already.)
_MAX_CAPTION_CHARS = 2000


async def gather_link_text(info: LinkInfo) -> str:
    """Everything readable from the post: caption + (subtitles | audio->ASR).

    Cost order is the point (measured, §0a): the caption is already in hand
    ($0); a subtitle track replaces ASR outright ($0 — YouTube's '-orig'
    auto-captions ARE the speech recognition we would otherwise buy); and
    only when neither covers the speech is audio downloaded (byte/wall-capped
    stream), ffprobe'd against the duration cap, and sent to Sarvam.
    """
    caption = " ".join((info.caption or "").split())[:_MAX_CAPTION_CHARS]

    spoken: str | None = None
    if info.subtitle is not None:
        spoken = await asyncio.to_thread(subtitle_text, info.subtitle)
    if spoken is None and info.has_media:
        data, ext = await asyncio.to_thread(
            download_link_audio, info.url, settings.max_media_bytes
        )
        wav, duration = await asyncio.to_thread(
            normalize_to_wav, data, f"media{ext}", settings.max_media_seconds
        )
        spoken = await transcribe_wav(wav, duration)

    combined = "\n\n".join(t for t in (caption, spoken) if t and t.strip())
    if not combined.strip():
        raise LinkError("other", "No speech or text could be read from that post.")
    return combined


def _friendly_link_failure(exc: Exception) -> str:
    """A FAILED report's error is rendered to the user — no raw internals."""
    if isinstance(exc, MediaTooLong):
        return (f"That video's audio is {exc.seconds:.0f}s long; the limit is "
                f"{settings.max_media_seconds}s. Try a shorter clip.")
    if isinstance(exc, LinkError):
        return str(exc)
    if isinstance(exc, MediaError):
        return "The audio in that post could not be read."
    if isinstance(exc, (httpx.HTTPError, RuntimeError)):
        return ("The transcription service is unavailable right now. "
                "Please try again in a minute.")
    print(f"[link] unexpected failure: {type(exc).__name__}: {exc}")
    return "Something went wrong reading that link. Please try again."


async def _run_link_job(job_id: str, info: LinkInfo, repo: ReportRepository) -> None:
    """Background half: fetch the text, then run the normal pipeline.

    A failure here becomes a FAILED report with a readable error (the page
    renders those), never a silent PROCESSING-forever. run_pipeline guards
    itself; this guard covers the fetch/ASR work before it.
    """
    meter = UsageMeter()
    try:
        with meter.activate():   # the download's normalize notes ASR seconds
            text = await gather_link_text(info)
    except Exception as exc:  # noqa: BLE001 — every failure must reach the report
        report = await asyncio.to_thread(repo.get, job_id)
        if report is not None:
            report.status = JobStatus.FAILED
            report.error = _friendly_link_failure(exc)
            report.usage = meter.snapshot()   # a failed fetch still spent ASR
            report.completed_at = datetime.now(timezone.utc)
            await asyncio.to_thread(repo.save, report)
        return
    await run_pipeline(job_id, text, repo, derived_text=text, meter=meter)


@router.post("/verify/link", response_model=JobAccepted, status_code=202)
async def verify_link(
    req: VerifyLinkRequest, background: BackgroundTasks, request: Request
) -> JobAccepted:
    """Paste a public Instagram Reel / YouTube (Shorts) URL.

    Resolve runs INLINE because it is free and bad links are the common
    failure — a typo'd or private link deserves an immediate readable 4xx
    (refunded: nothing was spent). The download + ASR run in the BACKGROUND:
    fetching from a platform is slower and less bounded than reading an
    upload, and a 202-then-poll contract survives a proxy cutting a long
    request. The cost of that split: a slot accepted here stays consumed
    even if the background half later fails — a refund cannot be issued from
    a background task, and of the two errors, over-counting is the one the
    wallet survives.
    """
    with _quota(request):
        url = req.url.strip()
        if allowed_link_host(url) is None:
            raise HTTPException(422, SUPPORTED_LINKS_MSG)
        try:
            info = await asyncio.to_thread(resolve_link, url)
        except LinkError as exc:
            raise HTTPException(_LINK_HTTP.get(exc.kind, 422), str(exc))

        # Everything knowable for free is checked before the job exists.
        if info.duration is not None and info.duration > settings.max_media_seconds:
            raise HTTPException(
                413,
                f"That video is {info.duration:.0f}s long; the limit is "
                f"{settings.max_media_seconds}s. Try a shorter clip.",
            )
        needs_asr = info.subtitle is None and info.has_media
        if needs_asr and not settings.sarvam_api_key:
            raise HTTPException(
                503, "Audio checking is not configured (SARVAM_API_KEY missing)."
            )
        if not info.has_media and not info.caption.strip():
            raise HTTPException(422, "That post has no video and no caption to check.")

        report = await _new_job()
        background.add_task(_run_link_job, report.job_id, info, _repo)
        return JobAccepted(job_id=report.job_id, status=report.status)


@router.get("/reports/{job_id}", response_model=TruthReport)
async def get_report(job_id: str) -> TruthReport:
    report = await asyncio.to_thread(_repo.get, job_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    # Invariant 1 on the way out of the STORE, not just out of the engine: a
    # report saved last week was filtered against last week's whitelist.
    return enforce_trust_on_report(report)
