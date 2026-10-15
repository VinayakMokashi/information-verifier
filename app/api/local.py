"""Is this request from THIS machine? One rule, shared.

Two things depend on it, and they must never disagree:

  * the spending dashboard, served to this machine only (a 404 to anyone
    else — app/api/dashboard.py);
  * the limiter, which lets a caller on this machine — the Telegram bot,
    submitting for many people over ONE connection — name the person it is
    submitting for (app/api/limits.py, subject_of). A visitor who could do
    that would pick a fresh bucket for every check.

From this machine means: it arrived from loopback, AND carries no proxy
header, AND names this machine in exactly one Host header.

  * The cloudflared tunnel connects from 127.0.0.1 but always adds
    X-Forwarded-For / CF-Connecting-IP (and uvicorn rewrites the client to
    the visitor's IP anyway).
  * DNS rebinding (found by review, reproduced): a page the owner visits
    re-resolves its own name to 127.0.0.1, and its same-origin fetch then
    arrives from this machine with no proxy header. The connection cannot
    tell that apart; the Host header can, because the browser still sends
    the attacker's name.
  * Exactly one Host: a request carrying two (a local one first, an
    attacker's second) passed when only the first was read. No browser can
    send that, but the rule should not depend on which one a parser hands
    over.
"""
import re

from starlette.requests import Request

_LOCAL_HOSTS = {"127.0.0.1", "::1"}
_PROXY_HEADERS = ("x-forwarded-for", "forwarded", "x-real-ip",
                  "cf-connecting-ip", "true-client-ip", "x-forwarded-host")
# The names this machine is asked for by, with an optional port. Exact match:
# anything a DNS name could be registered as must fail.
_LOCAL_HOST_HEADER = re.compile(r"(?:127\.0\.0\.1|localhost|\[::1\])(?::\d{1,5})?",
                                re.IGNORECASE)


def is_this_machine(request: Request) -> bool:
    peer = request.client.host if request.client else ""
    hosts = request.headers.getlist("host")
    return (peer in _LOCAL_HOSTS
            and not any(h in request.headers for h in _PROXY_HEADERS)
            and len(hosts) == 1
            and bool(_LOCAL_HOST_HEADER.fullmatch(hosts[0])))
