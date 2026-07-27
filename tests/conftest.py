"""Shared fixtures: a fully-offline app client with every paid stage faked."""
import pytest
from fastapi.testclient import TestClient

import scripts.fake_stages as F
from app.api import limits, routes as R
from app.config import settings
from app.engine import pipeline as P


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
    monkeypatch.setattr(settings, "semantic_cache_enabled", False)  # no model in tests
    monkeypatch.setattr(P, "normalize", F.fake_normalize)
    monkeypatch.setattr(P, "extract_claims", F.fake_extract)
    monkeypatch.setattr(P, "gather_evidence", F.fake_gather)
    monkeypatch.setattr(P, "adjudicate", F.fake_adjudicate)
    monkeypatch.setattr(P, "claims_equivalent", F.fake_equivalent)
    # Not optional: FakeNorm reports Hindi, so an unpatched localize() would
    # make real Anthropic calls on every test that runs the pipeline.
    monkeypatch.setattr(P, "localize", F.fake_localize)
    monkeypatch.setattr(R, "ocr_image", F.fake_ocr)
    F.CALLS["adjudicate"] = 0

    from app.main import app

    with TestClient(app) as c:
        yield c
