"""Live answer streaming (SSE) — the chat feel, without forking the truth.

Two rules shape this:

**The persisted Answer is canonical.** The stream is a preview; when it ends,
the page fetches `/reports/{job_id}` and re-renders from the stored object. So
streamed text and stored text can never drift, the Telegram bot keeps reading
one endpoint, and a reload after the job finished behaves identically to
watching it live.

**A late subscriber must see everything.** Every event carries a sequence id
and is buffered, so a page that reloads mid-check — or an EventSource that
reconnects with `Last-Event-ID` — replays what it missed instead of showing
half an answer or a duplicated one.

Single-process only, like the rate limiter it sits beside: an in-memory
registry means `uvicorn --workers 1`.
"""
import asyncio
import json
import time
from dataclasses import dataclass, field

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/v1")

_HEARTBEAT_S = 15.0      # a proxy was measured cutting idle connections at ~100 s
_STREAM_TTL_S = 900.0    # keep a finished stream replayable for 15 minutes
_MAX_EVENTS = 4000       # bounded by chat_max_tokens in practice


@dataclass
class JobStream:
    """One job's event log, replayable and followable.

    No lock: publish and follow both run on the one event loop and neither
    awaits between reading and mutating. An `asyncio.Condition` here was worse
    than useless — `follow` would suspend at a `yield` while still holding it,
    so `publish` could never acquire it and the whole stream deadlocked.
    """

    job_id: str
    events: list[tuple[int, str, dict]] = field(default_factory=list)
    done: bool = False
    finished_at: float | None = None
    _waiters: list[asyncio.Future] = field(default_factory=list)

    async def publish(self, kind: str, data: dict) -> None:
        if self.done:
            return
        if len(self.events) < _MAX_EVENTS:
            self.events.append((len(self.events) + 1, kind, data))
        if kind in ("done", "error"):
            self.done = True
            self.finished_at = time.monotonic()
        for waiter in self._waiters:
            if not waiter.done():
                waiter.set_result(None)
        self._waiters.clear()

    async def close(self) -> None:
        """Terminal even if the job crashed before publishing anything."""
        await self.publish("done", {})

    async def _wait(self, timeout: float) -> bool:
        """True if something was published, False on heartbeat timeout."""
        waiter = asyncio.get_running_loop().create_future()
        self._waiters.append(waiter)
        try:
            await asyncio.wait_for(waiter, timeout)
            return True
        except asyncio.TimeoutError:
            return False
        finally:
            if waiter in self._waiters:
                self._waiters.remove(waiter)

    async def follow(self, after: int = 0):
        """Yield (id, kind, data) from `after`, then live until done.

        Yields None on a heartbeat tick so the caller can emit an SSE comment
        and keep a proxy from cutting an idle connection.
        """
        while True:
            pending = [e for e in self.events if e[0] > after]
            if pending:
                for event in pending:
                    after = event[0]
                    yield event
                continue
            if self.done:
                return
            if not await self._wait(_HEARTBEAT_S):
                yield None


_streams: dict[str, JobStream] = {}


def create(job_id: str) -> JobStream:
    """Register a stream BEFORE the 202 goes out.

    The page opens its EventSource as soon as it has a job_id, which can be
    before the background task starts — so the registry entry cannot be
    created by the job itself without a race.
    """
    _prune()
    stream = JobStream(job_id=job_id)
    _streams[job_id] = stream
    return stream


def get(job_id: str) -> JobStream | None:
    return _streams.get(job_id)


def _prune() -> None:
    now = time.monotonic()
    for job_id, stream in list(_streams.items()):
        if stream.finished_at is not None and now - stream.finished_at > _STREAM_TTL_S:
            del _streams[job_id]


def _sse(event_id: int, kind: str, data: dict) -> str:
    return (f"id: {event_id}\n"
            f"event: {kind}\n"
            f"data: {json.dumps(data, ensure_ascii=False)}\n\n")


def _replay_from_answer(answer) -> str:
    """A finished job with no live stream — serve the stored Answer.

    Covers the two cases that would otherwise hang: a reload long after the
    check finished, and a server restart that took the in-memory stream with
    it. The page renders from the persisted object anyway, so this only needs
    to be enough to get it there.
    """
    chunks = []
    seq = 0
    for section in answer.sections:
        seq += 1
        chunks.append(_sse(seq, "text", {"text": section.markdown,
                                         "tier": section.tier}))
    for source in answer.sources:
        seq += 1
        chunks.append(_sse(seq, "source", source.model_dump()))
    seq += 1
    chunks.append(_sse(seq, "done", {"replayed": True}))
    return "".join(chunks)


@router.get("/stream/{job_id}")
async def stream_answer(job_id: str, request: Request):
    from app.api.routes import _repo   # local import: avoids a cycle at import

    stream = get(job_id)
    if stream is None:
        answer = await asyncio.to_thread(_repo.get, job_id)
        if answer is None:
            raise HTTPException(404, "No such check.")
        return StreamingResponse(
            iter([_replay_from_answer(answer)]),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # EventSource resends this automatically on reconnect; honouring it is
    # what stops a dropped connection from duplicating the whole answer.
    try:
        after = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        after = 0

    async def events():
        async for event in stream.follow(after):
            if await request.is_disconnected():
                return
            if event is None:
                yield ": ping\n\n"       # keeps proxies from cutting an idle turn
                continue
            yield _sse(*event)

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
