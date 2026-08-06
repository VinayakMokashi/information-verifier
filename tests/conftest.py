"""Shared fixtures: a fully-offline app client with every paid stage faked."""
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

import scripts.fake_stages as F
from app.api import limits, routes as R
from app.config import settings
from app.engine import pipeline as P, translate as T
from app.models.report import LocalizedClaim

HINDI_CLAIM = "5जी से कोरोना वायरस फैलता है।"
HINDI_REASONING = "भरोसेमंद स्रोतों के अनुसार यह दावा झूठा है।"
HINDI_CORRECTION = "कोरोना वायरस साँस की बूँदों से फैलता है।"
HINDI_SUMMARY = "1 दावे की जाँच की गई।"


def default_translation(kw):
    if kw["output_format"] is LocalizedClaim:
        return LocalizedClaim(claim=HINDI_CLAIM, reasoning=HINDI_REASONING,
                              correction=HINDI_CORRECTION)
    return T._LocalizedSummary(summary=HINDI_SUMMARY)


class _Resp:
    def __init__(self, parsed):
        self.parsed_output = parsed


class _Messages:
    def __init__(self):
        self.handler = default_translation   # swap per-test
        self.calls = []

    async def parse(self, **kw):
        self.calls.append(kw)
        result = self.handler(kw)
        if isinstance(result, Exception):     # a handler may return one to raise it
            raise result
        # A handler normally returns the parsed model and we wrap it. Returning
        # a non-model lets a test hand back a whole anomalous RESPONSE object
        # (no parsed_output, or one that raises) without affecting siblings.
        return _Resp(result) if isinstance(result, BaseModel) else result


class StubClient:
    """Stands in for the shared AsyncAnthropic in translation tests."""

    def __init__(self):
        self.messages = _Messages()


@pytest.fixture()
def stub(monkeypatch):
    """A translation stage that answers instantly, for free, and counts calls."""
    client = StubClient()
    monkeypatch.setattr(T, "async_client", client)
    monkeypatch.setattr(settings, "translate_reports", True)
    return client


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
    # Every paid seam the routes can reach, faked HERE rather than per-test.
    # Individual tests were patching this one themselves, which meant the
    # suite's freedom depended on each new /verify/media test remembering to
    # — and "a seam nobody remembered" is exactly how demo mode billed real
    # money once already (PROJECT_PLAN §7, 2026-07-26).
    monkeypatch.setattr(R, "get_asr_provider", lambda: F.FakeASR())
    # Link seams: resolve is $0 but ONLINE (tests must never touch the
    # network), and gather reaches Sarvam when a post has no subtitles.
    monkeypatch.setattr(R, "resolve_link", F.fake_resolve_link)
    monkeypatch.setattr(R, "gather_link_text", F.fake_gather_link_text)
    F.CALLS["adjudicate"] = 0

    from app.main import app

    with TestClient(app) as c:
        yield c
