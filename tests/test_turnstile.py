"""Cloudflare Turnstile: a person, verified before any money moves. Free.

Every test here answers siteverify with an httpx.MockTransport: no test may
reach challenges.cloudflare.com (invariant 9; the research's L4 note).
"""
import asyncio
import logging

import httpx
import pytest

from app.config import settings
from app.providers import turnstile as T

_SECRET = "SECRET-TURNSTILE-0123456789"
_TOKEN = "XXXX.DUMMY.TOKEN.XXXX"      # what Cloudflare's test site keys produce


@pytest.fixture()
def cloudflare(monkeypatch):
    """A fake siteverify. -> (answer it gives, requests it saw)."""
    seen, answer = [], {"status": 200, "json": {"success": True}}

    def handler(request):
        seen.append(request)
        return httpx.Response(answer["status"], json=answer["json"])

    monkeypatch.setattr(T, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(settings, "turnstile_site_key", "1x00000000000000000000AA")
    monkeypatch.setattr(settings, "turnstile_secret_key", _SECRET)
    return answer, seen


def test_a_pass_is_a_pass_and_the_secret_never_rides_in_a_url(cloudflare, caplog):
    answer, seen = cloudflare
    with caplog.at_level(logging.INFO, logger="httpx"):
        assert asyncio.run(T.verify(_TOKEN, "203.0.113.7")) is True
    (request,) = seen
    assert request.method == "POST" and str(request.url) == T._ENDPOINT
    form = dict(httpx.QueryParams(request.content.decode()))
    assert form["secret"] == _SECRET and form["response"] == _TOKEN
    assert form["remoteip"] == "203.0.113.7" and form["idempotency_key"]
    assert _SECRET not in str(request.url) and _SECRET not in caplog.text


@pytest.mark.parametrize("codes", [["invalid-input-response"], ["timeout-or-duplicate"], []])
def test_cloudflare_saying_no_is_a_no(cloudflare, codes):
    answer, _ = cloudflare
    answer["json"] = {"success": False, "error-codes": codes}
    assert asyncio.run(T.verify(_TOKEN, None)) is False


def test_our_own_bad_secret_is_not_blamed_on_the_visitor(cloudflare, capsys):
    """A wrong TURNSTILE_SECRET_KEY would otherwise tell every visitor they
    failed the challenge; it is our fault, so: "could not verify", loudly."""
    answer, _ = cloudflare
    answer["json"] = {"success": False, "error-codes": ["invalid-input-secret"]}
    assert asyncio.run(T.verify(_TOKEN, None)) is None
    out = capsys.readouterr().out
    assert "TURNSTILE_SECRET_KEY" in out and _SECRET not in out


@pytest.mark.parametrize("status", [500, 503, 429])
def test_cloudflare_unreachable_is_unknown_never_a_pass(cloudflare, status):
    answer, _ = cloudflare
    answer["status"], answer["json"] = status, {"success": True}
    assert asyncio.run(T.verify(_TOKEN, None)) is None


def test_a_dropped_connection_is_unknown_never_a_pass(monkeypatch, capsys):
    def handler(request):
        raise httpx.ConnectError("down", request=request)

    monkeypatch.setattr(T, "_TRANSPORT", httpx.MockTransport(handler))
    monkeypatch.setattr(settings, "turnstile_secret_key", _SECRET)
    assert asyncio.run(T.verify(_TOKEN, None)) is None
    assert "ConnectError" in capsys.readouterr().out


@pytest.mark.parametrize("token", ["", None, "x" * 2049])
def test_no_token_or_an_oversized_one_never_reaches_cloudflare(cloudflare, token):
    _, seen = cloudflare
    assert asyncio.run(T.verify(token, None)) is False
    assert seen == []


def test_it_is_on_only_with_both_keys(monkeypatch):
    monkeypatch.setattr(settings, "turnstile_site_key", "site")
    monkeypatch.setattr(settings, "turnstile_secret_key", "")
    assert not T.enabled()
    monkeypatch.setattr(settings, "turnstile_secret_key", _SECRET)
    assert T.enabled()
