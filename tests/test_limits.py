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


def test_rejected_submissions_do_not_burn_quota(limited, monkeypatch):
    """A too-long paste costs nothing, so it must not consume a check."""
    monkeypatch.setattr(settings, "max_input_chars", 10)
    for _ in range(5):
        assert limited.post("/api/v1/verify/text",
                            json={"text": "x" * 100}).status_code == 413
    # Quota untouched: all 3 real checks still available.
    for _ in range(3):
        assert _check(limited).status_code == 202


def test_visitor_table_does_not_grow_without_bound(limited, monkeypatch):
    """Many one-off visitors must not leak memory on a long-running server."""
    from starlette.requests import Request

    monkeypatch.setattr(settings, "max_checks_per_day", 10_000)

    def fake_request(ip):
        return Request({"type": "http", "client": (ip, 1234), "headers": []})

    for i in range(600):
        limits.reserve(fake_request(f"10.0.{i // 256}.{i % 256}"))
    assert len(limits._per_client) <= 512


def test_concurrent_submissions_cannot_all_pass_the_same_empty_counter(limited):
    """The cap must hold under parallel uploads, not just sequential ones."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
        codes = [f.result().status_code
                 for f in [pool.submit(_check, limited) for _ in range(20)]]

    # 3 allowed per hour (see the `limited` fixture); the rest must be refused.
    assert codes.count(202) == 3
    assert codes.count(429) == 17
