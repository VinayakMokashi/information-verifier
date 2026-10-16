"""FastAPI entrypoint.

Run locally:
    uvicorn app.main:app --reload

Interactive API docs at http://127.0.0.1:8000/docs
"""
import re
import shutil
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
# The very function Starlette's router matches routes with, so the raw ASGI
# middlewares below judge the same path the router will route (review R4).
# A private module: if an upgrade moves it, the import fails loudly at
# startup, and tests/test_cross_site.py pins the root-path behaviour.
from starlette._utils import get_route_path

from app.api.dashboard import router as dashboard_router
from app.api.local import names_this_machine
from app.api.routes import router
from app.api.stream import router as stream_router
from app.config import settings
from app.store.db import get_conn, init_db

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

        # The ROUTE path: with a root_path, uvicorn puts the prefix in
        # scope["path"], and every real screenshot was refused as "too long"
        # (review R4, reproduced on real uvicorn).
        upload = get_route_path(scope) in _UPLOAD_PATHS
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


# A plain DNS name, with an optional port: the only shape a public name can
# match, and the only shape ever printed (a refused Host is a visitor's text).
_PUBLIC_NAME = re.compile(r"([a-z0-9.-]+)(?::\d{1,5})?")
_REFUSED_HOSTS: set[str] = set()


def _our_host(scope) -> bool:
    """Is this request addressed to one of this app's own names?

    REPRODUCED (review R5, real uvicorn): a page re-resolves ITS OWN name to
    127.0.0.1, and the owner's browser — same-origin to that name, so
    Sec-Fetch-Site says same-origin and Origin equals Host — posted a paid
    check here and could read the answer. But the browser still sends the
    page's name as Host, which a page cannot choose. So a paid check must
    name this machine (the dashboard's rule, app/api/local.py) or a public
    name in settings.public_hosts, in exactly one Host header. Checking only
    requests that carry no proxy header would not do: a same-origin page
    can add X-Forwarded-For itself.
    """
    hosts = [value for name, value in scope.get("headers") or [] if name == b"host"]
    if len(hosts) != 1:
        return False
    host = hosts[0].decode("latin-1").strip().lower()
    if names_this_machine(host):
        return True
    shape = _PUBLIC_NAME.fullmatch(host)
    if not shape:
        return False
    name = shape.group(1)
    name = name[:-1] if name.endswith(".") else name    # the FQDN form, "x.com."
    for entry in (e.strip().lower() for e in settings.public_hosts.split(",")):
        if entry.startswith("."):
            if name.endswith(entry) and len(name) > len(entry):
                return True
        elif entry and name == entry:
            return True
    # Going live, every visitor arrives under the public name: a missing
    # PUBLIC_HOSTS would refuse them all with no word on the server. Once a
    # name, and a bounded set, so a flood of made-up names prints little.
    if name not in _REFUSED_HOSTS and len(_REFUSED_HOSTS) < 64:
        _REFUSED_HOSTS.add(name)
        print(f"[host] refused paid checks addressed to {name!r}, which is not one "
              f"of this app's names. If it IS this app's public name, add it to "
              f"PUBLIC_HOSTS in .env; otherwise ignore this.")
    return False


class RefuseCrossSite:
    """No other website can submit a paid check through its visitors.

    REPRODUCED 2026-10-15 in real headless Chrome: a page on another origin
    made the browser POST /verify/image — multipart/form-data is a
    CORS-"simple" request, so no preflight ever asked this app — and the
    server ran the paid vision call and took a daily slot, from the
    visitor's own IP, past every per-visitor limit. Dropping the CORS
    wildcard (below) had only ever stopped the JSON routes. Raw ASGI and
    outermost, so the refusal comes before a byte of the body is read. A
    same-origin page under ANOTHER name — DNS rebinding — is refused by
    its Host (_our_host).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (scope["type"] == "http" and scope.get("method") == "POST"
                and get_route_path(scope).startswith(_PAID_PREFIX)
                and (_cross_site(scope) or not _our_host(scope))):
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


_YTDLP_STALE_DAYS = 30


def _ytdlp_released():
    """yt-dlp's version IS its release date (2026.8.19); read from the
    installed metadata, so the heavy package is not imported to learn it."""
    from datetime import date
    from importlib.metadata import PackageNotFoundError, version

    try:
        year, month, day = (int(part) for part in version("yt-dlp").split(".")[:3])
        return date(year, month, day)
    except (PackageNotFoundError, ValueError, TypeError):
        return None


def _ytdlp_staleness(today=None) -> str | None:
    """A note when the installed yt-dlp is old (audit-ops OPS-25): the
    platforms change under it, a 24/7 server never updates it by itself,
    and reel links then fail for every stranger as "could not be read"."""
    from datetime import date

    released = _ytdlp_released()
    if released is None:
        return None
    age = ((today or date.today()) - released).days
    if age <= _YTDLP_STALE_DAYS:
        return None
    return (f"[startup] yt-dlp is {age} days old - the platforms change under it. "
            r"Update: .venv\Scripts\python.exe -m pip install -U yt-dlp")


_SWEEP_EVERY_S = 300
# Longer than any check really runs (the longest measured: a two-pass check
# at 295 s; a link adds its download and transcription), so a row this old
# whose job is no longer running here is stuck, not slow.
_STUCK_AFTER_S = 1800


async def _sweep_stale_once() -> int:
    """Fail jobs stuck mid-flight that no job here is still on (audit-ops
    OPS-06: one failed final save wedged a row, its page and its bot chat
    until a restart). A database read and writes: off the event loop."""
    import asyncio

    from app.api import stream as job_stream
    from app.store.repository import AnswerRepository

    try:
        healed = await asyncio.to_thread(AnswerRepository().sweep_stale,
                                         _STUCK_AFTER_S, job_stream.running)
    except Exception as exc:  # noqa: BLE001 — the next sweep tries again
        print(f"[sweep] failed: {type(exc).__name__}: {exc}")
        return 0
    if healed:
        print(f"[sweep] failed {healed} job(s) stuck mid-flight")
    return healed


async def _sweep_loop() -> None:
    import asyncio

    while True:
        await asyncio.sleep(_SWEEP_EVERY_S)
        await _sweep_stale_once()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import sys

    from app.store import instance

    # Line by line even when stdout is a pipe or a file (a service manager):
    # block-buffered, diagnostics arrived hours late and a killed process
    # lost them (audit-ops OPS-20, reproduced). Not left to whoever starts
    # the app remembering PYTHONUNBUFFERED.
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(line_buffering=True)
        except (OSError, ValueError):
            pass

    # FIRST, before _serving's startup sweep can touch a running copy's checks
    # (audit OPS-05: a second start failed them all, then died on the busy port).
    db_path = settings.db_path
    try:
        instance.acquire(db_path)
    except instance.AlreadyRunning:
        print("[startup] the app is already running on this database (another "
              "window? start.cmd?) — not starting a second copy. Close the other "
              "one first.")
        raise
    try:
        async with _serving():
            yield
    finally:
        instance.release(db_path)


@asynccontextmanager
async def _serving():
    import asyncio
    import contextlib

    init_db()
    # BackgroundTasks die with the process, so any QUEUED/PROCESSING row here
    # is dead by definition — it would otherwise be polled forever by a page
    # that will never get an answer. (Only once this process holds the
    # database: see the lock above.)
    from app.store.repository import AnswerRepository, housekeeping

    healed = AnswerRepository().sweep_orphans()
    if healed:
        print(f"[startup] failed {healed} job(s) orphaned by a restart")
    done = housekeeping()
    if any(done.values()):
        print(f"[startup] housekeeping: {done}")
    print("[startup] spending dashboard: /dashboard (this machine only)")
    stale = _ytdlp_staleness()
    if stale:
        print(stale)
    from app.providers import turnstile

    if settings.public_hosts.strip() and not turnstile.enabled():
        # Going live without it is silent otherwise: every visitor's browser
        # could submit paid checks with no person proven behind them.
        print("[startup] PUBLIC_HOSTS is set but Turnstile is not: visitors' paid "
              "checks are not challenged. Set TURNSTILE_SITE_KEY and "
              "TURNSTILE_SECRET_KEY in .env (decided 2026-10-15).")
    tasks = [asyncio.create_task(_housekeeping_loop()), asyncio.create_task(_sweep_loop())]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
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
    """Liveness only: the process answers. Whether a check would WORK here
    is /ready's question."""
    return {"status": "ok"}


# /ready's own deadline for a database write and read-back: past it, the
# pool /reports uses is starved or the database is held, and that is "not
# ready" however healthy the process looks.
_READY_TIMEOUT_S = 3.0


def _probe_database() -> bool:
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO ready_probe (id, at) VALUES (1, ?)", (now,))
        row = conn.execute("SELECT at FROM ready_probe WHERE id = 1").fetchone()
    return row is not None and row["at"] == now


@app.get("/ready")
async def ready() -> JSONResponse:
    """Would a check actually work here? REPRODUCED (audit-ops OPS-18): the
    constant /health stayed green while the database was locked, the pool
    starved (/health 10 ms while /reports took 19 s), the keys were missing
    — or while it was the free DEMO server, which the bot would then wire to
    people as if real (PROJECT_PLAN §11 19). Booleans and the mode only:
    what this server spends is the dashboard's business, not a probe's."""
    import asyncio

    try:
        database = await asyncio.wait_for(asyncio.to_thread(_probe_database),
                                          _READY_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 — any failure is "not ready"
        print(f"[ready] database probe failed: {type(exc).__name__}")
        database = False
    checks = {"database": bool(database),
              "keys": bool(settings.anthropic_api_key),
              "ffmpeg": bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))}
    ok = all(checks.values())
    return JSONResponse({"status": "ready" if ok else "not ready",
                         "mode": "demo" if settings.demo_mode else "real",
                         "checks": checks},
                        status_code=200 if ok else 503)


# Mounted LAST so the API routes above always win; "/" then serves the
# mobile-first demo page (static/index.html) with no Node/build step.
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
