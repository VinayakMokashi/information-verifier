"""FastAPI entrypoint.

Run locally:
    uvicorn app.main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

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


_TOO_LARGE_UPLOAD = b'{"detail":"File too large. Please send a shorter clip."}'
_TOO_LARGE_MESSAGE = (b'{"detail":"That message is too long. '
                      b'Send the part you want checked."}')

# The only routes that take a file. Decided by PATH, which the server owns:
# Content-Type is the client's word, and a JSON route must never get the
# upload allowance by claiming to be multipart.
_UPLOAD_PATHS = frozenset({"/api/v1/verify/image", "/api/v1/verify/media"})


async def _send_413(send, body: bytes = _TOO_LARGE_UPLOAD) -> None:
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

        upload = scope.get("path") in _UPLOAD_PATHS
        limit = settings.max_media_bytes if upload else settings.max_json_bytes
        refusal = _TOO_LARGE_UPLOAD if upload else _TOO_LARGE_MESSAGE
        for name, value in scope.get("headers") or []:
            if name == b"content-length" and value.isdigit() and int(value) > limit:
                return await _send_413(send, refusal)

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
                    await _send_413(send, refusal)
                return                # and drop whatever else it tries to send
            await send(message)

        await self.app(scope, limited_receive, tracking_send)
        if too_large and not answered:
            await _send_413(send, refusal)


_PAID_PREFIX = "/api/v1/verify/"
_CROSS_SITE_REFUSAL = (b'{"detail":"Checks can only be sent from the Information '
                       b'Verifier page itself."}')


def _cross_site(scope) -> bool:
    """Did another website's page make this request?

    A browser says so itself: Sec-Fetch-Site on every request (modern
    browsers, over HTTPS and to localhost), and Origin on every cross-origin
    POST. A request with neither did not come from a page at all — the
    Telegram bot, curl — and a cross-site forgery needs a page.
    """
    headers = {}
    for name, value in scope.get("headers") or []:
        headers.setdefault(name, value.decode("latin-1"))
    fetch_site = headers.get(b"sec-fetch-site")
    if fetch_site is not None:
        # "none": the user typed or bookmarked it; never a page's POST.
        return fetch_site.strip().lower() not in ("same-origin", "none")
    origin = headers.get(b"origin")
    if origin is None:
        return False
    try:
        netloc = urlsplit(origin.strip()).netloc.lower()
    except ValueError:
        return True
    # "null" (a sandboxed frame, a data: URL) has no netloc: refused.
    return not netloc or netloc != headers.get(b"host", "").strip().lower()


class RefuseCrossSite:
    """No other website can submit a paid check through its visitors.

    REPRODUCED 2026-10-15 in real headless Chrome: a page on another origin
    made the browser POST /verify/image — multipart/form-data is a
    CORS-"simple" request, so no preflight ever asked this app — and the
    server ran the paid vision call and took a daily slot, from the
    visitor's own IP, past every per-visitor limit. Dropping the CORS
    wildcard (below) had only ever stopped the JSON routes. Raw ASGI and
    outermost, so the refusal comes before a byte of the body is read.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope.get("method") == "POST"
                and scope.get("path", "").startswith(_PAID_PREFIX)
                and _cross_site(scope)):
            await send({"type": "http.response.start", "status": 403,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length",
                                     str(len(_CROSS_SITE_REFUSAL)).encode())]})
            await send({"type": "http.response.body", "body": _CROSS_SITE_REFUSAL})
            return
        await self.app(scope, receive, send)


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
    description="Checks whether a forward, screenshot, voice note or reel link is "
                "true — one Claude-style answer with its sources.",
    version="0.1.0",
    lifespan=lifespan,
)

# No CORS grants, deliberately. The page is served BY this app (same origin),
# bots are server-side, and every check spends money — the previous wildcard
# let any website drive checks from its visitors' browsers against a shared
# link. A future PWA on its own origin adds itself back explicitly. That
# stops only the JSON routes: RefuseCrossSite covers the form-post ones.
app.add_middleware(LimitUploadSize)
app.add_middleware(RefuseCrossSite)     # added last = outermost = runs first

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
