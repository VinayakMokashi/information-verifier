"""HTTP endpoints — surface-agnostic.

A verify request creates the job row, returns a job_id immediately, and runs
the pipeline as a BackgroundTask (the pipeline can take several seconds).
Clients poll GET /reports/{job_id}. A web PWA and a WhatsApp webhook consume
the exact same two-call contract.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile

from app.api.limits import check_and_count
from app.api.schemas import JobAccepted, VerifyTextRequest
from app.config import settings
from app.engine.pipeline import run_pipeline
from app.models.report import JobStatus, TruthReport
from app.providers.asr import get_asr_provider
from app.providers.media import MediaError, normalize_to_wav, split_wav
from app.providers.vision import ocr_image
from app.store.repository import ReportRepository

router = APIRouter(prefix="/api/v1")
_repo = ReportRepository()

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}
# ffmpeg sniffs the real container, so the type gate is deliberately loose —
# browsers label voice notes inconsistently (audio/ogg, application/ogg, …).
_ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")
_ALLOWED_MEDIA_TYPES = {"application/ogg", "application/octet-stream"}


def _new_job() -> TruthReport:
    report = TruthReport(
        job_id=uuid.uuid4().hex,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
    )
    _repo.save(report)
    return report


@router.post("/verify/text", response_model=JobAccepted, status_code=202)
async def verify_text(
    req: VerifyTextRequest, background: BackgroundTasks, request: Request
) -> JobAccepted:
    check_and_count(request)
    report = _new_job()
    background.add_task(run_pipeline, report.job_id, req.text, _repo)
    return JobAccepted(job_id=report.job_id, status=report.status)


@router.post("/verify/image", response_model=JobAccepted, status_code=202)
async def verify_image(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    check_and_count(request)
    if file.content_type not in _ALLOWED_IMAGE_TYPES:
        raise HTTPException(415, f"Unsupported image type: {file.content_type}")
    image_bytes = await file.read()
    # OCR is quick; do it inline so extracted text is captured even if the
    # heavier verification pipeline is deferred to the background.
    extracted = await ocr_image(image_bytes, file.content_type)
    if not extracted:
        raise HTTPException(422, "No text or visual claim could be read from the image.")

    report = _new_job()
    background.add_task(run_pipeline, report.job_id, extracted, _repo)
    return JobAccepted(job_id=report.job_id, status=report.status)


@router.post("/verify/media", response_model=JobAccepted, status_code=202)
async def verify_media(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    check_and_count(request)
    ctype = (file.content_type or "").lower()
    if not (ctype.startswith(_ALLOWED_MEDIA_PREFIXES) or ctype in _ALLOWED_MEDIA_TYPES):
        raise HTTPException(415, f"Unsupported media type: {file.content_type}")
    if not settings.sarvam_api_key:
        raise HTTPException(503, "Audio checking is not configured (SARVAM_API_KEY missing).")

    data = await file.read()
    if len(data) > settings.max_media_bytes:
        raise HTTPException(413, "File too large. Please send a shorter clip.")

    try:
        wav, duration = await asyncio.to_thread(normalize_to_wav, data, file.filename or "media")
    except MediaError as exc:
        raise HTTPException(422, f"Could not read audio from this file ({exc}).")
    if duration > settings.max_media_seconds:
        raise HTTPException(413, f"Audio is {duration:.0f}s long; the limit is "
                                 f"{settings.max_media_seconds}s. Send a shorter clip.")

    # Transcribe inline (like OCR): the transcript is the claim text, and a
    # transcription failure should be a clear 4xx/5xx, not a FAILED job.
    try:
        if duration <= settings.asr_chunk_seconds:
            chunks = [wav]
        else:
            chunks = await asyncio.to_thread(split_wav, wav, settings.asr_chunk_seconds)
        asr = get_asr_provider()
        parts = []
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

    report = _new_job()
    background.add_task(run_pipeline, report.job_id, text, _repo)
    return JobAccepted(job_id=report.job_id, status=report.status)


@router.get("/reports/{job_id}", response_model=TruthReport)
async def get_report(job_id: str) -> TruthReport:
    report = _repo.get(job_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report
