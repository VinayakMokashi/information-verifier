"""The free demo must be structurally incapable of spending money.

`share_demo.ps1 -DemoMode` puts this on a PUBLIC url advertised as costing
nothing, so an unpatched paid seam is a real bill. These tests pin every
seam and the dummy-key backstop.
"""
import scripts.fake_stages as F
from app.api import routes as R
from app.config import settings
from app.engine import pipeline as P
from app.providers.asr import SarvamASR


def test_apply_fake_stages_patches_every_paid_seam(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-real-key")
    monkeypatch.setattr(settings, "sarvam_api_key", "real-sarvam-key")
    monkeypatch.setattr(settings, "google_factcheck_api_key", "real-google-key")

    # apply_fake_stages assigns module attributes directly, so snapshot them
    # rather than reloading the modules (which would orphan routes' _repo).
    seams = [(P, "normalize"), (P, "extract_claims"), (P, "gather_evidence"),
             (P, "adjudicate"), (P, "claims_equivalent"), (P, "localize"),
             (R, "ocr_image"), (R, "get_asr_provider")]
    originals = [(mod, name, getattr(mod, name)) for mod, name in seams]

    F.apply_fake_stages()
    try:
        # Every seam that can reach a paid API is a fake.
        assert P.normalize is F.fake_normalize
        assert P.extract_claims is F.fake_extract
        assert P.gather_evidence is F.fake_gather
        assert P.adjudicate is F.fake_adjudicate
        assert P.claims_equivalent is F.fake_equivalent
        assert P.localize is F.fake_localize
        assert R.ocr_image is F.fake_ocr
        assert not isinstance(R.get_asr_provider(), SarvamASR)

        # Backstop: even a seam we forgot would fail auth, not spend.
        for key in (settings.anthropic_api_key, settings.sarvam_api_key,
                    settings.google_factcheck_api_key):
            assert key == "demo-mode-not-a-real-key"

        # Assert on the value that actually goes ON THE WIRE. The Anthropic
        # client is built once at import, so blanking `settings` alone left
        # the live client holding the real key — the backstop looked right
        # and protected nothing.
        from app.providers import llm

        assert llm.async_client.api_key == "demo-mode-not-a-real-key"
        assert "demo-mode-not-a-real-key" in str(llm.async_client.auth_headers)
    finally:
        for mod, name, original in originals:
            setattr(mod, name, original)


def test_demo_voice_note_never_reaches_sarvam(client, monkeypatch, tmp_path):
    """The regression that mattered: /verify/media in demo mode was live."""
    import shutil
    import subprocess

    if shutil.which("ffmpeg") is None:
        import pytest

        pytest.skip("ffmpeg not installed")

    out = tmp_path / "tone.ogg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "sine=frequency=440:duration=1", "-c:a", "libopus", str(out)],
        check=True, capture_output=True,
    )

    monkeypatch.setattr(settings, "sarvam_api_key", "demo-mode-not-a-real-key")
    monkeypatch.setattr(R, "get_asr_provider", lambda: F.FakeASR())

    resp = client.post(
        "/api/v1/verify/media",
        files={"file": ("note.ogg", out.read_bytes(), "audio/ogg")},
    )
    assert resp.status_code == 202
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "COMPLETE"


def test_fake_equivalence_is_strict():
    import asyncio

    assert asyncio.run(F.fake_equivalent("5G spreads COVID", "5g  spreads covid"))
    assert not asyncio.run(F.fake_equivalent("pandemic in 2020", "pandemic in 2019"))
