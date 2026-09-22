"""The spending dashboard: shows the owner's spend, to the owner only. Free."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.models.answer import Answer, AnswerSection, JobStatus, ModelUsage, ReportUsage


@pytest.fixture()
def local(client):
    """The same app, requested the way the owner does: from this machine, at
    the address the startup banner prints."""
    from app.main import app

    with TestClient(app, base_url="http://127.0.0.1:8000",
                    client=("127.0.0.1", 50000)) as c:
        yield c


def _record(usd, *, kind="text", cached=False, status=JobStatus.COMPLETE,
            searches=1, asr=0.0):
    from app.api import routes as R

    now = datetime.now(timezone.utc)
    answer = Answer(
        job_id=uuid.uuid4().hex, status=status, created_at=now, completed_at=now,
        input_text="SECRET message text", tier="trusted", cached=cached,
        sections=[AnswerSection(tier="trusted", markdown="It is false.")],
        usage=ReportUsage(
            models={"claude-sonnet-5": ModelUsage(calls=1, input_tokens=10, output_tokens=10)},
            web_searches=searches, asr_seconds=asr, estimated_usd=usd,
            llm_usd=usd - searches * 0.01 - asr * 0.0001, search_usd=searches * 0.01,
            asr_usd=asr * 0.0001))
    R._repo.ledger.record(answer, kind)


# -- who can see it -----------------------------------------------------------

def test_it_is_served_to_this_machine(local):
    page = local.get("/dashboard")
    assert page.status_code == 200
    assert "Spending" in page.text
    assert local.get("/api/v1/admin/spend").status_code == 200


def test_it_is_invisible_to_anyone_else(client):
    """The default TestClient is not 127.0.0.1 — i.e., someone else. 404,
    not 403: nothing announces that a dashboard exists."""
    assert client.get("/dashboard").status_code == 404
    assert client.get("/api/v1/admin/spend").status_code == 404


@pytest.mark.parametrize("header", ["X-Forwarded-For", "CF-Connecting-IP", "Forwarded",
                                    "X-Real-IP"])
def test_it_is_invisible_through_the_share_tunnel(local, header):
    """cloudflared connects from 127.0.0.1, so "is it localhost?" alone would
    hand the owner's spending to anyone holding the public share link. The
    tunnel always adds a forwarding header; any one of them means "remote"."""
    headers = {header: "203.0.113.9"}
    assert local.get("/dashboard", headers=headers).status_code == 404
    assert local.get("/api/v1/admin/spend", headers=headers).status_code == 404


@pytest.mark.parametrize("host", ["rebind.attacker.example:8000",
                                  "rebind.attacker.example", "127.0.0.1.evil.example",
                                  "localhost.evil.example:8000", "127.0.0.1:8000@evil"])
def test_a_rebound_hostname_is_not_this_machine(local, host):
    """Found by review, reproduced: DNS rebinding. A page the owner visits
    re-resolves its own name to 127.0.0.1, so its fetch arrives from this
    machine with no proxy header — and got the dashboard's data, which
    listed job ids that open other people's messages. The browser still
    sends the ATTACKER's name as Host; only a local name may pass."""
    headers = {"Host": host}
    assert local.get("/dashboard", headers=headers).status_code == 404
    assert local.get("/api/v1/admin/spend", headers=headers).status_code == 404


@pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "LOCALHOST:8000",
                                  "[::1]:8000", "127.0.0.1"])
def test_the_owners_own_addresses_still_work(local, host):
    assert local.get("/dashboard", headers={"Host": host}).status_code == 200


def test_the_recent_list_carries_no_job_ids(local):
    """A job id opens /reports/{id} — the full message — to anyone, through
    the public tunnel too. The page never used them; they are not sent."""
    _record(0.05)
    body = local.get("/api/v1/admin/spend").json()
    assert body["recent"], "the row should be listed"
    assert all("job_id" not in row for row in body["recent"])


def test_the_page_is_not_reachable_through_the_public_static_mount(client):
    """It lives outside static/, which is served to everyone."""
    assert client.get("/dashboard.html").status_code == 404


# -- what it says -------------------------------------------------------------

def test_totals_breakdown_and_cap(local, monkeypatch):
    from app.config import settings

    _record(0.0483, searches=1)
    _record(0.1504, searches=3)
    _record(0.0, cached=True, searches=0)
    data = local.get("/api/v1/admin/spend?days=7").json()

    today = data["totals"]["today"]
    assert today["checks"] == 3 and today["cached"] == 1
    assert today["usd"] == pytest.approx(0.1987)
    assert today["search_usd"] == pytest.approx(0.04)
    assert data["cap"]["limit"] == settings.max_checks_per_day
    assert data["cap"]["resets"] == "midnight India time"


def test_every_day_in_the_range_is_present(local):
    """A day with no checks is a real $0, not a gap in the time axis."""
    data = local.get("/api/v1/admin/spend?days=30").json()
    assert len(data["by_day"]) == 30
    assert data["by_day"][-1]["day"] == data["today"]
    days = [d["day"] for d in data["by_day"]]
    assert days == sorted(days) and len(set(days)) == 30


def test_the_range_is_bounded(local):
    assert len(local.get("/api/v1/admin/spend?days=100000").json()["by_day"]) == 366
    assert len(local.get("/api/v1/admin/spend?days=0").json()["by_day"]) == 1


def test_no_message_content_ever_reaches_the_dashboard(local):
    _record(0.05)
    body = local.get("/api/v1/admin/spend").text
    assert "SECRET" not in body


def test_the_page_renders_values_as_text_never_markup():
    """Ledger values (kind, tier, model ids) go through textContent. The page
    must not build DOM from strings."""
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "app" / "api" / "dashboard.html"
            ).read_text(encoding="utf-8")
    assert "innerHTML" not in page
    assert "textContent" in page
    # Accessibility twins the dataviz method requires.
    assert "Show as table" in page                 # table view for the chart
    assert "prefers-color-scheme: dark" in page    # dark mode, selected not flipped
    assert 'data-theme="dark"' in page
