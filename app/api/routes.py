"""HTTP endpoints — surface-agnostic.

A verify request creates the job row, returns a job_id immediately, and runs
the check as a BackgroundTask (a check takes tens of seconds).
Clients poll GET /reports/{job_id}. A web PWA and a WhatsApp webhook consume
the exact same two-call contract.
"""
import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile

from app.api.limits import refund, refund_daily, reserve
from app.api.schemas import JobAccepted, VerifyLinkRequest, VerifyTextRequest
from app.config import settings
from app.api import stream as job_stream
from app.engine.job import run_check
from app.models.answer import Answer, JobStatus
from app.providers.asr import get_asr_provider
from app.providers.links import (
    SUPPORTED_LINKS_MSG, LinkError, LinkInfo, allowed_link_host,
    download_link_audio, resolve_link, subtitle_text,
)
from app.providers.media import MediaError, MediaTooLong, normalize_to_wav, split_wav
from app.providers.usage import UsageMeter
from app.providers.vision import ocr_image
from app.trusted_sources import is_trusted_url
from app.store.repository import AnswerRepository, safe_cache_call

router = APIRouter(prefix="/api/v1")
_repo = AnswerRepository()

_ALLOWED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}

# Every error below is read by a person, often on a phone, often not in their
# first language. Measured 2026-09-22 before fixing: ffmpeg's own stderr, raw
# MIME types and an environment-variable name were all reaching them. The
# technical detail goes to the server log; the person gets what to do next.
_MSG_NOT_AN_IMAGE = ("That doesn't look like a picture. Send a screenshot or "
                     "a photo (PNG, JPG, WEBP or GIF).")
_MSG_NOT_MEDIA = ("That doesn't look like audio or video. Send a voice note "
                  "or a video file.")
_MSG_BAD_AUDIO = ("The audio in that file couldn't be read. Try sending it "
                  "again, or as a different file.")
_MSG_NO_ASR = ("Voice notes and videos can't be checked here right now. "
               "Send the message as text instead.")
# ffmpeg sniffs the real container, so the type gate is deliberately loose —
# browsers label voice notes inconsistently (audio/ogg, application/ogg, …).
_ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")
_ALLOWED_MEDIA_TYPES = {"application/ogg", "application/octet-stream"}


class _Spend:
    """Whether this request has already cost money, and which day it counted.

    `day` is the daily-cap day the slot was charged to (None when rate
    limiting is off), carried to the background job so a check that turns
    out to be FREE can hand its slot back — see `_settle_quota`.
    """

    __slots__ = ("started", "day")

    def __init__(self, day: str | None = None) -> None:
        self.started = False
        self.day = day

    def begin(self) -> None:
        """Call immediately BEFORE the first paid call of the request."""
        self.started = True


@asynccontextmanager
async def _quota(request: Request):
    """Claim a check up front; hand it back only if we never spent anything.

    Reserving first is what makes the cap real — checking now and consuming
    after an upload has been read leaves a window where any number of
    concurrent requests pass the same empty counter.

    Both the claim and the refund are SQLite writes, so both run in a thread.
    Found by review, measured: on the event loop, a claim that waited for
    another writer's lock froze every request and every live stream with it.

    The `started` flag is load-bearing, not bookkeeping: /verify/image raises
    422 ("no text in this image") AFTER a paid Opus vision call, and refunding
    that rejection handed the slot back — a loop of blank images could burn
    budget all day with the daily counter reading zero. A refund is only
    honest when nothing was bought. (The media ASR spend that used to share
    this trap now runs behind the 202, where no refund path exists at all.)
    """
    spend = _Spend(await asyncio.to_thread(reserve, request))
    try:
        yield spend
    except HTTPException:
        if not spend.started:
            await asyncio.to_thread(refund, request, spend.day)
        raise


async def _settle_quota(job_id: str, repo, quota_day: str | None) -> None:
    """Hand the day's slot back when the check turned out to cost nothing.

    With a cap of 2 a day (Vinayak, 2026-09-22), a forward someone sends twice
    would otherwise spend half the day's allowance on an answer served from
    cache for $0. Deliberately narrow: only a CLEAN cache hit whose measured
    bill is exactly zero. Anything that paid for OCR or a transcript keeps its
    slot, and so does a failure — a stream that died mid-answer may have been
    billed without its usage ever being recorded, and the cap exists for
    exactly the cases nobody measured.
    """
    if quota_day is None:
        return
    answer = await asyncio.to_thread(repo.get, job_id)
    if (answer is not None and answer.cached and answer.usage is not None
            and answer.usage.estimated_usd == 0):
        await asyncio.to_thread(refund_daily, quota_day)


async def _check(job_id: str, text: str, repo, stream=None, *,
                 derived_text: str | None = None, meter=None,
                 quota_day: str | None = None, kind: str = "text") -> None:
    """run_check, then settle the day's slot. Every route's engine call."""
    await run_check(job_id, text, repo, stream, derived_text=derived_text,
                    meter=meter, kind=kind)
    await _settle_quota(job_id, repo, quota_day)


async def _new_job(input_text: str = ""):
    """Create the job row AND its event stream before the 202 is sent.

    Registration order is load-bearing: the page opens its EventSource the
    moment it has a job_id, which can be before the BackgroundTask has
    started. If the job created the stream, that race would drop the opening
    events of every fast check.
    """
    answer = Answer(
        job_id=uuid.uuid4().hex,
        status=JobStatus.QUEUED,
        created_at=datetime.now(timezone.utc),
        input_text=input_text,
    )
    # SQLite calls are synchronous and can wait on a write lock; off the loop
    # so one contended write cannot stall every other request in the server.
    await asyncio.to_thread(_repo.save, answer)
    stream = job_stream.create(answer.job_id)
    return answer, stream


async def fail_job(job_id: str, message: str, repo, meter: UsageMeter,
                   stream=None, kind: str = "media") -> None:
    """Finalize a job that failed BEFORE the engine ran, on every surface.

    The stream half is not optional, and leaving it out was a real defect in
    both callers: a stored FAILED answer that never publishes leaves an SSE
    subscriber waiting on heartbeats forever, so the page shows "Checking…"
    indefinitely for a failure the server has already diagnosed and written
    down. Before streaming existed the page only polled, so saving the row was
    enough. It is not any more.

    One function because there were two, and they had already diverged — the
    media path attached the meter snapshot, the link path very nearly did not.
    """
    answer = await asyncio.to_thread(repo.get, job_id)
    if answer is not None:
        answer.status = JobStatus.FAILED
        answer.error = message
        answer.usage = meter.snapshot()      # a failed fetch still spent ASR
        answer.completed_at = datetime.now(timezone.utc)
        await asyncio.to_thread(repo.save, answer)
        await safe_cache_call(repo.ledger.record, answer, kind)
    if stream is not None:
        await stream.publish("error", {"message": message})


async def transcribe_wav(wav: bytes, duration: float) -> str:
    """16 kHz WAV -> transcript. The single ASR tail both audio paths use.

    It was copy-pasted between the media route and the link path; a change
    to chunking (overlap, a language hint, per-chunk retry) had to be made
    twice or the two surfaces would transcribe the same audio differently.

    Chunks are transcribed CONCURRENTLY and reassembled by index. Sarvam
    bills audio seconds, not requests, so this costs nothing — but a 300 s
    clip is ~11 chunks, and serially that is minutes of pure network wait
    that pushed jobs past the page's and the bot's poll windows (whose
    expiry used to invite a fully re-billed resubmission).
    """
    if duration <= settings.asr_chunk_seconds:
        chunks = [wav]
    else:
        chunks = await asyncio.to_thread(split_wav, wav, settings.asr_chunk_seconds)
    asr = get_asr_provider()
    transcripts = await asyncio.gather(*(asr.transcribe(c) for c in chunks))
    return " ".join(t.text.strip() for t in transcripts if t.text and t.text.strip())


async def _run_media_job(
    job_id: str, wav: bytes, duration: float, repo, meter: UsageMeter, stream=None,
    quota_day: str | None = None,
) -> None:
    """Background half of /verify/media: chunk -> Sarvam -> the check.

    A failure here becomes a FAILED report with a readable error — the page
    renders those — never a silent PROCESSING-forever. The transcript passes
    through as derived_text so the report shows what was heard (invariant 4):
    ASR can drop a claim's key term, and a silent mis-hear would mean
    checking a different claim than the one the person sent.
    """
    async def fail(message: str) -> None:
        await fail_job(job_id, message, repo, meter, stream, kind="media")

    try:
        text = await transcribe_wav(wav, duration)
    except MediaError as exc:
        print(f"[media] audio unreadable: {exc}")
        await fail(_MSG_BAD_AUDIO)
        return
    except (httpx.HTTPError, RuntimeError) as exc:
        # Sarvam down, key rejected, timeout — say so plainly.
        print(f"[media] transcription failed: {type(exc).__name__}: {exc}")
        await fail("The transcription service is unavailable right now. "
                   "Please try again in a minute.")
        return
    except Exception as exc:  # noqa: BLE001 — nothing may die silently here
        print(f"[media] unexpected failure: {type(exc).__name__}: {exc}")
        await fail("Something went wrong reading this audio. Please try again.")
        return

    if not text:
        await fail("No speech could be transcribed from this audio.")
        return
    await _check(job_id, text, repo, stream, derived_text=text, meter=meter,
                 quota_day=quota_day, kind="media")


@router.post("/verify/text", response_model=JobAccepted, status_code=202)
async def verify_text(
    req: VerifyTextRequest, background: BackgroundTasks, request: Request
) -> JobAccepted:
    async with _quota(request) as spend:
        if len(req.text) > settings.max_input_chars:
            raise HTTPException(
                413,
                f"That message is {len(req.text)} characters; the limit is "
                f"{settings.max_input_chars}. Send the part you want checked.",
            )
        answer, stream = await _new_job(req.text)
        background.add_task(_check, answer.job_id, req.text, _repo, stream,
                            quota_day=spend.day)
        return JobAccepted(job_id=answer.job_id, status=answer.status)


@router.post("/verify/image", response_model=JobAccepted, status_code=202)
async def verify_image(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    async with _quota(request) as spend:
        if file.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, _MSG_NOT_AN_IMAGE)
        image_bytes = await file.read()
        # OCR is quick; do it inline so extracted text is captured even if the
        # check itself runs in the background.
        spend.begin()          # everything past here has been paid for
        meter = UsageMeter()   # starts at the first paid call, so the report's
        with meter.activate():  # the bill includes route-level OCR, not just the check
            extracted = await ocr_image(image_bytes, file.content_type)
        if not extracted:
            raise HTTPException(422, "No text or visual claim could be read from the image.")

        answer, stream = await _new_job(extracted)
        background.add_task(_check, answer.job_id, extracted, _repo, stream,
                            derived_text=extracted, meter=meter,
                            quota_day=spend.day, kind="image")
        return JobAccepted(job_id=answer.job_id, status=answer.status)


@router.post("/verify/media", response_model=JobAccepted, status_code=202)
async def verify_media(
    background: BackgroundTasks, request: Request, file: UploadFile = File(...)
) -> JobAccepted:
    # `spend.begin()` is never called: since the Sarvam loop moved behind the
    # 202, this route spends nothing before returning, so every rejection here
    # is honestly refundable. `spend` is bound only to carry the day.
    async with _quota(request) as spend:
        ctype = (file.content_type or "").lower()
        if not (ctype.startswith(_ALLOWED_MEDIA_PREFIXES) or ctype in _ALLOWED_MEDIA_TYPES):
            raise HTTPException(415, _MSG_NOT_MEDIA)
        if not settings.sarvam_api_key:
            print("[config] SARVAM_API_KEY is missing; audio cannot be transcribed")
            raise HTTPException(503, _MSG_NO_ASR)

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
            print(f"[media] upload unreadable: {exc}")
            raise HTTPException(422, _MSG_BAD_AUDIO)

        # Everything free and fast has now run: the type gate, the byte cap
        # and the ffmpeg decode with its duration cap all reject with clear
        # HTTP errors. The SLOW, PAID part — the Sarvam loop — runs in the
        # background: the audit showed a proxy cutting long inline requests
        # at ~100 s while the server kept spending, and a 202-then-poll
        # contract survives that. Same trade as /verify/link, same documented
        # cost: the quota slot stays consumed even if transcription fails.
        answer, stream = await _new_job()
        background.add_task(_run_media_job, answer.job_id, wav, duration, _repo,
                            meter, stream, quota_day=spend.day)
        return JobAccepted(job_id=answer.job_id, status=answer.status)


# LinkError.kind -> HTTP status. Everything the user can fix is 422; only a
# platform we could not reach is the server's fault (502).
_LINK_HTTP = {"network": 502}

# The resolve runs INLINE — a caller is waiting for the 202 — and yt-dlp's
# own socket timeout is per operation, not per resolve. Traced by review: the
# Telegram bot gave up at 30 s and told the person to try again while this
# route went on to create and bill a job whose answer nobody would deliver.
# A Facebook reel measured 14 s. The bot now waits far longer than this.
_RESOLVE_WALL_S = 60.0

# The post's own caption text is a supplement, not the main source — cap its
# contribution so a stuffed caption cannot inflate the extract call. (The
# spoken text is bounded by max_media_seconds already.)
_MAX_CAPTION_CHARS = 2000


def _caption_text(info: LinkInfo) -> str:
    """The post's caption as it enters the text — normalized and capped."""
    return " ".join((info.caption or "").split())[:_MAX_CAPTION_CHARS]


async def gather_link_text(info: LinkInfo) -> str:
    """Everything readable from the post: caption + (subtitles | audio->ASR).

    Cost order is the point (measured, §0a): the caption is already in hand
    ($0); a subtitle track replaces ASR outright ($0 — YouTube's '-orig'
    auto-captions ARE the speech recognition we would otherwise buy); and
    only when neither covers the speech is audio downloaded (byte/wall-capped
    stream), ffprobe'd against the duration cap, and sent to Sarvam.
    """
    caption = _caption_text(info)

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
        spoken = await transcribe_wav(wav, duration)

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


def transcript_key(info: LinkInfo) -> str | None:
    """The transcript cache key: the platform's own id, known for free.

    Versioned, so a change to how link text is gathered (the caption cap, the
    subtitle choice) can retire every entry at once. None when the platform
    gave no id — an unkeyable post is simply not cached.
    """
    if not info.video_id or not info.platform:
        return None
    return f"v1:{info.platform.lower()}:{info.video_id}"


async def _run_link_job(job_id: str, info: LinkInfo, repo, stream=None,
                        quota_day: str | None = None) -> None:
    """Background half: fetch the text (or its cached transcript), then check it.

    A failure here becomes a FAILED report with a readable error (the page
    renders those), never a silent PROCESSING-forever. run_check guards
    itself; this guard covers the fetch/ASR work before it.
    """
    meter = UsageMeter()
    key = transcript_key(info)
    # A cache failure degrades to doing the work (invariant 6), never to a
    # failed check — so the lookup and the store both go through
    # safe_cache_call.
    text = await safe_cache_call(repo.transcripts.get, key) if key else None
    if text:
        print(f"[link] transcript cache hit for {key}: no download, no ASR")
    else:
        try:
            with meter.activate():   # the download's normalize notes ASR seconds
                text = await gather_link_text(info)
        except Exception as exc:  # noqa: BLE001 — every failure must reach the report
            await fail_job(job_id, _friendly_link_failure(exc), repo, meter,
                           stream, kind="link")
            return
        # Remember only what the audio or subtitles ADDED. Text that is just
        # the caption means the transcription heard nothing — maybe a music
        # reel, maybe a hiccup — and the cache's rule is to retry that, not
        # to remember it as the post for 30 days (found by review: the empty
        # check ran on caption + speech combined). A caption is free to read
        # again; re-hearing a music-only reel costs its ASR, a few paise.
        if key and text.strip() != _caption_text(info).strip():
            await safe_cache_call(repo.transcripts.put, key, text)
    await _check(job_id, text, repo, stream, derived_text=text, meter=meter,
                 quota_day=quota_day, kind="link")


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
    async with _quota(request) as spend:
        url = req.url.strip()
        if allowed_link_host(url) is None:
            raise HTTPException(422, SUPPORTED_LINKS_MSG)
        try:
            # On timeout the thread runs on until yt-dlp gives up; its result
            # is discarded, and no job exists yet, so nothing is billed.
            info = await asyncio.wait_for(asyncio.to_thread(resolve_link, url),
                                          _RESOLVE_WALL_S)
        except TimeoutError:
            print(f"[link] resolve took over {_RESOLVE_WALL_S:.0f}s; refused")
            raise HTTPException(502, "The platform could not be reached right "
                                     "now. Try again in a minute.")
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
            print("[config] SARVAM_API_KEY is missing; this link needs transcription")
            raise HTTPException(503, _MSG_NO_ASR)
        if not info.has_media and not info.caption.strip():
            raise HTTPException(422, "That post has no video and no caption to check.")

        answer, stream = await _new_job(url)
        background.add_task(_run_link_job, answer.job_id, info, _repo, stream,
                            quota_day=spend.day)
        return JobAccepted(job_id=answer.job_id, status=answer.status)


def relabel_sources(answer: Answer) -> Answer:
    """Re-derive every source's tier at SERVE time, not just at write time.

    An answer stored last week was labelled against last week's whitelist,
    and the page re-serves stored answers on every reload of a #job= link.
    Dropping a domain from TRUSTED_DOMAINS has to reach history too, or
    curating the list is theatre. Returns the same object when nothing
    changed, so the common path allocates nothing.

    The ANSWER's label only ever goes down here. A stored "general web"
    answer may be one whose model said no fact-checker addressed the claim,
    and its prose says so; whitelisting a domain afterwards must not promote
    the label over words that contradict it. Each source chip is still
    re-tiered both ways — that is a fact about the domain, not a judgment.
    """
    if not answer.sources:
        return answer
    fixed = [
        s if s.tier == (t := "trusted" if is_trusted_url(s.url) else "web")
        else s.model_copy(update={"tier": t})
        for s in answer.sources
    ]
    if all(new is old for new, old in zip(fixed, answer.sources)):
        return answer
    computed = ("trusted" if any(s.tier == "trusted" for s in fixed)
                else "web" if fixed else "none")
    rank = {"none": 0, "web": 1, "trusted": 2}
    tier = min(answer.tier, computed, key=rank.__getitem__)
    return answer.model_copy(update={"sources": fixed, "tier": tier})


@router.get("/reports/{job_id}", response_model=Answer)
async def get_report(job_id: str) -> Answer:
    answer = await asyncio.to_thread(_repo.get, job_id)
    if answer is None:
        raise HTTPException(404, "Report not found.")
    return relabel_sources(answer)
