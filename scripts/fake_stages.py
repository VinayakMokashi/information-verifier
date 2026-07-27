"""Simulated (FREE) versions of every paid stage.

Shared by scripts/demo_offline.py, scripts/serve_demo.py, and the web E2E
tests: same fakes everywhere, so "the demo works" means the real plumbing
works. Nothing here touches the network.

Two layers of protection, because "free mode quietly spent money" is the
failure that matters: every paid seam is patched (LLM stages, OCR, ASR,
equivalence), AND the real API keys are replaced with obvious dummies, so a
seam we forget to patch fails authentication instead of billing the user.
"""
import os

from app.models.claim import Claim
from app.models.evidence import Evidence, Source
from app.models.verdict import Rating, Verdict

_DUMMY_KEY = "demo-mode-not-a-real-key"

CALLS = {"adjudicate": 0}  # counts simulated adjudications to prove caching


class FakeNorm:
    detected_language = "hi"
    english_text = (
        "The World Health Organization stated that 5G technology spreads the "
        "coronavirus. 5G radiation also weakens the human immune system."
    )


async def fake_normalize(text: str) -> FakeNorm:
    return FakeNorm()


async def fake_extract(english_text: str) -> list[Claim]:
    return [
        Claim(
            text="The World Health Organization stated that 5G technology spreads the coronavirus.",
            subject="World Health Organization",
            claim_type="attribution",
            checkworthy=True,
        ),
        Claim(
            text="5G radiation weakens the human immune system.",
            subject="5G technology",
            claim_type="causal",
            checkworthy=True,
        ),
        Claim(  # non-checkworthy -> pipeline should drop it
            text="People should stay away from 5G towers to be safe.",
            subject="people",
            claim_type="other",
            checkworthy=False,
        ),
    ]


async def fake_gather(claim: Claim) -> Evidence:
    return Evidence(
        summary=(
            "Trusted fact-checkers and the WHO found no link between 5G and COVID-19. "
            "The virus spreads via respiratory droplets, not radio waves."
        ),
        sources=[
            Source(
                url="https://www.boomlive.in/health/5g-coronavirus-fake",
                title="No, 5G Does Not Spread Coronavirus",
                publisher="boomlive.in",
            ),
            Source(
                url="https://www.reuters.com/article/factcheck-5g-covid",
                title="Fact check: 5G does not cause or spread COVID-19",
                publisher="reuters.com",
            ),
        ],
    )


async def fake_adjudicate(claim: Claim, evidence: Evidence) -> Verdict:
    CALLS["adjudicate"] += 1
    return Verdict(
        rating=Rating.FALSE,
        confidence=97,
        reasoning=(
            "Multiple trusted fact-checkers and the WHO confirm there is no link "
            "between 5G and the coronavirus; viruses cannot travel on radio waves."
        ),
        correction=(
            "COVID-19 is caused by the SARS-CoV-2 virus and spreads through "
            "respiratory droplets. 5G is radio-frequency radiation and plays no "
            "role in its transmission."
        ),
        citations=[
            {"url": "https://www.boomlive.in/health/5g-coronavirus-fake",
             "title": "No, 5G Does Not Spread Coronavirus", "publisher": "boomlive.in"},
            {"url": "https://www.reuters.com/article/factcheck-5g-covid",
             "title": "Fact check: 5G does not cause or spread COVID-19", "publisher": "reuters.com"},
        ],
    )


async def fake_ocr(image_bytes: bytes, media_type: str) -> str:
    return "WHO ne kaha hai ki 5G se coronavirus phailta hai. (simulated OCR)"


class FakeTranscript:
    def __init__(self, text: str, language: str | None = None):
        self.text = text
        self.language = language


class FakeASR:
    async def transcribe(self, audio: bytes, language_hint: str | None = None):
        return FakeTranscript("WHO ne kaha hai ki 5G se coronavirus phailta hai.", "hi-IN")


async def fake_equivalent(claim_a: str, claim_b: str) -> bool:
    """Offline stand-in for the Haiku confirm: equal text means equal claim."""
    return " ".join(claim_a.lower().split()) == " ".join(claim_b.lower().split())


def apply_fake_stages() -> None:
    """Patch every paid seam and neutralize the API keys behind them."""
    from app.api import routes as R
    from app.config import settings
    from app.engine import pipeline as P

    P.normalize = fake_normalize
    P.extract_claims = fake_extract
    P.gather_evidence = fake_gather
    P.adjudicate = fake_adjudicate
    P.claims_equivalent = fake_equivalent
    R.ocr_image = fake_ocr
    R.get_asr_provider = lambda: FakeASR()

    # Belt and braces: with dummy keys, any seam that slips through fails
    # auth instead of spending. (Non-empty so routes' "not configured"
    # guards still pass and the demo exercises the real request path.)
    settings.anthropic_api_key = _DUMMY_KEY
    settings.google_factcheck_api_key = _DUMMY_KEY
    settings.sarvam_api_key = _DUMMY_KEY

    # Sarvam and Google read settings at call time, so the lines above cover
    # them. Anthropic does NOT: providers/llm.py builds one client at import,
    # which already happened above, and every stage holds a reference to that
    # same object. Mutating the live client's key is what actually protects
    # the expensive provider; setting `settings` alone does nothing.
    from app.providers import llm

    llm.async_client.api_key = _DUMMY_KEY
    os.environ["ANTHROPIC_API_KEY"] = _DUMMY_KEY  # for any lazily-built client
