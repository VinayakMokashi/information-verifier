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
from app.engine.pipeline import run_pipeline
from app.models.report import JobStatus, TruthReport
from app.providers.asr import get_asr_provider
from app.providers.links import (
    LinkError, LinkInfo, allowed_link_host, download_link_audio, resolve_link,
    subtitle_text,
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

    The `started` flag is load-bearing, not bookkeeping. Refunding on ANY
    HTTPException looks generous and is a hole: /verify/media raises 422
    ("no speech") and 502 (ASR down) AFTER every chunk has been posted to
    Sarvam and billed by the second, and /verify/image raises 422 ("no text")
    AFTER a paid Opus vision call. Each refund handed the slot back, so a
    loop of silent audio could burn ASR credit all day with the daily counter
    still reading zero — and the error message tells the caller which inputs
    trigger it. A refund is only honest when nothing was bought.
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

        # Transcribe inline (like OCR): the transcript is the claim text, and a
        # transcription failure should be a clear 4xx/5xx, not a FAILED job.
        try:
            if duration <= settings.asr_chunk_seconds:
                chunks = [wav]
            else:
                chunks = await asyncio.to_thread(split_wav, wav, settings.asr_chunk_seconds)
            asr = get_asr_provider()
            parts = []
            spend.begin()      # Sarvam bills per second from the first chunk
            for chunk in chunks:
                transcript = await asr.transcribe(chunk)
                parts.append(transcript.text)
        except MediaError as exc:
            raise HTTPException(422, f"Could not process this audio ({exc}).")
        except (httpx.HTTPError, RuntimeError) as exc:
            # Sarvam down, key rejected, timeout — say so plainly instead of a
            # bare 500 the page can only render as "HTTP 500".
            print(f"[media] transcription failed: {type(exc).__name__}: {exc}")
            raise HTTPException(502, "The transcription service is unavailable right now. "
                                     "Please try again in a minute.")
        text = " ".join(p.strip() for p in parts if p and p.strip())
        if not text:
            raise HTTPException(422, "No speech could be transcribed from this audio.")

        report = await _new_job()
        # Pass the transcript through so the report can show it: speech-to-text
        # can drop a claim's key term, and a silent mis-hear would mean checking
        # a different claim than the one the person sent.
        background.add_task(run_pipeline, report.job_id, text, _repo, text,
                            meter=meter)
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
        if duration <= settings.asr_chunk_seconds:
            chunks = [wav]
        else:
            chunks = await asyncio.to_thread(split_wav, wav, settings.asr_chunk_seconds)
        asr = get_asr_provider()
        parts = []
        for chunk in chunks:
            transcript = await asr.transcribe(chunk)
            parts.append(transcript.text)
        spoken = " ".join(p.strip() for p in parts if p and p.strip())

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
            raise HTTPException(
                422,
                "Only public Instagram and YouTube links can be checked "
                "(https://www.instagram.com/reel/…, https://youtube.com/shorts/…).",
            )
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
    return report
