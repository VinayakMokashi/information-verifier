"""The free demo must be structurally incapable of spending money.

`share_demo.ps1 -DemoMode` puts this on a PUBLIC url advertised as costing
nothing, so an unpatched paid seam is a real bill. These tests pin every seam
and the dummy-key backstop.
"""
import scripts.fake_stages as F
from app.api import routes as R
from app.config import settings
from app.engine import chat as C
from app.providers.asr import SarvamASR


def test_apply_fake_stages_patches_every_paid_seam(monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-real-key")
    monkeypatch.setattr(settings, "sarvam_api_key", "real-sarvam-key")
    monkeypatch.setattr(settings, "google_factcheck_api_key", "real-google-key")
    monkeypatch.setattr(settings, "turnstile_site_key", "real-site-key")
    monkeypatch.setattr(settings, "turnstile_secret_key", "real-turnstile-secret")
    # Patched first so the undo restores it: apply_fake_stages assigns it
    # directly, and it leaked "demo" into every later test's /ready.
    monkeypatch.setattr(settings, "demo_mode", False)

    # apply_fake_stages assigns module attributes directly, so snapshot them
    # rather than reloading the modules (which would orphan routes' _repo).
    seams = [(C, "answer"), (R, "ocr_image"), (R, "get_asr_provider"),
             (R, "resolve_link"), (R, "gather_link_text")]
    originals = [(mod, name, getattr(mod, name)) for mod, name in seams]

    F.apply_fake_stages()
    try:
        # Every seam that can reach a paid API — or, for resolve_link, any
        # network at all — is a fake.
        assert C.answer is F.fake_answer
        assert R.ocr_image is F.fake_ocr
        assert R.resolve_link is F.fake_resolve_link
        assert R.gather_link_text is F.fake_gather_link_text
        assert not isinstance(R.get_asr_provider(), SarvamASR)

        # Backstop: even a seam we forgot would fail auth, not spend.
        for key in (settings.anthropic_api_key, settings.sarvam_api_key,
                    settings.google_factcheck_api_key):
            assert key == "demo-mode-not-a-real-key"
        # Turnstile is switched OFF (empty), not dummied: the demo is
        # offline, and a configured Turnstile would ask Cloudflare.
        from app.providers import turnstile

        assert not turnstile.enabled()
        # And it says it is the demo, so the bot refuses it (OPS-18).
        assert settings.demo_mode is True

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


def test_a_demo_text_check_never_touches_the_llm_client(client, monkeypatch):
    """The engine seam is faked, so nothing may reach messages.stream at all."""
    from app.providers import llm

    def explode(**kw):
        raise AssertionError("the demo reached the real Anthropic client")

    monkeypatch.setattr(llm.async_client.messages, "stream", explode)

    resp = client.post("/api/v1/verify/text", json={"text": "WHO ne kaha 5G"})
    report = client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()
    assert report["status"] == "COMPLETE"
    assert report["usage"]["estimated_usd"] == 0.0      # honestly free


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


def test_the_canned_answer_mirrors_the_senders_script():
    """The demo should DEMONSTRATE "answers in your language", not claim it."""
    import asyncio

    english = asyncio.run(F.fake_answer("WHO said 5G spreads corona"))
    hindi = asyncio.run(F.fake_answer("डब्ल्यूएचओ ने कहा 5जी से कोरोना फैलता है"))

    assert english.markdown.startswith("**This is false.**")
    assert hindi.markdown.startswith("**यह दावा झूठा है।**")
    assert english.tier == hindi.tier == "trusted"
