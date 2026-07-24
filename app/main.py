"""FastAPI entrypoint.

Run locally:
    uvicorn app.main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.store.db import init_db


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

app.include_router(router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
