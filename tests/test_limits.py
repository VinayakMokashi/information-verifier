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


def test_a_rejection_that_came_after_paying_still_burns_quota(client, monkeypatch):
    """The hole this closes: /verify/image raises 422 ("no text in this image")
    AFTER a paid Opus vision call, and the refund handed the slot straight
    back — so a loop of blank images could bill all day with the counter
    still reading zero. A refund is only honest when nothing was bought."""
    from app.api import limits, routes as R

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_checks_per_day", 100)
    limits.reset()

    async def ocr_that_costs_money_and_finds_nothing(image_bytes, media_type):
        return ""      # paid for, no text found -> the 422 below

    monkeypatch.setattr(R, "ocr_image", ocr_that_costs_money_and_finds_nothing)

    resp = client.post("/api/v1/verify/image",
                       files={"file": ("blank.png", b"\x89PNG", "image/png")})
    assert resp.status_code == 422
    assert limits.used_today() == 1, "a paid-for request must consume its quota slot"


def test_a_rejection_before_any_spending_is_refunded(client, monkeypatch):
    """The other direction still holds — a 415 costs nothing, so it is free."""
    from app.api import limits

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()

    resp = client.post("/api/v1/verify/image",
                       files={"file": ("notes.txt", b"hi", "text/plain")})
    assert resp.status_code == 415
    assert limits.used_today() == 0


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


# -- the 2-a-day decision (Vinayak, 2026-09-22) -------------------------------

def test_the_daily_cap_defaults_to_two():
    """Pinned because it is a DECISION, not a tuning knob: "lower it for now
    and do only 2 checks per day, just to be safe." Raising it should be a
    deliberate edit here AND in config.py, recorded in PROJECT_PLAN §7."""
    from app.config import Settings

    assert Settings.model_fields["max_checks_per_day"].default == 2


def test_the_daily_cap_survives_a_restart(limited, monkeypatch):
    """The in-memory counter reset on every restart — under `--reload`, every
    saved file. Simulate one by wiping all in-process state: the count must
    still be there, and the cap must still hold."""
    monkeypatch.setattr(settings, "max_checks_per_day", 2)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    assert _check(limited).status_code == 202
    assert _check(limited).status_code == 202

    limits.reset()                       # everything a restart would lose

    assert limits.used_today() == 2
    blocked = _check(limited)
    assert blocked.status_code == 429
    assert "daily limit of 2 checks" in blocked.json()["detail"]


def test_the_refusal_says_when_it_resets(limited, monkeypatch):
    monkeypatch.setattr(settings, "max_checks_per_day", 1)
    monkeypatch.setattr(settings, "max_checks_per_hour", 100)
    assert _check(limited).status_code == 202
    detail = _check(limited).json()["detail"]
    assert "daily limit of 1 check." in detail          # no "1 checks"
    assert "midnight India time" in detail


def test_a_day_is_the_operators_day_not_utcs(monkeypatch):
    """7 pm UTC on the 22nd is already 12:30 am on the 23rd in India. "2 a
    day" means his day."""
    import datetime as real

    class FrozenClock(real.datetime):
        @classmethod
        def now(cls, tz=None):
            return real.datetime(2026, 9, 22, 19, 0, tzinfo=real.timezone.utc)

    monkeypatch.setattr(limits, "datetime", FrozenClock)
    monkeypatch.setattr(settings, "day_boundary_utc_offset_min", 330)
    assert limits.today() == "2026-09-23"
    monkeypatch.setattr(settings, "day_boundary_utc_offset_min", 0)
    assert limits.today() == "2026-09-22"


def test_an_unwritable_counter_refuses_rather_than_waves_through(limited, monkeypatch):
    """The guard fails CLOSED. A locked or broken database must not become an
    unlimited budget."""
    def broken(*a, **kw):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(limits._daily, "take", broken)
    resp = _check(limited)
    assert resp.status_code == 503
    assert "busy" in resp.json()["detail"]


def test_the_database_itself_refuses_a_slot_past_the_cap(client):
    """The guarantee does not rest on the Python lock: the UPSERT's WHERE is
    what refuses slot 3, even for two processes racing."""
    from app.store.repository import DailyQuota

    quota = DailyQuota()
    assert [quota.take("2026-01-01", 2) for _ in range(5)] == [True, True, False, False, False]
    assert quota.used("2026-01-01") == 2
    assert quota.take("2026-01-02", 0) is False       # a zero cap grants nothing
