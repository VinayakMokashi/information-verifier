"""Every report carries its own measured bill. Free — nothing calls out.

What these pin: usage flows from concurrent children into the right meter
(two reports running at once must not mix bills), a report is attached its
usage even when it fails, ASR seconds are captured at the ffmpeg boundary,
and the instrumented client is a strict no-op when no meter is active.
"""
import asyncio
import shutil
import subprocess
import types

import pytest

from app.config import settings
from app.providers import usage as U
from app.providers.usage import UsageMeter, instrument


def _usage(inp=100, out=10, cw=0, cr=0, searches=0):
    u = types.SimpleNamespace(
        input_tokens=inp, output_tokens=out,
        cache_creation_input_tokens=cw, cache_read_input_tokens=cr,
        server_tool_use=types.SimpleNamespace(web_search_requests=searches),
    )
    return u


# -- the meter itself ---------------------------------------------------------

def test_concurrent_children_bill_the_activating_meter():
    """The pipeline fans claims out with gather(); contextvars must carry the
    meter into every child or a report's bill would be partial."""
    meter = UsageMeter()

    async def child():
        U.note_llm("claude-haiku-4-5", _usage(inp=50, out=5))

    async def main():
        with meter.activate():
            await asyncio.gather(child(), child(), child())

    asyncio.run(main())
    snap = meter.snapshot()
    assert snap.models["claude-haiku-4-5"].calls == 3
    assert snap.models["claude-haiku-4-5"].input_tokens == 150


def test_two_meters_do_not_mix():
    """Two reports can be in flight at once; each must get only its own calls."""
    a, b = UsageMeter(), UsageMeter()

    async def job(meter, n):
        with meter.activate():
            await asyncio.sleep(0)   # force interleaving
            U.note_llm("claude-haiku-4-5", _usage(inp=n, out=0))

    async def main():
        await asyncio.gather(job(a, 111), job(b, 222))

    asyncio.run(main())
    assert a.snapshot().models["claude-haiku-4-5"].input_tokens == 111
    assert b.snapshot().models["claude-haiku-4-5"].input_tokens == 222


def test_no_active_meter_is_a_quiet_noop():
    U.note_llm("claude-haiku-4-5", _usage())    # must not raise
    U.note_asr(30.0)


def test_meter_reaches_into_to_thread_workers():
    """normalize_to_wav runs via asyncio.to_thread; contextvars must follow."""
    meter = UsageMeter()

    async def main():
        with meter.activate():
            await asyncio.to_thread(U.note_asr, 42.0)

    asyncio.run(main())
    assert meter.snapshot().asr_seconds == 42.0


def test_estimate_prices_measured_tokens():
    meter = UsageMeter()
    meter.note_llm("claude-haiku-4-5", _usage(inp=1_000_000, out=0, searches=2))
    meter.note_asr(3600.0)
    snap = meter.snapshot()
    # $1 (Haiku MTok in) + $0.02 (2 searches) + ₹30/₨88 of ASR
    assert snap.estimated_usd == pytest.approx(1.0 + 0.02 + 30 / 88, abs=0.01)
    assert snap.web_searches == 2


def test_an_unknown_model_is_priced_as_the_dearest():
    cheap, unknown = UsageMeter(), UsageMeter()
    cheap.note_llm("claude-haiku-4-5", _usage(inp=1_000_000))
    unknown.note_llm("claude-next-99", _usage(inp=1_000_000))
    assert unknown.snapshot().estimated_usd > cheap.snapshot().estimated_usd


# -- the instrumented client --------------------------------------------------

def test_instrument_reports_into_the_active_meter_only():
    class Messages:
        async def parse(self, **kw):
            return types.SimpleNamespace(usage=_usage(inp=10, out=1), parsed_output=None)

        async def create(self, **kw):
            return types.SimpleNamespace(usage=_usage(inp=20, out=2, searches=1))

    client = types.SimpleNamespace(messages=Messages())
    instrument(client)
    instrument(client)   # idempotent — wrapping twice must not double-count

    meter = UsageMeter()

    async def main():
        await client.messages.parse(model="claude-haiku-4-5")   # no meter: dropped
        with meter.activate():
            await client.messages.parse(model="claude-haiku-4-5")
            await client.messages.create(model="claude-haiku-4-5")

    asyncio.run(main())
    snap = meter.snapshot()
    assert snap.models["claude-haiku-4-5"].calls == 2       # not 3, not 4
    assert snap.models["claude-haiku-4-5"].input_tokens == 30
    assert snap.web_searches == 1


def test_a_metering_failure_never_sinks_the_call():
    class ExplodingUsage:
        @property
        def input_tokens(self):
            raise RuntimeError("usage object from a future SDK")

    class Messages:
        async def parse(self, **kw):
            return types.SimpleNamespace(usage=ExplodingUsage())

        async def create(self, **kw):
            return types.SimpleNamespace(usage=ExplodingUsage())

    client = types.SimpleNamespace(messages=Messages())
    instrument(client)

    async def main():
        with UsageMeter().activate():
            return await client.messages.parse(model="m")

    assert asyncio.run(main()) is not None


# -- end to end through the routes -------------------------------------------

def test_every_report_carries_a_usage_block(client):
    resp = client.post("/api/v1/verify/text", json={"text": "WHO ne kaha 5G"})
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()

    assert report["status"] == "COMPLETE"
    usage = report["usage"]
    assert usage is not None
    # Faked stages make no client calls, so the measured bill is honestly $0.
    assert usage["models"] == {}
    assert usage["estimated_usd"] == 0.0


def test_media_reports_carry_their_asr_seconds(client, monkeypatch, tmp_path):
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not installed")
    out = tmp_path / "tone.ogg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=2", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )
    monkeypatch.setattr(settings, "sarvam_api_key", "demo-mode-not-a-real-key")

    resp = client.post("/api/v1/verify/media",
                       files={"file": ("note.ogg", out.read_bytes(), "audio/ogg")})
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()

    assert report["status"] == "COMPLETE"
    assert report["usage"]["asr_seconds"] == pytest.approx(2.0, abs=0.3)
    assert report["usage"]["estimated_usd"] > 0     # ASR seconds price in


def test_a_failed_report_still_carries_its_bill(client, monkeypatch):
    """Failures cost money too; the bill must not vanish with the verdict."""
    from app.api import routes as R
    from app.providers.links import LinkInfo

    # `tests` is not a package, so no cross-test-module imports — inline the
    # minimal fixtures instead (same trap as test_back_translation notes).
    async def gather_that_spends_then_dies(info):
        U.note_asr(10.0)   # stands in for a decode billed before the failure
        raise RuntimeError("stream died")

    monkeypatch.setattr(R, "gather_link_text", gather_that_spends_then_dies)
    monkeypatch.setattr(R, "resolve_link", lambda u: LinkInfo(
        url=u, platform="Instagram", video_id="X", title="t", uploader="u",
        duration=None, caption="c", has_media=True, subtitle=None))
    monkeypatch.setattr(settings, "sarvam_api_key", "demo-mode-not-a-real-key")

    resp = client.post("/api/v1/verify/link",
                       json={"url": "https://www.instagram.com/reel/x/"})
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()

    assert report["status"] == "FAILED"
    assert report["usage"]["asr_seconds"] == 10.0
