"""FastAPI entrypoint.

Run locally:
    uvicorn app.main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.dashboard import router as dashboard_router
from app.api.routes import router
from app.api.stream import router as stream_router
from app.config import settings
from app.store.db import init_db

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class _BodyTooLarge(Exception):
    """Raised inside the ASGI receive channel to abort an oversize upload."""


async def _send_413(send) -> None:
    body = b'{"detail":"File too large. Please send a shorter clip."}'
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [(b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode())],
    })
    await send({"type": "http.response.body", "body": body})


class LimitUploadSize:
    """Reject oversize request bodies before anything reads them.

    Written as raw ASGI on purpose. A `@app.middleware("http")` function
    cannot do this: Starlette builds the downstream request with its own
    receive channel, so replacing `request._receive` there is ignored and a
    chunked upload sails through (measured: 629 MB spooled against a 1 MB
    cap). Here we own the receive callable the parser actually pulls from.

    Content-Length is checked first as a cheap fast path, but it is advisory
    and absent entirely on chunked uploads, so the body is also counted as
    it streams and aborted the moment it crosses the limit.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        limit = settings.max_media_bytes
        for name, value in scope.get("headers") or []:
            if name == b"content-length" and value.isdigit() and int(value) > limit:
                return await _send_413(send)

        received = 0
        too_large = False
        answered = False

        async def limited_receive():
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    too_large = True
                    # Cut the stream off. Raising here is no good: the
                    # multipart parser catches exceptions and turns them into
                    # a generic 400, so we signal end-of-stream and correct
                    # the status on the way out instead.
                    return {"type": "http.disconnect"}
            return message

        async def tracking_send(message):
            nonlocal answered
            if too_large:
                if not answered:      # replace the app's parse error with 413
                    answered = True
                    await _send_413(send)
                return                # and drop whatever else it tries to send
            await send(message)

        await self.app(scope, limited_receive, tracking_send)
        if too_large and not answered:
            await _send_413(send)


_HOUSEKEEPING_EVERY_S = 6 * 3600


async def _housekeeping_loop() -> None:
    """Forget old messages on a schedule, not only when the server restarts.

    A server that stays up for weeks (a shared link, the Telegram bot) must
    not depend on a restart to delete people's messages after
    answer_retention_days.
    """
    import asyncio

    from app.store.repository import housekeeping

    while True:
        await asyncio.sleep(_HOUSEKEEPING_EVERY_S)
        done = await asyncio.to_thread(housekeeping)
        if any(done.values()):
            print(f"[housekeeping] {done}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    import contextlib

    init_db()
    # BackgroundTasks die with the process, so any QUEUED/PROCESSING row here
    # is dead by definition — it would otherwise be polled forever by a page
    # that will never get an answer.
    from app.store.repository import AnswerRepository, housekeeping

    healed = AnswerRepository().sweep_orphans()
    if healed:
        print(f"[startup] failed {healed} job(s) orphaned by a restart")
    done = housekeeping()
    if any(done.values()):
        print(f"[startup] housekeeping: {done}")
    print("[startup] spending dashboard: /dashboard (this machine only)")
    task = asyncio.create_task(_housekeeping_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


app = FastAPI(
    title="Information Verifier",
    description="Multi-modal fact-checking engine for combating misinformation in India.",
    version="0.1.0",
    lifespan=lifespan,
)

# No CORS grants, deliberately. The page is served BY this app (same origin),
# bots are server-side, and every check spends money — the previous wildcard
# let any website drive checks from its visitors' browsers against a shared
# link. A future PWA on its own origin adds itself back explicitly.
app.add_middleware(LimitUploadSize)

app.include_router(router)
app.include_router(stream_router)
# Local-only; see app/api/dashboard.py. Before the static mount so it wins.
app.include_router(dashboard_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


# Mounted LAST so the API routes above always win; "/" then serves the
# mobile-first demo page (static/index.html) with no Node/build step.
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
