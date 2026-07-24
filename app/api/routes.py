"""HTTP endpoints — surface-agnostic.

A verify request creates the job row, returns a job_id immediately, and runs
the pipeline as a BackgroundTask (the pipeline can take several seconds).
Clients poll GET /reports/{job_id}. A web PWA and a WhatsApp webhook consume
the exact same two-call contract.
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from app.api.schemas import JobAccepted, VerifyTextRequest
from app.engine.pipeline import run_pipeline
from app.models.report import JobStatus, TruthReport
from app.providers.vision import ocr_image
from app.store.repository import ReportRepository

router = APIRouter(prefix="/api/v1")
_repo = ReportRepository()

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}


def _new_job() -> TruthReport:
    report = TruthReport(
        job_id=uuid.uuid4().hex,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
    )
    _repo.save(report)
    return report


@router.post("/verify/text", response_model=JobAccepted, status_code=202)
async def verify_text(req: VerifyTextRequest, background: BackgroundTasks) -> JobAccepted:
    report = _new_job()
    background.add_task(run_pipeline, report.job_id, req.text, _repo)
    return JobAccepted(job_id=report.job_id, status=report.status)


@router.post("/verify/image", response_model=JobAccepted, status_code=202)
async def verify_image(background: BackgroundTasks, file: UploadFile = File(...)) -> JobAccepted:
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


@router.get("/reports/{job_id}", response_model=TruthReport)
async def get_report(job_id: str) -> TruthReport:
    report = _repo.get(job_id)
    if report is None:
        raise HTTPException(404, "Report not found.")
    return report
