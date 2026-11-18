"""HTTP endpoints — surface-agnostic.

A verify request creates the job row, returns a job_id immediately, and runs
the check as a BackgroundTask (a check takes tens of seconds).
Clients poll GET /reports/{job_id}. A web PWA and a WhatsApp webhook consume
the exact same two-call contract.
"""
import asyncio
import contextlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import (APIRouter, BackgroundTasks, File, Form, HTTPException,
                     Request, Response, UploadFile)

from app.api import device
from app.api.local import is_this_machine
from app.api.limits import (admit, attempt, claim, fund_async, give_back, give_back_day,
                            give_back_person, pause, paused, release, reserve_usd,
                            settle, subject_of)
from app.api.schemas import JobAccepted, VerifyLinkRequest, VerifyTextRequest
from app.config import settings
from app.api import stream as job_stream
from app.engine.job import cache_key, run_check
from app.engine.triage import nothing_to_check
from app.models.answer import Answer, JobStatus
from app.providers.asr import get_asr_provider
from app.providers.llm import PAUSED_MESSAGE, paused_reason, tell_owner_paused
from app.providers.links import (
    SUPPORTED_LINKS_MSG, LinkError, LinkInfo, allowed_link_host,
    download_link_audio, fetch_post_image, log_safe, resolve_link, subtitle_text,
)
from app.providers import alerts, turnstile
from app.providers.media import MediaError, MediaTooLong, normalize_to_wav, split_wav
from app.providers.usage import UsageMeter
from app.providers.vision import ocr_images
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
_MSG_NOTHING_TO_CHECK = ("That looks like a greeting, not something to check. "
                         "Paste or forward the message, link or claim you "
                         "want checked.")
# ffmpeg sniffs the real container, so the type gate is deliberately loose —
# browsers label voice notes inconsistently (audio/ogg, application/ogg, …).
_ALLOWED_MEDIA_PREFIXES = ("audio/", "video/")
_ALLOWED_MEDIA_TYPES = {"application/ogg", "application/octet-stream"}


class _Spend:
    """Whether this request has already cost money, and which day it counted.

    `day` is the daily-cap day the slot was charged to (None when rate
    limiting is off), carried to the background job, which settles it when
    the check ends (`_finish`). `subject` is whose check this is
    (limits.subject_of), released then so that person's next check may
    start. `kind` and `mode` (what the day's budget still buys —
    limits.budget_mode) decide what was reserved of the day's dollar budget,
    and the engine is told the mode.
    """

    __slots__ = ("started", "day", "subject", "kind", "mode", "_request", "token")

    def __init__(self, day: str | None = None, subject: str | None = None,
                 kind: str = "text", mode: str = "full", request=None,
                 token: str | None = None) -> None:
        self.started = False
        self.day = day
        self.subject = subject
        self.kind = kind
        self.mode = mode
        self._request = request
        self.token = token                # this claim's own in-flight entry

    def release(self) -> None:
        """This person's check is over: exactly this claim's place in line
        goes (limits.release by token) — safe to call more than once."""
        release(self.subject, self.token)

    async def fund(self) -> None:
        """A deferred claim's money: the day's slot, the person's allowance
        and the budget — call right BEFORE the first paid step, once the free
        part (a link's resolve, an upload's decode) has succeeded."""
        if self.subject is None:          # rate limiting is off
            return
        self.day, self.mode = await fund_async(self._request, self.subject, self.kind)

    def begin(self) -> None:
        """Call immediately BEFORE the first paid call of the request."""
        self.started = True


# How often a running job's bill so far is saved onto its row (_checkpoint):
# a few small writes per check, only when the bill has grown.
_CHECKPOINT_EVERY_S = 5.0


# A web visitor proves a person is asking (decided 2026-10-15): the page sends
# a fresh Cloudflare Turnstile token with every paid check.
TURNSTILE_HEADER = "x-turnstile-token"
_NOT_A_PERSON = ("We couldn't confirm you're a person. Please try again — and if "
                 "it keeps failing, open this page in Chrome.")
_COULD_NOT_CONFIRM = ("We couldn't confirm you're a person just now. Please try "
                      "again in a minute.")


async def _person(request: Request, response: Response | None) -> str:
    """Whose check this is — and, for a web visitor while Turnstile is on,
    proof first that a person is asking, verified BEFORE any slot, money or
    place in line is taken: a failed check costs nothing. A pass from a
    device without a cookie earns one, and this check already counts
    against it. The bot and this machine are not web visitors."""
    subject = subject_of(request)
    if not turnstile.enabled() or is_this_machine(request):
        return subject
    remote = request.client.host if request.client else None
    human = await turnstile.verify(request.headers.get(TURNSTILE_HEADER), remote)
    if human is None:                 # Cloudflare could not be asked: never a pass
        raise HTTPException(503, _COULD_NOT_CONFIRM)
    if not human:
        raise HTTPException(403, _NOT_A_PERSON)
    if subject.startswith("dev:") or response is None:
        return subject
    device_id, cookie = device.mint()
    response.set_cookie(device.COOKIE, cookie, max_age=device.MAX_AGE_S,
                        path="/api/v1", secure=True, httponly=True, samesite="strict")
    return f"dev:{device_id}"


@router.get("/client-config", include_in_schema=False)
async def client_config() -> dict:
    """What the page must know before a check: the Turnstile SITE key, which
    is public by design (the widget shows it), or null while Turnstile is
    off. Never the secret."""
    return {"turnstile_site_key": settings.turnstile_site_key if turnstile.enabled() else None}


@asynccontextmanager
async def _quota(request: Request, kind: str, *, deferred: bool = False,
                 response: Response | None = None):
    """Claim a check up front; hand it back only if we never spent anything.

    Reserving first is what makes the cap real — checking now and consuming
    after an upload has been read leaves a window where any number of
    concurrent requests pass the same empty counter.

    Both the claim and the refund are SQLite writes, so both run on the
    limiter's own small pool (`limits.claim`). Two review rounds, measured:
    on the event loop, a claim waiting for another writer's lock froze every
    request and every live stream; in asyncio's shared pool, a burst of
    claims filled it and reading a finished answer stalled 30 s behind them.

    The `started` flag is load-bearing, not bookkeeping: /verify/image raises
    422 ("no text in this image") AFTER a paid Opus vision call, and refunding
    that rejection handed the slot back — a loop of blank images could burn
    budget all day with the daily counter reading zero. A refund is only
    honest when nothing was bought. (The media ASR spend that used to share
    this trap now runs behind the 202, where no refund path exists at all.)
    """
    if paused():
        # Anthropic is refusing for money: this check would only fail after
        # reserving and waiting (limits.pause). A cached repeat is still
        # served free — the text route looks for one before it gets here.
        raise HTTPException(503, PAUSED_MESSAGE)
    subject = await _person(request, response)
    token = uuid.uuid4().hex
    if deferred:
        # Free but slow work comes first (review R1, 2026-10-15): hold only
        # the person's place in line until the route calls spend.fund().
        admitted = admit(request, subject, token)
        spend = _Spend(None, subject if admitted else None, kind, "full",
                       request, token)
    else:
        day, mode = await claim(request, subject, kind, token)
        spend = _Spend(day, subject if day else None, kind, mode, request, token)
    try:
        yield spend
    except BaseException:
        # ANY failure that bought nothing hands the slot back, not only an
        # HTTPException: found by review, a database error inside the route —
        # or a request cancelled at shutdown — burned half the day's budget
        # with no job row and nothing in the log. Shielded so a cancellation
        # still lets the refund finish; over-counting is the safe direction
        # if it does not. After paid work (the image route's OCR), the slot
        # and the reservation stay: the real cost is not known here.
        try:
            if not spend.started and spend.day is not None:
                await asyncio.shield(give_back(request, spend.day, spend.kind,
                                               spend.mode, spend.subject))
        finally:
            # No background check exists to release this person later: it
            # ends here. In a finally: a SECOND cancellation landing on the
            # shielded refund skipped it, and the person was "in flight" for
            # the TTL (found by review, reproduced 2026-10-16).
            spend.release()
        raise


_FAILURES_TO_ALERT = 3
_failures = [0]            # checks failed in a row, in this process


def _count_outcome(status: str, error: str) -> None:
    """A run of failed checks is the error storm the owner must hear about
    (audit-ops OPS-19: a revoked key or a Sarvam outage fails every check,
    and only the app window said so). One success resets the count."""
    if status != "FAILED":
        _failures[0] = 0
        return
    _failures[0] += 1
    if _failures[0] == _FAILURES_TO_ALERT:
        alerts.notify("failing", f"{_FAILURES_TO_ALERT} checks in a row failed. "
                                 f"The last said: {error[:200]}")


async def _finish(job_id: str, repo, quota: _Spend | None) -> None:
    """A background check has ended, however it ended: settle its day.

    Its reservation becomes what it really cost: a COMPLETE check's bill, or
    a failed one's when that is MORE than was reserved. Otherwise a failure
    keeps its reservation — a stream that died mid-answer may have been
    billed without its usage ever being recorded, and the budget exists for
    exactly the cases nobody measured.

    A CLEAN free cache hit also hands back the day's slot and the person's
    daily check: with a cap of 2 a day (2026-09-22) a forward someone sent
    twice spent half the day on an answer served for $0. Deliberately narrow
    — anything that paid for OCR or a transcript keeps them.

    The person is released FIRST — the engine already did, just before the
    answer became visible (review R6); this is the backstop for the paths
    that never reached it, and releasing the same claim twice does nothing.
    """
    if quota is None:
        return
    quota.release()
    try:
        answer = await asyncio.to_thread(repo.get, job_id)
        # Refused for MONEY (chat.ServicePaused): what it cost is exactly what
        # was recorded — "failed requests aren't charged" — and every check
        # after it fails the same way until someone pays. Before 2026-10-16
        # each one kept its reservation, so a handful drained the day's $1.
        refused = answer is not None and answer.error == PAUSED_MESSAGE
        if refused:
            pause()                 # (the owner was told when it was detected)
        elif answer is not None:
            _count_outcome(answer.status.value, answer.error or "")
        if quota.day is not None:
            usage = answer.usage if answer is not None else None
            actual = None
            reserved = reserve_usd(quota.kind, quota.mode)
            if usage is not None and (answer.status is JobStatus.COMPLETE or refused
                                      or usage.estimated_usd > reserved):
                actual = usage.estimated_usd
            await settle(quota.day, quota.kind, actual, quota.mode)
            if answer is not None and (answer.cached or refused) and actual == 0:
                await give_back_day(quota.day)
                give_back_person(quota.subject, quota.day)
    except Exception as exc:  # noqa: BLE001 — settling must never cost the answer
        print(f"[quota] settling failed: {type(exc).__name__}: {exc}")


def _engine_kwargs(quota: _Spend | None) -> dict:
    """What run_check needs from a claim: the budget mode, and the hook that
    releases the person just before their answer becomes visible."""
    if quota is None:
        return {"mode": "full"}
    return {"mode": quota.mode, "on_finished": quota.release}


async def _checkpoint(job_id: str, repo, meter: UsageMeter) -> None:
    """Every few seconds while a job runs, its bill so far onto its row —
    whenever it has grown. REPRODUCED (audit-ops OPS-04): a check killed
    mid-flight (a closed window, a crash, a reboot; a redeploy on a host)
    restarted as FAILED with usage=None, and the passes, searches and
    transcription it had bought never reached the ledger, the spend truth.
    The sweeps that fail such a row now write its ledger row from this."""
    last = None
    while True:
        await asyncio.sleep(_CHECKPOINT_EVERY_S)
        usage = meter.snapshot()
        if usage.estimated_usd > 0 and usage.model_dump() != last:
            if await safe_cache_call(repo.record_progress, job_id, usage):
                last = usage.model_dump()


@asynccontextmanager
async def _checkpointing(job_id: str, repo, meter: UsageMeter):
    task = asyncio.create_task(_checkpoint(job_id, repo, meter))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def _run_check_job(job_id: str, text: str, repo, stream=None, *,
                         quota: _Spend | None = None, **check) -> None:
    """The background job of /verify/text and /verify/image: the check, then
    its day settled (`_finish`), however the check ended."""
    for key, value in _engine_kwargs(quota).items():
        check.setdefault(key, value)
    meter = check.setdefault("meter", UsageMeter())
    try:
        async with _checkpointing(job_id, repo, meter):
            await run_check(job_id, text, repo, stream, **check)
    finally:
        await _finish(job_id, repo, quota)


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
    quota: _Spend | None = None, language: str | None = None,
) -> None:
    """The background job of /verify/media. Whatever ends it — an answer, a
    transcription failure, a crash — settles its day (`_finish`)."""
    try:
        async with _checkpointing(job_id, repo, meter):
            await _media_job(job_id, wav, duration, repo, meter, stream, language=language,
                             **_engine_kwargs(quota))
    finally:
        await _finish(job_id, repo, quota)


async def _media_job(
    job_id: str, wav: bytes, duration: float, repo, meter: UsageMeter, stream=None,
    language: str | None = None, mode: str = "full", on_finished=None,
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
    await run_check(job_id, text, repo, stream, derived_text=text, meter=meter,
                    kind="media", language=language, mode=mode,
                    on_finished=on_finished)


@router.post("/verify/text", response_model=JobAccepted, status_code=202)
async def verify_text(
    req: VerifyTextRequest, background: BackgroundTasks, request: Request,
    response: Response,
) -> JobAccepted:
    # The length first: it is O(1), and the triage below is not — it walks
    # every character on the event loop (2026-10-15: a 25 MB "message" froze
    # the server; the body cap in main.py now bounds what reaches here).
    if len(req.text) > settings.max_input_chars:
        raise HTTPException(
            413,
            f"That message is {len(req.text)} characters; the limit is "
            f"{settings.max_input_chars}. Send the part you want checked.",
        )
    # Before the slot is even claimed: "hi" used to buy a full check and use
    # up one of the day's capped slots (measured 2026-10-10).
    if nothing_to_check(req.text):
        raise HTTPException(422, _MSG_NOTHING_TO_CHECK)
    # Repeats stay free (Vinayak's $1-a-day decision, 2026-10-15; audit-ops
    # OPS-15): an answer already in the cache costs nothing, so it is served
    # with no slot and no reservation — even when the day's budget or this
    # person's allowance is spent. cache_only makes the job FAIL, not pay, if
    # the entry expires in the instant between here and there.
    if await safe_cache_call(_repo.cache.get, cache_key(req.text, req.language)):
        # Free of money, not of the abuse guard (review R14): every repeat
        # makes a job row and a live stream, so it is this hour's attempt.
        attempt(request, subject_of(request))
        answer, stream = await _new_job(req.text)
        background.add_task(_run_check_job, answer.job_id, req.text, _repo, stream,
                            language=req.language, cache_only=True)
        return JobAccepted(job_id=answer.job_id, status=answer.status)
    async with _quota(request, "text", response=response) as spend:
        answer, stream = await _new_job(req.text)
        background.add_task(_run_check_job, answer.job_id, req.text, _repo, stream,
                            quota=spend, language=req.language)
        return JobAccepted(job_id=answer.job_id, status=answer.status)


@router.post("/verify/image", response_model=JobAccepted, status_code=202)
async def verify_image(
    background: BackgroundTasks, request: Request, response: Response,
    file: UploadFile = File(...), language: str | None = Form(None, max_length=40),
) -> JobAccepted:
    async with _quota(request, "image", response=response) as spend:
        if file.content_type not in _ALLOWED_IMAGE_TYPES:
            raise HTTPException(415, _MSG_NOT_AN_IMAGE)
        image_bytes = await file.read()
        # OCR is quick; do it inline so extracted text is captured even if the
        # check itself runs in the background.
        spend.begin()          # everything past here has been paid for
        meter = UsageMeter()   # starts at the first paid call, so the report's
        with meter.activate():  # the bill includes route-level OCR, not just the check
            try:
                extracted = await ocr_images([(image_bytes, file.content_type)])
            except Exception as exc:
                reason = paused_reason(exc)
                if not reason:
                    raise
                # Refused for MONEY: nothing was charged after all ("failed
                # requests aren't charged"), so _quota gives it all back.
                tell_owner_paused(reason)
                spend.started = False
                pause()
                raise HTTPException(503, PAUSED_MESSAGE) from exc
        if not extracted:
            raise HTTPException(422, "No text or visual claim could be read from the image.")

        answer, stream = await _new_job(extracted)
        background.add_task(_run_check_job, answer.job_id, extracted, _repo, stream,
                            quota=spend, derived_text=extracted, meter=meter,
                            kind="image", language=language)
        return JobAccepted(job_id=answer.job_id, status=answer.status)


@router.post("/verify/media", response_model=JobAccepted, status_code=202)
async def verify_media(
    background: BackgroundTasks, request: Request, response: Response,
    file: UploadFile = File(...), language: str | None = Form(None, max_length=40),
) -> JobAccepted:
    # `spend.begin()` is never called: since the Sarvam loop moved behind the
    # 202, this route spends nothing before returning, so every rejection here
    # is honestly refundable. `spend` is bound only to carry the day.
    async with _quota(request, "media", deferred=True, response=response) as spend:
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
        # Funded only now: the decode above was free (review R1).
        await spend.fund()
        answer, stream = await _new_job()
        background.add_task(_run_media_job, answer.job_id, wav, duration, _repo,
                            meter, stream, quota=spend, language=language)
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
    """Everything readable from the post: caption + (subtitles | audio->ASR),
    or, for a post of pictures, caption + what its pictures say (one vision
    call).

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

    seen = await _read_pictures(info) if info.images else None

    combined = "\n\n".join(t for t in (caption, spoken, seen) if t and t.strip())
    if not combined.strip():
        raise LinkError("other", "No speech or text could be read from that post.")
    return combined


# Said with the text when a picture could not be fetched. Also how _link_job
# knows not to remember the text: a read that missed a picture is retried
# next time, never kept for 30 days (invariant 6).
_PICTURES_MISSED = "[Some of the post's pictures could not be fetched.]"


async def _read_pictures(info: LinkInfo) -> str:
    """A photo post's pictures -> what they say: ONE paid vision call.

    Bounded before it is made (invariant 5): at most max_images_per_check
    pictures, each byte-capped as it is fetched. What was not read is said
    in the text the reader is shown, and the model sees it too.
    """
    wanted = info.images[: settings.max_images_per_check]
    # Side by side, kept in the post's order: one after another, a carousel's
    # fetches added up in front of the person waiting.
    outcomes = await asyncio.gather(
        *(asyncio.to_thread(fetch_post_image, url, settings.max_image_bytes)
          for url in wanted),
        return_exceptions=True)
    fetched = []
    for outcome in outcomes:
        if isinstance(outcome, BaseException):
            print(f"[link] a picture could not be fetched: "
                  f"{getattr(outcome, 'kind', type(outcome).__name__)}")
        else:
            fetched.append(outcome)
    if not fetched:
        raise LinkError("network", "That post's pictures could not be fetched. Try "
                                   "again in a minute, or send a screenshot instead.")
    notes = []
    if len(info.images) > len(wanted):
        notes.append(f"[This post has {len(info.images)} pictures; only the first "
                     f"{len(wanted)} were read.]")
    if len(fetched) < len(wanted):
        notes.append(_PICTURES_MISSED)
    if info.videos_skipped:
        noun = "video" if info.videos_skipped == 1 else "videos"
        notes.append(f"[This post also has {info.videos_skipped} {noun}; "
                     "they were not listened to.]")
    read = await ocr_images(fetched)
    return "\n".join([read, *notes])


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
    print(f"[link] unexpected failure: {type(exc).__name__}: {log_safe(exc)}")
    return "Something went wrong reading that link. Please try again."


def transcript_key(info: LinkInfo) -> str | None:
    """The transcript cache key: the platform's own id, known for free.

    Versioned, so a change to how link text is gathered (the caption cap, the
    subtitle choice) can retire every entry at once. None when the platform
    gave no id — an unkeyable post is simply not cached.

    v2 since 2026-09-22: v1 entries could be a caption alone, stored when the
    transcription heard nothing. That rule changed, and old entries would
    have gone on serving it for their 30 days (found by review).
    """
    if not info.video_id or not info.platform:
        return None
    return f"v2:{info.platform.lower()}:{info.video_id}"


async def _run_link_job(job_id: str, info: LinkInfo, repo, stream=None,
                        quota: _Spend | None = None,
                        language: str | None = None) -> None:
    """The background job of /verify/link; settles its day (`_finish`)
    however it ends."""
    meter = UsageMeter()   # here, so the transcription it pays for is checkpointed
    try:
        async with _checkpointing(job_id, repo, meter):
            await _link_job(job_id, info, repo, stream, language=language,
                            meter=meter, **_engine_kwargs(quota))
    finally:
        await _finish(job_id, repo, quota)


async def _link_job(job_id: str, info: LinkInfo, repo, stream=None,
                    language: str | None = None, mode: str = "full",
                    on_finished=None, meter: UsageMeter | None = None) -> None:
    """Background half: fetch the text (or its cached transcript), then check it.

    A failure here becomes a FAILED report with a readable error (the page
    renders those), never a silent PROCESSING-forever. run_check guards
    itself; this guard covers the fetch/ASR work before it.
    """
    meter = meter or UsageMeter()
    key = transcript_key(info)
    # A cache failure degrades to doing the work (invariant 6), never to a
    # failed check — so the lookup and the store both go through
    # safe_cache_call.
    text = await safe_cache_call(repo.transcripts.get, key) if key else None
    if text:
        # The platform, never the key: it carries the post's id (audit OPS-11).
        print(f"[link] transcript cache hit ({info.platform}): no download, no ASR")
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
        # again; re-hearing a music-only reel costs its ASR, a few paise. A
        # post read with a picture missing is retried the same way.
        if (key and text.strip() != _caption_text(info).strip()
                and _PICTURES_MISSED not in text):
            await safe_cache_call(repo.transcripts.put, key, text)
    await run_check(job_id, text, repo, stream, derived_text=text, meter=meter,
                    kind="link", language=language, mode=mode,
                    on_finished=on_finished)


@router.post("/verify/link", response_model=JobAccepted, status_code=202)
async def verify_link(
    req: VerifyLinkRequest, background: BackgroundTasks, request: Request,
    response: Response,
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
    async with _quota(request, "link", deferred=True, response=response) as spend:
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
        if not info.has_media and not info.images and not info.caption.strip():
            raise HTTPException(422, "That post has no video, picture or caption to check.")

        # Funded only now, once the free resolve has succeeded: REPRODUCED
        # (review R1), five people's slow, refused resolves held every slot.
        await spend.fund()
        answer, stream = await _new_job(url)
        background.add_task(_run_link_job, answer.job_id, info, _repo, stream,
                            quota=spend, language=req.language)
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
