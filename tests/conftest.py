"""Shared fixtures: a fully-offline app client with every paid seam faked."""
import pytest
from fastapi.testclient import TestClient

import scripts.fake_stages as F
from app.api import limits, routes as R
from app.config import settings
from app.engine import chat as C


@pytest.fixture(autouse=True)
def _no_rate_limit(monkeypatch):
    """Tests submit far faster than a human; the limiter is tested explicitly."""
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    limits.reset()
    yield
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
