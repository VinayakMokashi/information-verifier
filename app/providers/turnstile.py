"""Cloudflare Turnstile: is the browser behind this paid check a person? Free.

Decided 2026-10-15 (PROJECT_PLAN §7; docs/research/2026-10-15/limits-budget.md
L2 and L4): a paid check from a web visitor needs a Turnstile pass (managed
mode), verified here BEFORE any slot or money is claimed — a failed
verification never costs a slot — and only a pass earns the device cookie
that carries the visitor's 3-a-day allowance (app/api/device.py).

Free with unlimited verifications (Cloudflare's plans page, 2026-08-14). A
token is single-use and lives 300 s (server-side validation docs,
2026-09-16), so the page asks for a fresh one for every check.

Both keys unset means no challenge: this machine and development. Going live
they must be set — main.py warns at startup when a public name is configured
without them. Tests never reach Cloudflare: the suite runs with both unset
(tests/conftest.py), and the tests of this module hand in a MockTransport.
"""
import uuid

import httpx

from app.config import settings

_ENDPOINT = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TRANSPORT = None        # a seam: tests hand in an httpx.MockTransport
_MAX_TOKEN = 2048        # "The token can be up to 2048 characters" (the docs)
# Cloudflare refusing OUR side, not the visitor: a wrong or missing secret.
_OUR_FAULT = {"missing-input-secret", "invalid-input-secret"}


def enabled() -> bool:
    return bool(settings.turnstile_secret_key and settings.turnstile_site_key)


async def verify(token: str | None, remoteip: str | None) -> bool | None:
    """True: Cloudflare says a person passed. False: it says no — a missing,
    expired, reused or forged token. None: it could not be asked, or refused
    OUR key; the caller refuses rather than wave a visitor through, and the
    visitor can simply try again."""
    if not token or len(token) > _MAX_TOKEN:
        return False
    form = {"secret": settings.turnstile_secret_key, "response": token,
            "idempotency_key": str(uuid.uuid4())}
    if remoteip:
        form["remoteip"] = remoteip
    try:
        async with httpx.AsyncClient(timeout=10, transport=_TRANSPORT) as client:
            # The secret travels in the BODY, never in a URL: a URL is what an
            # httpx error and httpx's own INFO log line print (review R8).
            resp = await client.post(_ENDPOINT, data=form)
        resp.raise_for_status()
        outcome = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        print(f"[turnstile] could not verify: {type(exc).__name__}")
        return None
    if outcome.get("success") is True:
        return True
    codes = {str(c) for c in outcome.get("error-codes") or []}
    if codes & _OUR_FAULT:
        print(f"[turnstile] Cloudflare refused OUR secret ({', '.join(sorted(codes))}): "
              "check TURNSTILE_SECRET_KEY in .env")
        return None
    return False
