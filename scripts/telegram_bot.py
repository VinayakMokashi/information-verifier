"""Telegram bot — check a forward without leaving the chat. Phase 3 delivery.

Telegram over WhatsApp, deliberately (PROJECT_PLAN §6): long polling needs NO
tunnel and no webhook, and going live takes one @BotFather token in .env —
against WhatsApp's Meta business verification, webhook re-pasting on every
restart, and 5-recipient test cap. Everything here except `getUpdates` reuses
the same two REST calls as the web page, which is the point of the
surface-agnostic contract; a WhatsApp bot later swaps the transport and keeps
`format_reply` unchanged.

Run (the app must be serving on APP_BASE):
    .venv\\Scripts\\python.exe -m uvicorn app.main:app          # terminal 1
    .venv\\Scripts\\python.exe scripts\\telegram_bot.py          # terminal 2

Costs whatever the checks cost — Telegram itself is free. No token → prints
setup instructions and exits at $0.
"""
import asyncio
import contextlib
import html
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.api.limits import SUBJECT_HEADER  # noqa: E402
from app.config import settings  # noqa: E402
from app.engine.marker import strip_any_sentinel  # noqa: E402
from app.engine.triage import nothing_to_check  # noqa: E402
from app.providers.links import allowed_link_host  # noqa: E402

APP_BASE = os.environ.get("APP_BASE", "http://127.0.0.1:8000/api/v1")


def subject_of_message(msg: dict) -> str:
    """Whom a check is for, as the API counts people (limits.subject_of).

    Every submission reaches the API from this one connection, so without a
    name every Telegram user was one person to the limiter (reproduced
    2026-10-15). The sender's user id; a channel post has none, so its chat
    is the person. The API honours this only from this machine.
    """
    # An anonymous group admin, or someone posting "as a channel", arrives
    # with `from` set to ONE shared placeholder account (1087968824,
    # 136817688) and the real sender in `sender_chat` — so `from` made them
    # all one person, able to use up one allowance for all (review R13).
    on_behalf_of = (msg.get("sender_chat") or {}).get("id")
    if on_behalf_of is not None:
        return f"tgchat:{on_behalf_of}"
    sender = (msg.get("from") or {}).get("id")
    if sender is not None:
        return f"tg:{sender}"
    return f"tgchat:{(msg.get('chat') or {}).get('id')}"

_POLL_S = 3.0
_POLL_MAX = 90            # ~4.5 min — link jobs download + transcribe first
_TG_HARD_LIMIT = 4096     # Telegram's message cap
_REPLY_BUDGET = 3900      # headroom under it for our own framing
_MAX_HEARD_CHARS = 1200   # of source_text inline; any cut is disclosed

_SOURCE_BUDGET = 900      # receipts get a reserved slice; the prose can't eat it
_SUMMARY_BUDGET = 500     # so does the summary: it is what a skimmer reads
_MAX_PARA = 700           # a block must be small enough to be droppable

# The badge describes the EVIDENCE, not the truth — the verdict itself is in
# the prose, where it belongs. A tier that reads like a rating is how a reader
# ends up thinking "general web" meant "checked and fine".
_TIER_BADGE = {
    "trusted": "✅ Fact-checkers / official sources se check kiya",
    "web": "⚠️ Sirf aam web — kisi fact-checker ne ise cover nahi kiya",
    "none": "❓ Pushti nahi ho saki — koi bharosemand source nahi mila",
}

_MD_LINK_RE = re.compile(r"\[([^\]]*)\]\((?:[^)\s]+)\)")
_URL_RE = re.compile(r"\bhttps?://\S+", re.IGNORECASE)
_BULLET_RE = re.compile(r"^(?:[-*]|\d+[.)])\s+(.*)$")

HELP = (
    "🔎 <b>Information Verifier</b>\n"
    "Bhejo:\n"
    "• koi bhi forwarded message (text) — kisi bhi bhasha mein\n"
    "• Instagram Reel / YouTube Shorts / Facebook video ka link\n"
    "• voice note ya video\n"
    "• screenshot / photo\n\n"
    "Main fact-checkers (AltNews, BOOM, PIB, Factly, Snopes, Full Fact…) aur "
    "official sources (WHO, NASA, NIH, government sites…) se check karke "
    "jawab dunga — aapki hi bhasha mein. Sirf India ya politics nahi: "
    "health, science, history, kuch bhi.\n\n"
    "Galat ho sakta hoon; diye gaye sources khud padhiye."
)


# The Bot API hands a bot files up to 20 MB (getFile); bigger ones are
# refused with "file is too big" whatever the app's own upload cap says.
_TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024


def classify_message(msg: dict) -> tuple[str, str]:
    """(kind, payload) for one Telegram message. Pure — fully offline-testable.

    kinds: help | smalltalk | text | link | media | image | too_big |
    unsupported. The
    link test reuses the SERVER's own allowlist check, and the small-talk test
    the server's own triage, so the bot and the API can never disagree about
    what counts as a checkable link or as nothing to check.
    """
    text = (msg.get("text") or "").strip()
    if text.startswith(("/start", "/help")):
        return "help", ""
    # (A voice note or photo has no text at all: guard the split.)
    if text.startswith("/") and text.split(maxsplit=1)[0].split("@")[0].lower() == "/id":
        # Anyone's own chat id — how the owner finds the OWNER_CHAT_ID that
        # the app's alerts go to (app/providers/alerts.py).
        return "id", ""
    if text:
        if allowed_link_host(text) is not None:
            return "link", text
        if nothing_to_check(text):
            return "smalltalk", text
        return "text", text
    for key in ("voice", "audio", "video", "video_note"):
        if msg.get(key):
            # Telegram refuses getFile over this, every time — so saying
            # "try again later" after the download fails can never come true.
            if (msg[key].get("file_size") or 0) > _TG_DOWNLOAD_LIMIT:
                return "too_big", ""
            return "media", msg[key].get("file_id", "")
    if msg.get("photo"):
        # Telegram sends multiple sizes; the last is the largest.
        return "image", msg["photo"][-1].get("file_id", "")
    return "unsupported", ""


def _e(text) -> str:
    """Escape for Telegram HTML — INCLUDING quotes.

    quote=False was wrong: this output also lands inside href="…", and a
    citation URL is adjudicator output whose path/query nothing validates
    (the trust filter checks the HOST). One double quote there closes the
    attribute early, Telegram rejects the whole message with "can't parse
    entities", and the reader gets silence after a paid check.
    """
    return html.escape(str(text or ""), quote=True)


def _clip_escaped(text: str, room: int) -> tuple[str, int]:
    """Escape `text` so the RESULT fits in `room`. -> (escaped, chars dropped).

    MEASURED: escaping expands — one `&` becomes `&amp;`. A caption of 4,000
    ampersands measured as 4,000 characters and arrived as 20,000, blowing
    Telegram's hard limit, so the reply degraded to "Jawab bahut lamba hai" and
    an answer that had already been paid for was thrown away.

    Cutting the ESCAPED string instead would be worse: a cut inside `&amp;` is
    exactly the broken entity Telegram rejects outright. So cut the RAW text,
    then shrink until its escaped form fits. Worst case is a 5x expansion, so
    the proportional step converges in a couple of iterations.
    """
    keep = min(len(text), room)
    while keep > 0:
        escaped = _e(text[:keep])
        if len(escaped) <= room:
            return escaped, len(text) - keep
        shrunk = keep * room // len(escaped)
        keep = shrunk if shrunk < keep else keep - 1
    return "", len(text)


def _https(url: str) -> bool:
    """Only ever emit an href whose scheme a reader can trust on sight."""
    return url.lower().startswith(("https://", "http://"))


def _md_to_tg(markdown: str) -> str:
    """One markdown paragraph -> Telegram HTML. Escape FIRST, then promote.

    Escaping before promoting is what makes this safe: by the time any tag is
    inserted, every `<` in the model's own prose is already `&lt;`, so the
    only tags in the output are the ones this function put there.
    """
    lines: list[str] = []
    # Defence in depth for invariant 7 — also covers rows written before a fix.
    for raw in strip_any_sentinel(markdown).splitlines():
        line = raw.strip()
        if not line:
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            line = "• " + bullet.group(1)
        line = re.sub(r"^#{1,6}\s+", "", line)
        # Invariant 3: prose is never a receipt. Telegram auto-links bare URLs
        # in message text, so a URL the MODEL wrote would arrive tappable and
        # indistinguishable from the vetted ones below. Strip both forms; the
        # real receipts are the Sources block, built from API citations.
        line = _MD_LINK_RE.sub(r"\1", line)
        line = _URL_RE.sub("[link neeche Sources mein]", line)
        line = _e(line)
        line = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", line)
        line = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"<i>\1</i>", line)
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        lines.append(line)
    return "\n".join(lines)


def _soften(paragraph: str) -> list[str]:
    """Break an over-long markdown paragraph at word boundaries.

    MEASURED: a single unbroken 15,000-char paragraph fit in no budget at all,
    so the whole answer was dropped and the reader got a 95%-confident badge
    with a source link and NOTHING ELSE — the exact failure this project
    exists to prevent. Blocks must be droppable, so they must be bounded.

    Splitting before conversion can land inside `**bold**`; the halves then
    simply fail to match and render as literal asterisks. Slightly ugly, and
    structurally safe — the right trade for a pathological input.
    """
    if len(paragraph) <= _MAX_PARA:
        return [paragraph]
    pieces: list[str] = []
    current = ""
    for word in paragraph.split(" "):
        # A word can itself be longer than the budget — CJK and Thai do not
        # separate words with spaces, and one enormous token has the same
        # shape. Breaking only on spaces left those as a single undroppable
        # block, which is how the whole answer disappeared again.
        while len(word) > _MAX_PARA:
            if current:
                pieces.append(current)
                current = ""
            pieces.append(word[:_MAX_PARA])
            word = word[_MAX_PARA:]
        if not word:
            continue
        if current and len(current) + 1 + len(word) > _MAX_PARA:
            pieces.append(current)
            current = word
        else:
            current = f"{current} {word}" if current else word
    if current:
        pieces.append(current)
    return pieces


def _answer_paragraphs(answer: dict) -> list[str]:
    """The prose as independently well-formed HTML paragraphs.

    Paragraph-at-a-time conversion is what lets the length budget below stay
    safe: a cut lands BETWEEN paragraphs, so it can never land inside a tag or
    an &entity;. The old code sliced finished HTML, and a cut inside a tag made
    Telegram reject the whole message — silence after a paid check.
    """
    out: list[str] = []
    seen_web = False
    for section in answer.get("sections") or []:
        # Strip any leaked verdict tag from the WHOLE section first: the
        # per-piece strip below runs after the text is split into paragraphs
        # and ≤700-char pieces, so a tag longer than a piece lost only its
        # first fragment and the rest reached the chat (found by review, on a
        # row stored before the engine stopped leaking them).
        markdown = strip_any_sentinel(section.get("markdown") or "")
        if not markdown.strip():
            continue
        if section.get("tier") == "web" and not seen_web:
            seen_web = True
            out.append("<i>— Yahan tak fact-checkers ne kuch nahi kaha. "
                       "Neeche sirf aam web se: —</i>")
        for para in markdown.split("\n\n"):
            for piece in _soften(para):
                rendered = _md_to_tg(piece)
                if rendered.strip():
                    out.append(rendered)
    return out


def _source_lines(answer: dict) -> list[str]:
    lines: list[str] = []
    sources = answer.get("sources") or []
    for tier, heading in (("trusted", "📎 <b>Sources</b>"),
                          ("web", "🌐 <b>Aam web (fact-checkers nahi)</b>")):
        group = [s for s in sources if (s.get("tier") or "web") == tier]
        if not group:
            continue
        lines.append(heading)
        for s in group:
            url = str(s.get("url") or "")
            if not _https(url):
                continue
            publisher = s.get("publisher") or ""
            title = s.get("title") or ""
            label = (f"{publisher}: {title}" if publisher and title
                     else (publisher or title or url))
            if len(label) > 90:
                label = label[:87] + "…"
            lines.append(f'<a href="{_e(url)}">{_e(label)}</a>')
    return lines


def _fit(blocks: list[str], limit: int, sep: str = "\n\n") -> tuple[str, int]:
    """Take whole blocks from the front while they fit. -> (text, n_dropped)."""
    kept: list[str] = []
    used = 0
    for i, block in enumerate(blocks):
        cost = len(block) + (len(sep) if kept else 0)
        if used + cost > limit:
            return sep.join(kept), len(blocks) - i
        kept.append(block)
        used += cost
    return sep.join(kept), 0


def format_reply(answer: dict) -> str:
    """One Telegram-HTML message from an Answer.

    The prose IS the answer, so it gets most of the budget; the evidence badge
    and the receipts are reserved out of it first, because they are short and
    because a verdict with no receipts is the failure mode this whole project
    exists to avoid. Nothing is sliced mid-string — whole blocks are dropped
    and every drop is disclosed.
    """
    if answer.get("status") == "FAILED":
        return ("😕 Check nahi ho paya: "
                f"{_e(answer.get('error') or 'unknown error')}")

    tier = answer.get("tier") or "none"
    verdict = f"<b>{_TIER_BADGE.get(tier, _TIER_BADGE['none'])}</b>"
    confidence = answer.get("confidence")
    if isinstance(confidence, int):
        verdict += f"\n<b>{confidence}% confident</b>"
    else:
        # Confidence is always shown WITH its basis, and "not stated" is a
        # real value — inventing a number would be worse than the blank.
        verdict += "\n<i>Confidence stated nahi hui</i>"
    if answer.get("cached"):
        verdict += "  <i>(pehle check kiya hua — is baar kharch $0)</i>"
    if answer.get("truncated"):
        verdict += "\n<i>Jawab lamba tha, beech mein kat gaya — poora web page par.</i>"

    # The two lines a skimmer reads. Reserved BEFORE the prose, like the
    # receipts: it is the one part a reader who reads nothing else will read,
    # so the length budget must never be able to drop it. A blockquote is the
    # closest Telegram has to the page's highlighted box.
    summary = ""
    raw_summary = " ".join(str(answer.get("summary") or "").split())
    if raw_summary:
        shown, _ = _clip_escaped(raw_summary, _SUMMARY_BUDGET)
        summary = f"<blockquote>📌 <b>In short</b>\n{shown}</blockquote>"

    remaining = _REPLY_BUDGET - len(verdict) - len(summary) - 4

    # Receipts first: bounded, and the only thing that lets a reader check us.
    # A long answer must not be able to push every source out of the message.
    sources, _ = _fit(_source_lines(answer), min(_SOURCE_BUDGET, remaining), sep="\n")
    # A heading the budget cut everything off of tells the reader we found
    # general-web sources and then shows none of them.
    kept = sources.splitlines()
    while kept and not kept[-1].startswith("<a href="):
        kept.pop()
    sources = "\n".join(kept)
    if sources:
        remaining -= len(sources) + 2

    body, dropped = _fit(_answer_paragraphs(answer), max(remaining - 120, 0))
    if dropped:
        body += f"\n\n…aur {dropped} paragraph — poora jawab web page par."
    if body:
        remaining -= len(body) + 2

    heard_block = ""
    if answer.get("source_text"):
        # Invariant 4: machine-read text is SHOWN BACK, because a mis-hear
        # silently becomes a confident answer about words the sender never
        # said. Any shortening is disclosed — a hard slice once hid most of a
        # measured 599-char caption with no marker at all.
        heard = " ".join(str(answer["source_text"]).split())
        room = min(_MAX_HEARD_CHARS, max(remaining - 120, 0))
        if room < 80:
            heard_block = ("<i>Humne jo suna/padha wo web page par hai — "
                           "yahan jagah nahi bachi.</i>")
        else:
            shown, dropped_chars = _clip_escaped(heard, room)
            heard_block = f"<i>Humne yeh suna/padha:</i> {shown}"
            if dropped_chars:
                heard_block += (f" […{dropped_chars} aur characters — "
                                "poora text web page par]")

    reply = "\n\n".join(p for p in (heard_block, body, verdict, summary, sources)
                        if p)
    if len(reply) > _TG_HARD_LIMIT:
        # Unreachable via the budget above; if it ever happens, send something
        # valid rather than something Telegram will refuse outright.
        return ("Jawab bahut lamba hai — poora jawab web page par dekhiye. "
                f"({_e(_TIER_BADGE.get(tier, tier))})")
    return reply or "Is message mein check karne layak kuch nahi mila."


def _server_trouble(status: int) -> str:
    """What a chat reads when the API refused without saying why.

    "HTTP 500" used to be sent straight into the chat. The code is logged;
    the person is told what to do.
    """
    print(f"[bot] API answered {status} with no detail")
    if status >= 500:
        return "Server par kuch gadbad hai — thodi der baad dobara bhejiye."
    return "Yeh bheja nahi ja saka — thodi der baad dobara try kariye."


class JobGone(Exception):
    """The API has no such job (404) — deleted after the retention period, or
    the app is now pointed at another database. Never "still running"."""


# How long a submission may take to be ACCEPTED. The API does real work
# before its 202 — a link is resolved (bounded server-side at 60 s), a
# screenshot is read by a paid vision call — and a bot that gives up first
# tells the person to try again while the server creates, and bills, a job
# whose answer nobody will ever deliver (traced by review; the bot's timeout
# was 30 s, and a Facebook reel's resolve measured 14 s).
_SUBMIT_TIMEOUT = httpx.Timeout(30.0, read=300.0)


class AppClient:
    """The same two-call REST contract the web page uses."""

    def __init__(self, http: httpx.AsyncClient, base: str = APP_BASE):
        self._http = http
        self._base = base

    @staticmethod
    def _for(subject: str | None) -> dict:
        return {SUBJECT_HEADER: subject} if subject else {}

    async def submit_json(self, endpoint: str, payload: dict,
                          subject: str | None = None) -> tuple[str | None, str]:
        """-> (job_id, "") on 202, (None, readable-detail) on rejection."""
        resp = await self._http.post(f"{self._base}/verify/{endpoint}", json=payload,
                                     headers=self._for(subject), timeout=_SUBMIT_TIMEOUT)
        if resp.status_code != 202:
            try:
                detail = resp.json().get("detail") or _server_trouble(resp.status_code)
            except ValueError:
                detail = _server_trouble(resp.status_code)
            return None, str(detail)
        return resp.json()["job_id"], ""

    async def submit_file(self, endpoint: str, filename: str, content: bytes,
                          content_type: str,
                          subject: str | None = None) -> tuple[str | None, str]:
        resp = await self._http.post(
            f"{self._base}/verify/{endpoint}",
            files={"file": (filename, content, content_type)},
            headers=self._for(subject),
            timeout=_SUBMIT_TIMEOUT,
        )
        if resp.status_code != 202:
            try:
                detail = resp.json().get("detail") or _server_trouble(resp.status_code)
            except ValueError:
                detail = _server_trouble(resp.status_code)
            return None, str(detail)
        return resp.json()["job_id"], ""

    async def wait_for_report(self, job_id: str, attempts: int | None = None) -> dict | None:
        """Poll until the report is done. Transient errors are survived.

        One blip used to raise out of this loop and abandon a job that had
        already been paid for — and the generic handler then told the user
        to resubmit, buying the whole check a second time. A network error
        here is never a reason to abandon money already spent.

        -> the report, or None if it is still running when the attempts run
        out. A 404 raises JobGone: it used to return None as well, and since
        answers are deleted after 30 days that is a normal outcome — a chat
        whose remembered job had been deleted was told "still running" on
        every message until the bot restarted (found by review, reproduced).
        """
        for attempt in range(attempts if attempts is not None else _POLL_MAX):
            try:
                resp = await self._http.get(f"{self._base}/reports/{job_id}")
                if resp.status_code == 200:
                    report = resp.json()
                    if report["status"] in ("COMPLETE", "FAILED"):
                        return report
                elif resp.status_code == 404:
                    raise JobGone(job_id)
            except (httpx.HTTPError, ValueError) as exc:
                print(f"[bot] poll blip, retrying: {type(exc).__name__}: {exc}")
            if attempt + 1 < (attempts if attempts is not None else _POLL_MAX):
                await asyncio.sleep(_POLL_S)
        return None


# Measured 2026-07-28 from this machine: getMe timed out twice before
# succeeding on the third try. Telegram is reachable but intermittently slow
# here, so every call to it retries — a bot that gives up on the first
# timeout drops the reply to a check the user already paid for.
_TG_ATTEMPTS = 3
_TG_BACKOFF_S = 3.0


async def _tg_retry(what: str, call):
    """Run a Telegram call with retries. Returns None if every attempt fails."""
    for attempt in range(1, _TG_ATTEMPTS + 1):
        try:
            return await call()
        except (httpx.HTTPError, asyncio.TimeoutError) as exc:
            print(f"[bot] {what} attempt {attempt}/{_TG_ATTEMPTS}: "
                  f"{type(exc).__name__}")
            if attempt < _TG_ATTEMPTS:
                await asyncio.sleep(_TG_BACKOFF_S)
    return None


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient, token: str):
        self._http = http
        self._api = f"https://api.telegram.org/bot{token}"
        self._files = f"https://api.telegram.org/file/bot{token}"

    @staticmethod
    def _check(resp: httpx.Response, method: str) -> None:
        """raise_for_status(), minus the URL.

        Every Bot API URL carries the token, and an httpx status error's text
        IS its URL. MEASURED 2026-10-15: a voice note over Telegram's 20 MB
        getFile limit made the submit catch-all print the token. Raised
        directly, not re-raised, so no chained original can show it either;
        still an httpx.HTTPStatusError, because the poll loop retries on that.
        """
        if resp.is_success:
            return
        try:
            body = resp.json()
        except ValueError:
            body = None
        why = body.get("description") if isinstance(body, dict) else None
        raise httpx.HTTPStatusError(
            f"Telegram {method} answered HTTP {resp.status_code}"
            + (f": {str(why)[:200]}" if why else ""),
            request=resp.request, response=resp)

    async def get_updates(self, offset: int, confirm_only: bool = False) -> list[dict]:
        """Long-poll for updates. `confirm_only` acknowledges `offset` and
        returns immediately — used to mark a batch handled BEFORE the paid
        work starts, so a crash cannot cause a redelivery that re-bills."""
        resp = await self._http.get(
            f"{self._api}/getUpdates",
            params={"offset": offset, "timeout": 0 if confirm_only else 50,
                    **({"limit": 1} if confirm_only else {})},
            timeout=30.0 if confirm_only else 60.0,
        )
        self._check(resp, "getUpdates")
        return resp.json().get("result", [])

    async def send(self, chat_id: int, text: str) -> bool:
        """Send, and NOTICE if Telegram refused.

        The response used to be discarded, so a rejected reply — a broken
        entity, an over-long message, a blocked bot — completed 'fine' and
        the reader got silence after a paid check, with nothing logged.
        On a parse-mode rejection we retry once as plain text: the verdict
        matters more than its formatting.
        """
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML",
                   "disable_web_page_preview": True}
        resp = await _tg_retry(
            "sendMessage",
            lambda: self._http.post(f"{self._api}/sendMessage", json=payload))
        if resp is not None and resp.status_code == 200:
            return True
        if resp is not None:
            print(f"[bot] sendMessage rejected ({resp.status_code}): {resp.text[:200]}")

        # A rejection is usually our HTML, not the network — resend the same
        # words with no markup rather than leaving a paid check unanswered.
        plain = html.unescape(re.sub(r"<[^>]+>", "", text))[:_TG_HARD_LIMIT]
        retry = await _tg_retry(
            "sendMessage(plain)",
            lambda: self._http.post(f"{self._api}/sendMessage", json={
                "chat_id": chat_id, "text": plain,
                "disable_web_page_preview": True,
            }))
        if retry is not None and retry.status_code == 200:
            print("[bot] recovered: sent as plain text")
            return True
        if retry is not None:
            print(f"[bot] plain-text retry also rejected: {retry.text[:200]}")
        return False

    async def file_bytes(self, file_id: str) -> tuple[bytes, str]:
        meta = await self._http.get(f"{self._api}/getFile",
                                    params={"file_id": file_id})
        self._check(meta, "getFile")
        path = meta.json()["result"]["file_path"]
        data = await self._http.get(f"{self._files}/{path}")
        self._check(data, "file download")
        return data.content, path


async def _submit(kind: str, payload: str, app: AppClient,
                  tg: TelegramClient, subject: str | None = None) -> tuple[str | None, str]:
    """Send one message's content to the API, for `subject` (the sender).
    -> (job_id, "") or (None, why)."""
    if kind == "text":
        return await app.submit_json("text", {"text": payload}, subject=subject)
    if kind == "link":
        return await app.submit_json("link", {"url": payload}, subject=subject)
    content, path = await tg.file_bytes(payload)
    name = os.path.basename(path) or "media.bin"
    if kind == "image":
        ext = os.path.splitext(name)[1].lower()
        ctype = "image/png" if ext == ".png" else "image/jpeg"
        return await app.submit_file("image", name, content, ctype, subject=subject)
    return await app.submit_file("media", name, content, "audio/ogg", subject=subject)


_NOT_CHECKED = ("ℹ️ Yeh naya message check nahi hua, kyunki pichla check chal "
                "raha tha. Ise check karwana ho to ab dobara bhejiye.")
_SMALLTALK_REPLY = ("🙂 Kuch check karwana ho to woh message, link, voice note "
                    "ya photo yahan bhejiye.")
_TOO_BIG_REPLY = ("📦 Yeh file 20 MB se badi hai — Telegram bots itni badi file "
                  "download nahi kar sakte. Chhota clip (5 minute tak) bhejiye, "
                  "ya video ka link.")
# Kinds that are never submitted, so never told "this was not checked".
_NEVER_CHECKED = ("unsupported", "smalltalk", "too_big")
# Said when a wait gives up while the check still runs; the person's next
# message, whatever it is, collects the answer.
_STILL_RUNNING = ("⏳ Check abhi bhi chal raha hai. Mujhe koi bhi message bhejiye "
                  "aur main wahi report dikha dunga — dobara paisa nahi lagega. "
                  "(Wo message khud check nahi hoga — use baad mein dobara bhejiyega.)")
_DONE_EARLIER = "Aapka pichla check pura hua:"


class PendingStore(dict):
    """`pending` (chat id -> the job it waits for), written through to a file.

    REPRODUCED (docs/research/2026-10-15/audit-ops.md OPS-07; the review's
    R12): kept only in memory, every check in flight was forgotten when the
    bot restarted — its window closed, a reboot. The check still completed
    and was billed, and no reply was ever sent. Dispatcher.resume delivers
    what a previous run was waiting for.

    A job id opens the person's message (OPS-11), so nothing is kept longer
    than it could still be delivered: an entry goes on delivery, and any
    older than a day is dropped on load. Written whole, to a temporary file
    swapped in, so a crash mid-write leaves the old file, never half of one.
    The bot uses only get, item assignment, `in` and pop — those write.
    """

    _TTL_S = 24 * 3600

    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path
        self._at: dict[int, float] = {}
        try:
            with open(path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        now = time.time()
        for chat, entry in (saved.items() if isinstance(saved, dict) else ()):
            try:
                chat_id, job_id, at = int(chat), str(entry["job"]), float(entry["at"])
            except (KeyError, TypeError, ValueError):
                continue
            if now - at < self._TTL_S:
                super().__setitem__(chat_id, job_id)
                self._at[chat_id] = at
        self._write()

    def __setitem__(self, chat_id, job_id) -> None:
        super().__setitem__(chat_id, job_id)
        self._at[chat_id] = time.time()
        self._write()

    def __delitem__(self, chat_id) -> None:
        super().__delitem__(chat_id)
        self._at.pop(chat_id, None)
        self._write()

    def pop(self, chat_id, *default):
        had = chat_id in self
        value = super().pop(chat_id, *default)
        if had:
            self._at.pop(chat_id, None)
            self._write()
        return value

    def _write(self) -> None:
        data = {str(chat): {"job": job, "at": self._at.get(chat, time.time())}
                for chat, job in self.items()}
        temporary = f"{self._path}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(temporary, self._path)
        except OSError as exc:
            print(f"[bot] could not save the pending checks: {type(exc).__name__}")


def pending_path() -> str:
    """Beside the app's database: the same .env says where both live."""
    return os.path.join(os.path.dirname(os.path.abspath(settings.db_path)),
                        "bot_pending.json")


async def handle_message(
    msg: dict, app: AppClient, tg: TelegramClient,
    pending: dict[int, str] | None = None,
    locks: dict[int, asyncio.Lock] | None = None,
    *, slots: asyncio.Semaphore | None = None,
    prompted: set[int] | None = None,
    busy_on_arrival: bool = False,
) -> None:
    """One message, end to end. Every failure becomes words in the chat.

    `pending` remembers a chat's undelivered job_id so a check that outran the
    poll window is RESUMED rather than resubmitted. Telling a user to
    "send it again" bought the whole check a second time — ASR, retrieval,
    adjudication — precisely for the slow, expensive jobs.

    Messages run concurrently (see Dispatcher), which opens a way to pay
    twice: two messages from ONE chat arriving together would both see no
    pending job and both submit. So everything that decides whether to spend
    — reading `pending`, submitting, recording the job — runs under a
    per-chat lock, and only the long wait happens outside it.

    A message that arrives while the chat's previous check is undelivered is
    NEVER checked automatically — at 2 checks a day, an impatient "kya hua?"
    would spend half the day. It either hands over the finished answer or is
    told, in words, to send again. Found by review, reproduced: it used to be
    swallowed silently when the first handler delivered while it peeked.
    `prompted` tells a poke from a new message: a chat is in it once its
    wait gave up and ASKED for "any message", and leaves when that message
    arrives. An earlier version asked instead whether the first handler was
    still waiting — unreliable, because the wait also ends when someone else
    delivers the report, and the next message's own words were then dropped
    in silence (found by a 2,000-interleaving search of the fixed bot).
    `busy_on_arrival` comes from the Dispatcher, decided when the message
    ARRIVED: a second poke that queued behind the first one's lock would
    otherwise find the answer already delivered, look like a fresh start,
    and be paid for (found by review of the concurrency fix).
    """
    chat_id = msg.get("chat", {}).get("id")
    if chat_id is None:
        return
    pending = pending if pending is not None else {}
    locks = locks if locks is not None else {}
    prompted = prompted if prompted is not None else set()
    kind, payload = classify_message(msg)

    if kind == "help":           # instant — it never waits behind anyone's check
        await tg.send(chat_id, HELP)
        return
    if kind == "id":             # instant too: nothing to check, nothing spent
        await tg.send(chat_id, f"Your chat id: {chat_id}")
        return

    # Lock BEFORE slot: a message queued behind its own chat must not hold
    # one of the bot's slots while it waits (found by review: one chat
    # re-sending could hold every slot and starve all the others).
    async with locks.setdefault(chat_id, asyncio.Lock()), \
            (slots if slots is not None else contextlib.nullcontext()):
        # A job already paid for comes first, whatever this message says.
        stale_job = pending.get(chat_id)
        if stale_job:
            gone = False
            try:
                report = await app.wait_for_report(stale_job, attempts=2)
            except JobGone:
                report, gone = None, True
            # Re-read after the await: the first message's own wait may have
            # delivered it meanwhile — then there is nothing to hand over, and
            # this message still arrived during a check.
            if pending.get(chat_id) != stale_job:
                if kind not in _NEVER_CHECKED:
                    await tg.send(chat_id, _NOT_CHECKED)
                return
            if gone:
                # Deleted after the retention period: the old answer is lost,
                # and this is plainly a new message, not a poke for it.
                pending.pop(chat_id, None)
                print(f"[bot] job {stale_job} no longer exists; "
                      "checking the new message instead")
            elif report is None:
                await tg.send(chat_id, "⏳ Aapka pichla check abhi bhi chal raha hai. "
                                       "Wo pura hone ke baad naya bhejiye — "
                                       "warna dobara paisa lagega.")
                return
            else:
                pending.pop(chat_id, None)
                await tg.send(chat_id, _DONE_EARLIER)
                await tg.send(chat_id, format_reply(report))
                # Its wait had asked for "any message": this was that poke.
                # Otherwise the person sent something new mid-check — say so.
                was_poke = chat_id in prompted
                prompted.discard(chat_id)
                if not was_poke and kind not in _NEVER_CHECKED:
                    await tg.send(chat_id, _NOT_CHECKED)
                return
        elif busy_on_arrival and kind not in _NEVER_CHECKED:
            # Its check was delivered while this message waited for the lock.
            # It still arrived mid-check, so it is not checked automatically.
            await tg.send(chat_id, _NOT_CHECKED)
            return

        if kind == "unsupported":
            await tg.send(chat_id, "Yeh message type abhi check nahi kar sakta — "
                                   "text, link, voice note ya photo bhejiye.")
            return
        if kind == "too_big":
            await tg.send(chat_id, _TOO_BIG_REPLY)
            return
        if kind == "smalltalk":
            # "hi", "ok", "thanks": nothing to check, so nothing is spent and
            # no daily slot is used (it used to buy a full check). It did
            # still go through the pending-report logic above, because "ok"
            # is exactly what people send when told "send any message".
            await tg.send(chat_id, _SMALLTALK_REPLY)
            return

        await tg.send(chat_id, "🔎 Checking… thoda time lagega (1–3 min).")
        try:
            job_id, err = await _submit(kind, payload, app, tg, subject_of_message(msg))
        except Exception as exc:  # noqa: BLE001 — a chat must always get an answer
            print(f"[bot] submit failed: {type(exc).__name__}: {exc}")
            await tg.send(chat_id, "😕 Kuch gadbad ho gayi. Thodi der baad try karo.")
            return
        if job_id is None:
            await tg.send(chat_id, f"😕 {_e(err)}")
            return
        # Remembered BEFORE the wait: if this process dies mid-poll, the job
        # is still recoverable on the next message instead of being re-bought.
        pending[chat_id] = job_id
        prompted.discard(chat_id)   # a fresh check, not a poke

    # The long wait, outside the lock AND the slot: this chat's next message
    # must be able to say "still running" instead of queueing silently for
    # minutes, and a report that takes minutes must not hold a slot.
    try:
        try:
            report = await app.wait_for_report(job_id)
        except JobGone:
            if pending.get(chat_id) == job_id:
                pending.pop(chat_id, None)
            print(f"[bot] job {job_id} vanished right after it was accepted")
            await tg.send(chat_id, "😕 Kuch gadbad ho gayi. Thodi der baad try karo.")
            return
        if report is None:
            # Says outright that the poke itself is not checked: a new claim
            # sent in answer to this was consumed as the poke, in silence.
            prompted.add(chat_id)          # the next message IS the poke
            await tg.send(chat_id, _STILL_RUNNING)
            return
        if pending.get(chat_id) != job_id:
            return        # a later message from this chat already delivered it
        pending.pop(chat_id, None)
        await tg.send(chat_id, format_reply(report))
    except Exception as exc:  # noqa: BLE001 — a chat must always get an answer
        print(f"[bot] handling failed: {type(exc).__name__}: {exc}")
        await tg.send(chat_id, "😕 Kuch gadbad ho gayi. Thodi der baad try karo.")


class Dispatcher:
    """Every incoming message on its own task, so no chat waits on another.

    The bot used to handle messages one at a time: one person's 4-minute
    reel check blocked every other chat, /help included. Serializing was also
    how it kept spend in line — no longer needed, because the API's daily cap
    is now persisted and atomic (2 a day, 2026-09-22), and the per-chat lock
    in handle_message stops one chat paying twice.

    `max_in_flight` bounds the handlers deciding and submitting at once (a
    voice note is downloaded and re-uploaded then). A message queued behind
    its own chat's lock holds no slot, the minutes-long wait for a report
    holds none, and /help skips the bound entirely.
    """

    def __init__(self, app: AppClient, tg: TelegramClient, max_in_flight: int = 16,
                 pending_path: str | None = None):
        self.app, self.tg = app, tg
        # Persisted when given a path (the bot itself — OPS-07); tests that
        # do not care keep the plain in-memory dict.
        self.pending: dict[int, str] = (PendingStore(pending_path) if pending_path
                                        else {})
        self.locks: dict[int, asyncio.Lock] = {}
        self.prompted: set[int] = set()   # chats asked for "any message"
        self.in_flight: dict[int, int] = {}      # handlers per chat, right now
        self._slots = asyncio.Semaphore(max_in_flight)
        self._tasks: set[asyncio.Task] = set()

    def dispatch(self, message: dict) -> None:
        # Whether the chat was busy is decided HERE, as the message arrives.
        # Deciding it after the per-chat lock lets a poke that queued behind
        # another one find the answer already delivered, look like a fresh
        # start, and be paid for (found by review). Busy means an undelivered
        # job OR an earlier message of this chat still being handled: a burst
        # arrives before the first handler has even submitted, so `pending`
        # alone left the third message of three looking like a fresh start
        # (found by a 2,000-interleaving search, seed 120).
        chat_id = (message.get("chat") or {}).get("id")
        counted = chat_id is not None and classify_message(message)[0] != "help"
        busy = chat_id is not None and (chat_id in self.pending
                                        or self.in_flight.get(chat_id, 0) > 0)
        if counted:
            self.in_flight[chat_id] = self.in_flight.get(chat_id, 0) + 1
        task = asyncio.create_task(
            self._run(message, busy, chat_id if counted else None))
        self._tasks.add(task)                    # keep a reference until done
        task.add_done_callback(self._tasks.discard)

    async def _run(self, message: dict, busy: bool = False,
                   counted_chat: int | None = None) -> None:
        try:
            await handle_message(message, self.app, self.tg, self.pending,
                                 self.locks, slots=self._slots,
                                 prompted=self.prompted, busy_on_arrival=busy)
        except Exception as exc:  # noqa: BLE001 — one message must not kill the bot
            print(f"[bot] task failed: {type(exc).__name__}: {exc}")
        finally:
            if counted_chat is not None:
                left = self.in_flight.get(counted_chat, 1) - 1
                if left > 0:
                    self.in_flight[counted_chat] = left
                else:
                    self.in_flight.pop(counted_chat, None)

    async def resume(self) -> None:
        """Deliver what a previous run of the bot was waiting for (OPS-07).
        Each on its own task, like any message; the chat counts as busy
        meanwhile (its entry is in `pending`), so a message it sends is
        never checked on top of it."""
        for chat_id, job_id in list(self.pending.items()):
            task = asyncio.create_task(self._deliver_late(chat_id, job_id))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _deliver_late(self, chat_id: int, job_id: str) -> None:
        try:
            try:
                report = await self.app.wait_for_report(job_id)
            except JobGone:
                # Deleted after the retention period: nothing left to deliver.
                if self.pending.get(chat_id) == job_id:
                    self.pending.pop(chat_id, None)
                return
            if self.pending.get(chat_id) != job_id:
                return            # the person's own message collected it meanwhile
            if report is None:
                self.prompted.add(chat_id)       # the next message IS the poke
                await self.tg.send(chat_id, _STILL_RUNNING)
                return
            self.pending.pop(chat_id, None)
            await self.tg.send(chat_id, _DONE_EARLIER)
            await self.tg.send(chat_id, format_reply(report))
        except Exception as exc:  # noqa: BLE001 — one chat must not stop the rest
            print(f"[bot] delivering a check after a restart failed: "
                  f"{type(exc).__name__}: {exc}")

    async def drain(self) -> None:
        """Wait for everything in flight (tests; a graceful shutdown).

        The sleep(0) is load-bearing. A finished task leaves `_tasks` in its
        done-callback, which runs on the NEXT loop turn — and on 3.12 gather()
        over tasks that are all already done completes without yielding at
        all. A drain() called just as the last task finished therefore spun
        forever, blocking the loop (measured: a new test did exactly that).
        """
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
            await asyncio.sleep(0)


def _utf8_console() -> None:
    """A long-running bot must not die of a console encoding error.

    It logs whatever Telegram sends back, which can carry Devanagari; on a
    Windows console that falls back to the ANSI code page (cp1252 here) and
    printing it raises UnicodeEncodeError — killing the process mid-poll.
    Same hazard scripts/render.py::print_report exists for.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


async def check_token(http: httpx.AsyncClient, token: str) -> tuple[bool, str]:
    """Validate the bot token with getMe. FREE — no message, no check, $0."""
    resp = await _tg_retry(
        "getMe",
        lambda: http.get(f"https://api.telegram.org/bot{token}/getMe", timeout=45.0))
    if resp is None:
        return False, "could not reach Telegram after retries"
    if resp.status_code != 200:
        return False, f"Telegram rejected the token (HTTP {resp.status_code})"
    me = resp.json().get("result") or {}
    return True, f"@{me.get('username', '?')} ({me.get('first_name', '')})"


async def app_status(http: httpx.AsyncClient, base: str = APP_BASE) -> str:
    """"ready", "demo", "not ready" or "unreachable", from OUR app's /ready.

    /ready lives at the site root, not under the API prefix. MEASURED
    2026-09-29: `{base}/../health` resolved to /api/health, a 404, and passed
    anyway because any response counted as "up" — so did whatever else might
    have been listening on the port: only our app's own answer counts. And
    the FREE demo server answers too, with simulated verdicts (audit-ops
    OPS-18, PROJECT_PLAN §11 19): it says "demo", and the bot refuses it.
    """
    root = base.rstrip("/").removesuffix("/api/v1")
    try:
        resp = await http.get(f"{root}/ready")
        body = resp.json()
    except (httpx.HTTPError, ValueError, AttributeError):
        return "unreachable"
    if not isinstance(body, dict) or body.get("status") not in ("ready", "not ready"):
        return "unreachable"                     # some other server answered
    if body.get("mode") == "demo":
        return "demo"
    return "ready" if resp.status_code == 200 and body["status"] == "ready" else "not ready"


async def app_is_up(http: httpx.AsyncClient, base: str = APP_BASE) -> bool:
    return await app_status(http, base) == "ready"


async def main() -> None:
    _utf8_console()
    if not settings.telegram_bot_token:
        print("No TELEGRAM_BOT_TOKEN in .env — nothing was started ($0).\n"
              "To create one (2 minutes):\n"
              "  1. In Telegram, message @BotFather -> /newbot -> pick a name.\n"
              "  2. Put the token in .env as TELEGRAM_BOT_TOKEN=...\n"
              "  3. Start the app, then run this script again.")
        return

    async with httpx.AsyncClient(timeout=30.0) as http:
        app = AppClient(http)
        tg = TelegramClient(http, settings.telegram_bot_token)

        ok, detail = await check_token(http, settings.telegram_bot_token)
        print(f">> Token: {'OK — ' + detail if ok else 'FAILED — ' + detail}")
        if not ok:
            return
        if "--check-token" in sys.argv:
            print(">> --check-token: nothing started, nothing spent.")
            return

        status = await app_status(http)
        if status == "demo":
            print(f"The app at {APP_BASE} is the FREE DEMO server - its answers are "
                  "simulated, and the bot would send them to people as real. Start "
                  "the real app instead (start.cmd).")
            return
        if status == "unreachable":
            print(f"The app is not reachable at {APP_BASE} - start it first:\n"
                  "  .venv\\Scripts\\python.exe -m uvicorn app.main:app")
            return
        if status == "not ready":
            print(">> WARNING: the app says it is NOT READY (see its /ready: the "
                  "database, its keys or ffmpeg). Checks may fail until that is fixed.")

        print(">> Bot polling. Ctrl+C to stop. Checks cost real money.")
        offset = 0
        dispatcher = Dispatcher(app, tg, pending_path=pending_path())
        if dispatcher.pending:
            print(f">> Resuming {len(dispatcher.pending)} check(s) a previous run "
                  "was waiting for.")
        await dispatcher.resume()
        while True:
            try:
                updates = await tg.get_updates(offset)
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                print(f"[bot] getUpdates failed, retrying: {type(exc).__name__}")
                await asyncio.sleep(5)
                continue
            if not updates:
                continue

            # CONFIRM THE BATCH BEFORE DOING PAID WORK. Telegram redelivers
            # anything not acknowledged by a later offset, and handling takes
            # minutes — so a crash or Ctrl+C mid-check used to redeliver the
            # same voice note on restart and pay for the whole transcription
            # again. Of the two failure modes, losing a message the user can
            # resend deliberately beats silently re-billing them.
            offset = updates[-1]["update_id"] + 1
            try:
                await tg.get_updates(offset, confirm_only=True)
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                print(f"[bot] offset confirm failed: {type(exc).__name__}")

            for update in updates:
                message = update.get("message") or update.get("channel_post")
                if message:
                    # Concurrent: one chat's long check no longer blocks the
                    # others. Spend stays bounded by the API's daily cap and
                    # the per-chat lock (see Dispatcher / handle_message).
                    dispatcher.dispatch(message)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped.")
