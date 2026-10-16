"""SSE streaming: nobody sees half an answer, nobody sees it twice. Free.

The cases that matter are the ones a phone actually does: reload mid-check,
lose signal and reconnect, open the link an hour later, or hit a server that
restarted. TestClient runs background tasks to completion before returning,
so live-follow behaviour is driven against JobStream directly.
"""
import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from app.api import stream as S
from app.models.answer import Answer, AnswerSection, JobStatus, Source


def _collect(stream: S.JobStream, after: int = 0, limit: int = 50):
    async def run():
        out = []
        async for event in stream.follow(after):
            out.append(event)
            if len(out) >= limit:
                break
        return out
    return asyncio.run(run())


def test_a_subscriber_replays_everything_then_stops_at_done():
    stream = S.JobStream(job_id="j")

    async def fill():
        await stream.publish("status", {"text": "Reading…"})
        await stream.publish("text", {"text": "It is ", "tier": "trusted"})
        await stream.publish("text", {"text": "false.", "tier": "trusted"})
        await stream.publish("done", {})

    asyncio.run(fill())
    events = _collect(stream)

    assert [e[1] for e in events] == ["status", "text", "text", "done"]
    assert [e[0] for e in events] == [1, 2, 3, 4]        # monotonic ids


def test_a_late_joiner_sees_the_whole_answer_not_the_tail():
    """A page that reloads mid-check must not show half an answer."""
    stream = S.JobStream(job_id="j")

    async def run():
        await stream.publish("text", {"text": "first "})
        await stream.publish("text", {"text": "second"})
        await stream.publish("done", {})
        return [e async for e in stream.follow(0)]

    events = asyncio.run(run())
    assert "".join(e[2].get("text", "") for e in events) == "first second"


def test_last_event_id_resumes_without_duplicating():
    """EventSource resends Last-Event-ID on reconnect; without honouring it a
    dropped connection replays the whole answer and the page shows it twice."""
    stream = S.JobStream(job_id="j")

    async def run():
        for word in ["a ", "b ", "c"]:
            await stream.publish("text", {"text": word})
        await stream.publish("done", {})
        return [e async for e in stream.follow(2)]      # saw 1 and 2 already

    events = asyncio.run(run())
    assert "".join(e[2].get("text", "") for e in events) == "c"


def test_a_live_follower_wakes_on_each_new_event():
    stream = S.JobStream(job_id="j")

    async def run():
        received = []

        async def follower():
            async for event in stream.follow(0):
                if event is not None:
                    received.append(event)

        task = asyncio.create_task(follower())
        await asyncio.sleep(0)
        await stream.publish("text", {"text": "live"})
        await stream.publish("done", {})
        await asyncio.wait_for(task, timeout=2)
        return received

    events = asyncio.run(run())
    assert [e[1] for e in events] == ["text", "done"]


def test_a_silent_stream_yields_heartbeats():
    """A thinking-then-searching model is silent for 20-60s, and a proxy was
    measured cutting idle connections at ~100s."""
    stream = S.JobStream(job_id="j")

    async def run():
        beats = 0
        async for event in stream.follow(0):
            if event is None:
                beats += 1
                if beats == 2:
                    await stream.publish("done", {})
        return beats

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(S, "_HEARTBEAT_S", 0.01)
        assert asyncio.run(run()) == 2


def test_done_closes_the_stream_to_further_events():
    stream = S.JobStream(job_id="j")

    async def run():
        await stream.publish("done", {})
        await stream.publish("text", {"text": "too late"})
        return list(stream.events)

    assert [e[1] for e in asyncio.run(run())] == ["done"]


def test_an_error_is_terminal_too():
    stream = S.JobStream(job_id="j")
    asyncio.run(stream.publish("error", {"message": "boom"}))
    assert stream.done is True


def test_the_event_buffer_is_bounded():
    stream = S.JobStream(job_id="j")

    async def run():
        for i in range(S._MAX_EVENTS + 50):
            await stream.publish("text", {"text": str(i)})

    asyncio.run(run())
    assert len(stream.events) == S._MAX_EVENTS


# -- the registry --------------------------------------------------------------

def test_a_stream_is_registered_before_the_job_runs():
    """The page opens its EventSource as soon as it has a job_id, which can be
    before the background task starts — so the job cannot create the entry."""
    job_id = uuid.uuid4().hex
    created = S.create(job_id)
    assert S.get(job_id) is created


def test_finished_streams_are_evicted_after_their_ttl():
    import time

    job_id = uuid.uuid4().hex
    stream = S.create(job_id)
    asyncio.run(stream.publish("done", {}))
    stream.finished_at = time.monotonic() - S._STREAM_TTL_S - 1

    S.create(uuid.uuid4().hex)          # any create() prunes
    assert S.get(job_id) is None


# -- serving a job whose stream is gone ---------------------------------------

def test_a_finished_job_with_no_live_stream_replays_from_the_store():
    """A reload an hour later, or after a restart, must not hang."""
    answer = Answer(
        job_id="j", status=JobStatus.COMPLETE,
        created_at=datetime.now(timezone.utc),
        sections=[AnswerSection(tier="trusted", markdown="It is false.")],
        sources=[Source(url="https://www.altnews.in/x", title="t",
                        tier="trusted")],
    )
    body = S._replay_from_answer(answer)

    assert "event: text" in body
    assert "It is false." in body
    assert "event: source" in body
    assert body.rstrip().endswith('data: {"replayed": true}')


def test_a_deleted_check_is_not_replayed_from_memory(client):
    """REPRODUCED by review S5-16: forget.py deleted the row and /reports
    said 404 — but /stream replayed the whole answer from memory until the
    stream was pruned, up to hours later on a quiet night."""
    from app.store.repository import AnswerRepository

    job_id = client.post("/api/v1/verify/text",
                         json={"text": "5G se corona phailta hai"}).json()["job_id"]
    repo = AnswerRepository()
    answer = repo.get(job_id)
    assert answer.status is JobStatus.COMPLETE and S.get(job_id) is not None
    repo.forget([answer])
    assert client.get(f"/api/v1/reports/{job_id}").status_code == 404
    assert client.get(f"/api/v1/stream/{job_id}").status_code == 404


def test_the_sse_frame_is_well_formed():
    frame = S._sse(7, "text", {"text": "हिंदी"})
    assert frame.startswith("id: 7\nevent: text\ndata: ")
    assert frame.endswith("\n\n")
    assert "हिंदी" in frame          # ensure_ascii=False keeps Devanagari readable
