"""The spending guard on the public share link."""
import pytest

from app.api import limits
from app.config import settings


@pytest.fixture()
def limited(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_hour", 3)
    monkeypatch.setattr(settings, "max_checks_per_day", 5)
    limits.reset()
    return client


def _check(client):
    return client.post("/api/v1/verify/text", json={"text": "5G claim"})


def test_per_visitor_hourly_limit(limited):
    for _ in range(3):
        assert _check(limited).status_code == 202
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "this hour" in blocked.json()["detail"]


def test_daily_limit_across_everyone(limited, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    for _ in range(5):
        assert _check(limited).status_code == 202
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "daily limit" in blocked.json()["detail"]


def test_reading_a_report_is_never_rate_limited(limited):
    job_id = _check(limited).json()["job_id"]
    for _ in range(20):
        assert limited.get(f"/api/v1/reports/{job_id}").status_code == 200


def test_disabled_by_default_for_local_use(client):
    # The `client` fixture leaves rate_limit_enabled False (see conftest).
    for _ in range(15):
        assert _check(client).status_code == 202
