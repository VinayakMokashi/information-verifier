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
import html
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx  # noqa: E402

from app.config import settings  # noqa: E402
from app.providers.links import allowed_link_host  # noqa: E402

APP_BASE = os.environ.get("APP_BASE", "http://127.0.0.1:8000/api/v1")

_POLL_S = 3.0
_POLL_MAX = 90            # ~4.5 min — link jobs download + transcribe first
_TG_HARD_LIMIT = 4096     # Telegram's message cap
_REPLY_BUDGET = 3900      # headroom under it for our own framing
_MAX_HEARD_CHARS = 1200   # of source_text inline; any cut is disclosed

_SOURCE_BUDGET = 900      # receipts get a reserved slice; the prose can't eat it
_MAX_PARA = 700           # a block must be small enough to be droppable

# The badge describes the EVIDENCE, not the truth — the verdict itself is in
# the prose, where it belongs. A tier that reads like a rating is how a reader
# ends up thinking "general web" meant "checked and fine".
_TIER_BADGE = {
    "trusted": "✅ Fact-checkers / official sources se check kiya",
    "web": "⚠️ Sirf aam web — kisi fact-checker ne ise cover nahi kiya",
    "none": "❓ Pushti nahi ho saki — koi bharosemand source nahi mila",
}

# Defence in depth for invariant 7. The engine strips its own sentinel; this
# also runs over rows written before a fix, where a leaked `<verdict …/>`
# would otherwise reach a reader.
_SENTINEL_RE = re.compile(r"<verdict\b[^>]*/?>", re.IGNORECASE)
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


def classify_message(msg: dict) -> tuple[str, str]:
    """(kind, payload) for one Telegram message. Pure — fully offline-testable.

    kinds: help | text | link | media | image | unsupported. The link test
    reuses the SERVER's own allowlist check, so the bot and the API can never
    disagree about what counts as a checkable link.
    """
    text = (msg.get("text") or "").strip()
    if text.startswith(("/start", "/help")):
        return "help", ""
    if text:
        if allowed_link_host(text) is not None:
            return "link", text
        return "text", text
    for key in ("voice", "audio", "video", "video_note"):
        if msg.get(key):
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
    for raw in _SENTINEL_RE.sub("", markdown).splitlines():
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
    pieces, current = [], ""
    for word in paragraph.split(" "):
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
        markdown = section.get("markdown") or ""
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

    remaining = _REPLY_BUDGET - len(verdict) - 2

    # Receipts first: bounded, and the only thing that lets a reader check us.
    # A long answer must not be able to push every source out of the message.
    sources, _ = _fit(_source_lines(answer), min(_SOURCE_BUDGET, remaining), sep="\n")
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
        room = min(_MAX_HEARD_CHARS, max(remaining - 80, 0))
        if room < 80:
            heard_block = ("<i>Humne jo suna/padha wo web page par hai — "
                           "yahan jagah nahi bachi.</i>")
        elif len(heard) > room:
            heard_block = (f"<i>Humne yeh suna/padha:</i> {_e(heard[:room])}"
                           f" […{len(heard) - room} aur characters — "
                           "poora text web page par]")
        else:
            heard_block = f"<i>Humne yeh suna/padha:</i> {_e(heard)}"

    reply = "\n\n".join(p for p in (heard_block, body, verdict, sources) if p)
    if len(reply) > _TG_HARD_LIMIT:
        # Unreachable via the budget above; if it ever happens, send something
        # valid rather than something Telegram will refuse outright.
        return ("Jawab bahut lamba hai — poora jawab web page par dekhiye. "
                f"({_e(_TIER_BADGE.get(tier, tier))})")
    return reply or "Is message mein check karne layak kuch nahi mila."


class AppClient:
    """The same two-call REST contract the web page uses."""

    def __init__(self, http: httpx.AsyncClient, base: str = APP_BASE):
        self._http = http
        self._base = base

    async def submit_json(self, endpoint: str, payload: dict) -> tuple[str | None, str]:
        """-> (job_id, "") on 202, (None, readable-detail) on rejection."""
        resp = await self._http.post(f"{self._base}/verify/{endpoint}", json=payload)
        if resp.status_code != 202:
            try:
                detail = resp.json().get("detail") or f"HTTP {resp.status_code}"
            except ValueError:
                detail = f"HTTP {resp.status_code}"
            return None, str(detail)
        return resp.json()["job_id"], ""

    async def submit_file(self, endpoint: str, filename: str, content: bytes,
                          content_type: str) -> tuple[str | None, str]:
        resp = await self._http.post(
            f"{self._base}/verify/{endpoint}",
            files={"file": (filename, content, content_type)},
        )
        if resp.status_code != 202:
            try:
                detail = resp.json().get("detail") or f"HTTP {resp.status_code}"
            except ValueError:
                detail = f"HTTP {resp.status_code}"
            return None, str(detail)
        return resp.json()["job_id"], ""

    async def wait_for_report(self, job_id: str, attempts: int | None = None) -> dict | None:
        """Poll until the report is done. Transient errors are survived.

        One blip used to raise out of this loop and abandon a job that had
        already been paid for — and the generic handler then told the user
        to resubmit, buying the whole check a second time. A network error
        here is never a reason to abandon money already spent.
        """
        for attempt in range(attempts if attempts is not None else _POLL_MAX):
            try:
                resp = await self._http.get(f"{self._base}/reports/{job_id}")
                if resp.status_code == 200:
                    report = resp.json()
                    if report["status"] in ("COMPLETE", "FAILED"):
                        return report
                elif resp.status_code == 404:
                    print(f"[bot] job {job_id} not found; giving up")
                    return None
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
        resp.raise_for_status()
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
        meta.raise_for_status()
        path = meta.json()["result"]["file_path"]
        data = await self._http.get(f"{self._files}/{path}")
        data.raise_for_status()
        return data.content, path


async def handle_message(
    msg: dict, app: AppClient, tg: TelegramClient,
    pending: dict[int, str] | None = None,
) -> None:
    """One message, end to end. Every failure becomes words in the chat.

    `pending` remembers a chat's in-flight job_id so a check that outran the
    poll window is RESUMED rather than resubmitted. Telling a user to
    "send it again" bought the whole check a second time — ASR, retrieval,
    adjudication — precisely for the slow, expensive jobs.
    """
    chat_id = msg.get("chat", {}).get("id")
    if chat_id is None:
        return
    pending = pending if pending is not None else {}
    kind, payload = classify_message(msg)

    if kind == "help":
        await tg.send(chat_id, HELP)
        return

    # A job already paid for comes first, whatever this message says.
    stale_job = pending.get(chat_id)
    if stale_job:
        report = await app.wait_for_report(stale_job, attempts=2)
        if report is not None:
            pending.pop(chat_id, None)
            await tg.send(chat_id, "Aapka pichla check pura hua:")
            await tg.send(chat_id, format_reply(report))
        else:
            await tg.send(chat_id, "⏳ Aapka pichla check abhi bhi chal raha hai. "
                                   "Wo pura hone ke baad naya bhejiye — "
                                   "warna dobara paisa lagega.")
        return

    if kind == "unsupported":
        await tg.send(chat_id, "Yeh message type abhi check nahi kar sakta — "
                               "text, link, voice note ya photo bhejiye.")
        return

    await tg.send(chat_id, "🔎 Checking… thoda time lagega (1–3 min).")
    try:
        if kind == "text":
            job_id, err = await app.submit_json("text", {"text": payload})
        elif kind == "link":
            job_id, err = await app.submit_json("link", {"url": payload})
        else:
            content, path = await tg.file_bytes(payload)
            name = os.path.basename(path) or "media.bin"
            if kind == "image":
                ext = os.path.splitext(name)[1].lower()
                ctype = "image/png" if ext == ".png" else "image/jpeg"
                job_id, err = await app.submit_file("image", name, content, ctype)
            else:
                job_id, err = await app.submit_file("media", name, content, "audio/ogg")
        if job_id is None:
            await tg.send(chat_id, f"😕 {_e(err)}")
            return
        # Remembered BEFORE the wait: if this process dies mid-poll, the job
        # is still recoverable on the next message instead of being re-bought.
        pending[chat_id] = job_id
        report = await app.wait_for_report(job_id)
        if report is None:
            await tg.send(chat_id, "⏳ Check abhi bhi chal raha hai. Mujhe koi "
                                   "bhi message bhejiye aur main wahi report "
                                   "dikha dunga — dobara paisa nahi lagega.")
            return
        pending.pop(chat_id, None)
        await tg.send(chat_id, format_reply(report))
    except Exception as exc:  # noqa: BLE001 — a chat must always get an answer
        print(f"[bot] handling failed: {type(exc).__name__}: {exc}")
        await tg.send(chat_id, "😕 Kuch gadbad ho gayi. Thodi der baad try karo.")


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

        try:
            await http.get(f"{APP_BASE}/../health")
        except httpx.HTTPError:
            print(f"The app is not reachable at {APP_BASE} - start it first:\n"
                  "  .venv\\Scripts\\python.exe -m uvicorn app.main:app")
            return

        print(">> Bot polling. Ctrl+C to stop. Checks cost real money.")
        offset = 0
        pending: dict[int, str] = {}   # chat_id -> in-flight job_id
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
                    # Sequential on purpose: one user at a time is the current
                    # scale, and it keeps the spend serialized.
                    await handle_message(message, app, tg, pending)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped.")
