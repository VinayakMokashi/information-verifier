"""FastAPI entrypoint.

Run locally:
    uvicorn app.main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.config import settings
from app.store.db import init_db

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Information Verifier",
    description="Multi-modal fact-checking engine for combating misinformation in India.",
    version="0.1.0",
    lifespan=lifespan,
)

# Open CORS for local dev; tighten to your PWA origin before deploying.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def reject_oversize_uploads(request: Request, call_next):
    """Refuse huge bodies before anything reads them.

    Route handlers run only after the framework has parsed (and spooled to
    disk) the whole multipart body, so a size check inside the endpoint is
    already too late — a multi-gigabyte POST to the public share link would
    fill the disk and the RAM before being rejected. Content-Length is
    advisory, so the endpoint still checks the real length afterwards.
    """
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > settings.max_media_bytes:
        return JSONResponse(
            {"detail": "File too large. Please send a shorter clip."}, status_code=413
        )
    return await call_next(request)


app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted LAST so the API routes above always win; "/" then serves the
# mobile-first demo page (static/index.html) with no Node/build step.
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
