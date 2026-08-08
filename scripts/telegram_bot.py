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

_RATING_BADGE = {
    "TRUE": "✅ TRUE — sach hai",
    "MOSTLY_TRUE": "🟢 MOSTLY TRUE",
    "MISLEADING": "⚠️ MISLEADING — bhramak",
    "FALSE": "❌ FALSE — jhooth hai",
    "UNVERIFIED": "❓ UNVERIFIED — pushti nahi ho saki",
}

HELP = (
    "🔎 <b>Information Verifier</b>\n"
    "Bhejo:\n"
    "• koi bhi forwarded message (text)\n"
    "• Instagram Reel / YouTube Shorts / Facebook video ka link\n"
    "• voice note ya video\n"
    "• screenshot / photo\n\n"
    "Main trusted fact-checkers (AltNews, BOOM, PIB, Factly…) se check karke "
    "jawab dunga — aapki hi bhasha mein. Galat ho sakta hoon; diye गए sources "
    "khud padhiye."
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
    return html.escape(str(text or ""), quote=False)


def format_reply(report: dict) -> str:
    """One Telegram-HTML message from a Truth Report.

    Localized-first (the whole point of back-translation), English fallback
    per claim; citations stay in English — they are receipts, and a
    translated headline is unfindable on the source page. Never exceeds
    Telegram's length cap: whole claims are dropped from the end with a
    note, not truncated mid-sentence.
    """
    if report.get("status") == "FAILED":
        return ("😕 Check nahi ho paya: "
                f"{_e(report.get('error') or 'unknown error')}")

    loc = report.get("localized") or {}
    loc_claims = loc.get("claims") or []
    parts: list[str] = []

    overall = report.get("overall_rating")
    if overall:
        parts.append(f"<b>{_RATING_BADGE.get(overall, overall)}</b>")
    summary = loc.get("summary") or report.get("summary")
    if summary:
        parts.append(_e(summary))
    if report.get("source_text"):
        parts.append(f"<i>Humne yeh suna/padha:</i> {_e(report['source_text'][:500])}")

    claim_blocks: list[str] = []
    for i, cv in enumerate(report.get("claim_verdicts") or []):
        v = cv["verdict"]
        lc = loc_claims[i] if i < len(loc_claims) else None
        claim_text = (lc or {}).get("claim") or cv["claim"]["text"]
        reasoning = (lc or {}).get("reasoning") or v["reasoning"]
        block = [f"{i + 1}. “{_e(claim_text)}”",
                 f"{_RATING_BADGE.get(v['rating'], v['rating'])} ({v['confidence']}%)",
                 _e(reasoning)]
        correction = (lc or {}).get("correction") or v.get("correction")
        if correction:
            block.append(f"✔️ Sach yeh hai: {_e(correction)}")
        for c in v.get("citations") or []:
            block.append(f'📎 <a href="{_e(c["url"])}">{_e(c["publisher"])}: '
                         f'{_e(c["title"])}</a>')
        claim_blocks.append("\n".join(block))

    head = "\n\n".join(parts)
    reply = head
    shown = 0
    for block in claim_blocks:
        candidate = reply + "\n\n" + block
        if len(candidate) > _REPLY_BUDGET:
            break
        reply = candidate
        shown += 1
    if shown < len(claim_blocks):
        reply += (f"\n\n…aur {len(claim_blocks) - shown} claim(s) — "
                  "poora report web page par dekhiye.")
    return reply[:_TG_HARD_LIMIT] or "Koi checkable claim nahi mila."


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

    async def wait_for_report(self, job_id: str) -> dict | None:
        for _ in range(_POLL_MAX):
            resp = await self._http.get(f"{self._base}/reports/{job_id}")
            if resp.status_code == 200:
                report = resp.json()
                if report["status"] in ("COMPLETE", "FAILED"):
                    return report
            await asyncio.sleep(_POLL_S)
        return None


class TelegramClient:
    def __init__(self, http: httpx.AsyncClient, token: str):
        self._http = http
        self._api = f"https://api.telegram.org/bot{token}"
        self._files = f"https://api.telegram.org/file/bot{token}"

    async def get_updates(self, offset: int) -> list[dict]:
        resp = await self._http.get(
            f"{self._api}/getUpdates",
            params={"offset": offset, "timeout": 50},
            timeout=60.0,
        )
        resp.raise_for_status()
        return resp.json().get("result", [])

    async def send(self, chat_id: int, text: str) -> None:
        await self._http.post(f"{self._api}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        })

    async def file_bytes(self, file_id: str) -> tuple[bytes, str]:
        meta = await self._http.get(f"{self._api}/getFile",
                                    params={"file_id": file_id})
        meta.raise_for_status()
        path = meta.json()["result"]["file_path"]
        data = await self._http.get(f"{self._files}/{path}")
        data.raise_for_status()
        return data.content, path


async def handle_message(msg: dict, app: AppClient, tg: TelegramClient) -> None:
    """One message, end to end. Every failure becomes words in the chat."""
    chat_id = msg.get("chat", {}).get("id")
    if chat_id is None:
        return
    kind, payload = classify_message(msg)

    if kind == "help":
        await tg.send(chat_id, HELP)
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
        report = await app.wait_for_report(job_id)
        if report is None:
            await tg.send(chat_id, "⏳ Check abhi bhi chal raha hai — thodi der "
                                   "baad wahi message dobara bhej dena.")
            return
        await tg.send(chat_id, format_reply(report))
    except Exception as exc:  # noqa: BLE001 — a chat must always get an answer
        print(f"[bot] handling failed: {type(exc).__name__}: {exc}")
        await tg.send(chat_id, "😕 Kuch gadbad ho gayi. Thodi der baad try karo.")


async def main() -> None:
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
        try:
            await http.get(f"{APP_BASE}/../health")
        except httpx.HTTPError:
            print(f"The app is not reachable at {APP_BASE} — start it first:\n"
                  "  .venv\\Scripts\\python.exe -m uvicorn app.main:app")
            return

        print(">> Bot polling. Ctrl+C to stop. Checks cost real money.")
        offset = 0
        while True:
            try:
                updates = await tg.get_updates(offset)
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                print(f"[bot] getUpdates failed, retrying: {type(exc).__name__}")
                await asyncio.sleep(5)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("channel_post")
                if message:
                    # Sequential on purpose: one user at a time is the current
                    # scale, and it keeps the spend serialized.
                    await handle_message(message, app, tg)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nbot stopped.")
