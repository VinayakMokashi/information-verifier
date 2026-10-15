"""On the web, a person is a DEVICE: a signed cookie, earned by a Turnstile pass.

Decided 2026-10-15 (PROJECT_PLAN §7): 3 paid checks a day per web device, by
a cookie issued only after a Cloudflare Turnstile pass
(app/providers/turnstile.py; routes._quota issues it). limits.subject_of
names a request carrying a valid one `dev:<id>`.

The cookie is a random id and its HMAC — nothing about the visitor, and
nothing of it is written to disk. The key is made fresh at every start: the
per-person counts it keys live in memory and reset on a restart anyway
(limits._person_today), so a key that outlived restarts would buy nothing and
be one more secret to keep. After a restart the next pass simply issues a new
cookie. Like every per-person key it is resettable (clear cookies, solve
Turnstile again); the day's dollar budget remains the hard bound.
"""
import base64
import hashlib
import hmac
import re
import secrets

from starlette.requests import Request

COOKIE = "vd"
MAX_AGE_S = 365 * 24 * 3600
_KEY = secrets.token_bytes(32)
_SHAPE = re.compile(r"([A-Za-z0-9_-]{22})\.([A-Za-z0-9_-]{22})")


def _mac(device_id: str) -> str:
    digest = hmac.new(_KEY, b"device:" + device_id.encode("ascii"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest[:16]).decode("ascii").rstrip("=")


def mint() -> tuple[str, str]:
    """A new device: -> (its id, the cookie value that proves it)."""
    device_id = secrets.token_urlsafe(16)          # 22 characters
    return device_id, f"{device_id}.{_mac(device_id)}"


def verified(value: str) -> str | None:
    """The device id a cookie value proves, or None — forged, malformed, or
    signed by an earlier run of this process."""
    shape = _SHAPE.fullmatch(value or "")
    if not shape:
        return None
    device_id, mac = shape.groups()
    return device_id if hmac.compare_digest(mac, _mac(device_id)) else None


def device_of(request: Request) -> str | None:
    return verified(request.cookies.get(COOKIE, ""))
