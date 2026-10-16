"""Shared fixtures: a fully-offline app client with every paid seam faked."""
import os

# No real key in a test, ever — set BEFORE anything imports the app, because
# some clients read their key once, at import (the Anthropic case, §7).
# MEASURED 2026-10-16: the suite ran with the real keys from .env loaded,
# and 8 link and voice tests passed only because a real Sarvam key was
# there. A dummy keeps those paths open, and a seam nobody faked reaches a
# provider with a key it refuses instead of one it bills. Environment
# variables outrank .env (pydantic-settings). tests/test_isolation.py pins it.
for _key in ("ANTHROPIC_API_KEY", "GOOGLE_FACTCHECK_API_KEY", "SARVAM_API_KEY",
             "HF_TOKEN", "TELEGRAM_BOT_TOKEN"):
    os.environ[_key] = "test-not-a-real-key"
# The names the test clients send as Host — TestClient's "testserver",
# httpx's "http://test" — are this app's public names here: a paid POST to
# any other name is refused (review R5). tests/test_cross_site.py sets its own.
os.environ["PUBLIC_HOSTS"] = "testserver,test"
# No Turnstile unless a test turns it on: a configured one demands a token
# for every paid check and asks Cloudflare (tests/test_turnstile.py fakes it).
os.environ["TURNSTILE_SITE_KEY"] = ""
os.environ["TURNSTILE_SECRET_KEY"] = ""
# No owner alerts from a test (app/providers/alerts.py): tests/test_alerts.py
# turns them on against a fake Telegram.
os.environ["OWNER_CHAT_ID"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import scripts.fake_stages as F  # noqa: E402
from app.api import limits, routes as R  # noqa: E402
from app.config import settings  # noqa: E402
from app.engine import chat as C  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _never_the_real_database(tmp_path_factory):
    """Point the default database at a throwaway file for the whole session.

    MEASURED 2026-09-29: each run of this suite handed one of the day's
    paid-for slots back on the REAL database (tests/test_isolation.py has
    the mechanism). Work that finishes after a test — a cancelled claim
    settling on the limiter's pool — reads `settings.db_path` once the
    test's patches are undone, and undoing restores whatever was there
    before. Set here, before any test patches anything, that is a
    throwaway file. Deliberately never restored: late work can outlive the
    session's teardown too.
    """
    settings.db_path = str(tmp_path_factory.mktemp("session") / "default.db")
    yield


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """Tests submit far faster than a human; the limiter is tested explicitly."""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    limits.reset()
    yield
    # No claim may outlive the test that made it. MEASURED 2026-10-11: claims
    # a test cancelled settled later in OTHER tests' databases — one took a
    # slot in another test's 2-slot cap (a 429 in 1 full run of 3). Drained
    # HERE, before monkeypatch undoes this test's settings, so late work
    # still lands in this test's own database. It used to fall back to the
    # real one (the session fixture above).
    assert limits.drain(), "a quota claim was still running 10 s after its test"
    limits.reset()


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "test.db"))
    # THE paid seam. One engine call replaced six pipeline stages, so there is
    # exactly one thing to forget here now instead of six.
    monkeypatch.setattr(C, "answer", F.fake_answer)
    monkeypatch.setattr(R, "ocr_image", F.fake_ocr)
    # Every paid seam the routes can reach, faked HERE rather than per-test —
    # "a seam nobody remembered" is how demo mode billed real money once
    # already (PROJECT_PLAN §7, 2026-07-26).
    monkeypatch.setattr(R, "get_asr_provider", lambda: F.FakeASR())
    # resolve_link is $0 but ONLINE (tests must never touch the network);
    # gather_link_text reaches Sarvam when a post has no subtitles.
    monkeypatch.setattr(R, "resolve_link", F.fake_resolve_link)
    monkeypatch.setattr(R, "gather_link_text", F.fake_gather_link_text)
    F.CALLS["answer"] = 0

    from app.main import app

    with TestClient(app) as c:
        yield c
