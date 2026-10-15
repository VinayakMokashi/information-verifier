"""On the web, a person is a DEVICE: a signed cookie, earned by a Turnstile pass. Free.

Decided 2026-10-15 (PROJECT_PLAN §7): 3 paid checks a day per web device, by
a cookie issued only after a Cloudflare Turnstile pass; Turnstile in managed
mode on every paid web submission, verified before any slot or money is
claimed (docs/research/2026-10-15/limits-budget.md, L2 and L4). The Telegram
bot and this machine are not web visitors and are never challenged.
Cloudflare itself is faked here (tests/test_turnstile.py covers the call).
"""
import pytest
from fastapi.testclient import TestClient

from app.api import device, limits
from app.config import settings
from app.providers import turnstile as T
from app.store.repository import DailyBudget

_TOKEN = {"x-turnstile-token": "XXXX.DUMMY.TOKEN.XXXX"}


@pytest.fixture()
def guarded(client, monkeypatch):
    """Turnstile on, Cloudflare faked: it answers what `answer[0]` says. Over
    https, as visitors arrive through the tunnel: the cookie is Secure, and
    a client on http:// would rightly never send it back."""
    from app.main import app

    answer = [True]

    async def verify(token, remoteip):
        return answer[0] if token else False

    monkeypatch.setattr(settings, "turnstile_site_key", "1x00000000000000000000AA")
    monkeypatch.setattr(settings, "turnstile_secret_key", "1x0000000000000000000000000000000AA")
    monkeypatch.setattr(T, "verify", verify)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    limits.reset()
    with TestClient(app, base_url="https://testserver") as visitor:
        yield visitor, answer


_n = iter(range(10**9))


def _text(c, headers=None):
    return c.post("/api/v1/verify/text", json={"text": f"5G claim number {next(_n)}"},
                  headers=headers if headers is not None else _TOKEN)


def _nothing_held():
    return (limits.used_today(), DailyBudget().committed(limits.today()),
            limits._in_flight, limits._person_today)


def test_a_pass_earns_a_device_cookie_and_the_check_counts_against_it(guarded):
    c, _ = guarded
    resp = _text(c)
    assert resp.status_code == 202
    cookie = resp.headers["set-cookie"]
    for attribute in ("vd=", "HttpOnly", "Secure", "SameSite=strict", "Path=/api/v1"):
        assert attribute.lower() in cookie.lower(), attribute
    (person,) = limits._person_today
    assert person.startswith("dev:"), "the check was not counted against the device"


def test_the_same_device_is_the_same_person_and_gets_three_a_day(guarded):
    c, _ = guarded
    first = _text(c)                                # TestClient keeps the cookie
    for _ in range(2):
        resp = _text(c)
        assert resp.status_code == 202
        assert "set-cookie" not in resp.headers, "a device that has one got another"
    assert len(limits._person_today) == 1
    over = _text(c)
    assert over.status_code == 429 and "3 checks" in over.json()["detail"]
    assert first.status_code == 202


@pytest.mark.parametrize("headers", [{}, {"x-turnstile-token": ""}])
def test_no_pass_means_no_check_and_nothing_held(guarded, headers):
    c, _ = guarded
    resp = _text(c, headers)
    assert resp.status_code == 403 and "person" in resp.json()["detail"]
    assert "set-cookie" not in resp.headers
    assert _nothing_held() == (0, 0, {}, {})


def test_cloudflare_saying_no_holds_nothing(guarded):
    c, answer = guarded
    answer[0] = False
    resp = _text(c)
    assert resp.status_code == 403
    assert _nothing_held() == (0, 0, {}, {})


def test_cloudflare_unreachable_is_never_a_free_pass(guarded):
    c, answer = guarded
    answer[0] = None
    resp = _text(c)
    assert resp.status_code == 503 and "try again" in resp.json()["detail"]
    assert _nothing_held() == (0, 0, {}, {})


def test_a_link_is_challenged_before_its_free_work_too(guarded, monkeypatch):
    """The deferred routes admit before their free resolve: no pass, no
    place in line either."""
    c, _ = guarded
    resp = c.post("/api/v1/verify/link",
                  json={"url": "https://www.youtube.com/watch?v=hhhhhhhhhhh"})
    assert resp.status_code == 403
    assert _nothing_held() == (0, 0, {}, {})


def test_a_forged_cookie_is_nobody(guarded):
    c, _ = guarded
    resp = _text(c, {**_TOKEN, "cookie": "vd=" + "A" * 22 + "." + "B" * 22})
    assert resp.status_code == 202
    assert "set-cookie" in resp.headers, "a forged cookie was taken as a device"
    (person,) = limits._person_today
    assert person != "dev:" + "A" * 22


def test_the_bot_and_this_machine_are_never_challenged(guarded):
    from app.main import app

    with TestClient(app, base_url="http://127.0.0.1:8000",
                    client=("127.0.0.1", 50000)) as local:
        resp = local.post("/api/v1/verify/text", json={"text": "a claim from the bot"},
                          headers={"x-verifier-subject": "tg:42"})
    assert resp.status_code == 202
    assert "set-cookie" not in resp.headers
    assert "tg:42" in limits._person_today


def test_with_turnstile_off_nothing_changes(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    resp = _text(client, {})
    assert resp.status_code == 202 and "set-cookie" not in resp.headers


@pytest.mark.parametrize("configured", [False, True])
def test_going_public_without_turnstile_is_said_out_loud(client, monkeypatch, capsys,
                                                        configured):
    from app.main import app

    monkeypatch.setattr(settings, "public_hosts", "verifier.example.com")
    if configured:
        monkeypatch.setattr(settings, "turnstile_site_key", "1x00000000000000000000AA")
        monkeypatch.setattr(settings, "turnstile_secret_key", "s3cr3t")
    capsys.readouterr()
    with TestClient(app):
        pass
    out = capsys.readouterr().out
    assert ("Turnstile is not" in out) is not configured
    assert "s3cr3t" not in out


def test_a_cookie_is_only_ever_this_processes_own():
    device_id, value = device.mint()
    assert device.verified(value) == device_id
    assert device.verified(value[:-1] + ("A" if value[-1] != "A" else "B")) is None
    assert device.verified(device_id) is None
    assert device.verified("") is None
