"""Simulated (FREE) versions of every paid seam.

Shared by scripts/demo_offline.py, scripts/serve_demo.py and the web E2E
tests: the same fakes everywhere, so "the demo works" means the real plumbing
works. Nothing here touches the network.

Two layers of protection, because "free mode quietly spent money" is the
failure that actually happened once: every paid seam is patched, AND the real
API keys are replaced with obvious dummies, so a seam we forget to patch
fails authentication instead of billing the user.
"""
import os
import re

from app.engine.chat import ChatAnswer
from app.models.answer import AnswerSection, Source
from app.providers.links import LinkInfo

_DUMMY_KEY = "demo-mode-not-a-real-key"

CALLS = {"answer": 0}  # counts simulated engine calls, to prove caching

# Devanagari in -> Devanagari out, so the demo DEMONSTRATES the "answers in
# your language" promise instead of claiming it.
_DEVANAGARI = re.compile(r"[ऀ-ॿ]")

_ANSWER_EN = (
    "**This is false.** 5G radio waves cannot carry or spread a virus.\n\n"
    "Alt News and BOOM both checked this claim when it went viral, and the "
    "World Health Organization has said plainly that COVID-19 spreads through "
    "respiratory droplets, not radio signals. The two are unrelated: 5G is "
    "non-ionising radio-frequency radiation, and a virus needs a physical "
    "host to travel.\n\n"
    "Worth knowing why this one spread so well — 5G rollouts and the pandemic "
    "overlapped in time, and coincidence reads a lot like cause when you are "
    "frightened."
)
_ANSWER_HI = (
    "**यह दावा झूठा है।** 5जी की रेडियो तरंगें किसी वायरस को नहीं फैला सकतीं।\n\n"
    "ऑल्ट न्यूज़ और बूम, दोनों ने यह दावा वायरल होने पर जाँचा था, और विश्व "
    "स्वास्थ्य संगठन ने साफ़ कहा है कि कोविड-19 साँस की बूँदों से फैलता है, "
    "रेडियो तरंगों से नहीं। 5जी रेडियो-फ़्रीक्वेंसी विकिरण है, और वायरस को "
    "फैलने के लिए एक शरीर चाहिए — दोनों का आपस में कोई संबंध नहीं।\n\n"
    "यह अफ़वाह इसलिए फैली क्योंकि 5जी की शुरुआत और महामारी एक ही समय पर हुए। "
    "डर में इत्तेफ़ाक़ भी वजह जैसा लगने लगता है।"
)

_FAKE_SOURCES = [
    Source(url="https://www.boomlive.in/health/5g-coronavirus-fake",
           title="No, 5G Does Not Spread Coronavirus", publisher="BOOM",
           tier="trusted", via="search",
           cited_text="There is no link between 5G and the coronavirus."),
    Source(url="https://www.who.int/health-topics/coronavirus",
           title="Coronavirus disease (COVID-19)", publisher="WHO",
           tier="trusted", via="search"),
    Source(url="https://www.altnews.in/5g-covid-viral-claim/",
           title="Viral claim linking 5G to COVID-19 is false",
           publisher="Alt News", tier="trusted", via="factcheck"),
]


async def fake_answer(text, *, heard=None, emit=None):
    """Offline stand-in for the whole chat engine. No network, no spend.

    Streams the canned answer in word-sized pieces on purpose: the demo then
    exercises the page's incremental rendering, the status line and the
    arriving sources, rather than one atomic blob that would hide every
    streaming bug we have.
    """
    CALLS["answer"] += 1
    body = _ANSWER_HI if _DEVANAGARI.search(f"{text} {heard or ''}") else _ANSWER_EN

    if emit:
        await emit("status", {"text": "Checking trusted fact-checkers…"})
        for piece in re.findall(r"\S+\s*", body):   # keep whitespace: markdown
            await emit("text", {"text": piece, "tier": "trusted"})
        for source in _FAKE_SOURCES:
            await emit("source", source.model_dump())

    return ChatAnswer(
        sections=[AnswerSection(tier="trusted", markdown=body)],
        sources=list(_FAKE_SOURCES),
        confidence=95,
        tier="trusted",
    )


async def fake_ocr(image_bytes: bytes, media_type: str) -> str:
    return "WHO ne kaha hai ki 5G se coronavirus phailta hai. (simulated OCR)"


class FakeTranscript:
    def __init__(self, text: str, language: str | None = None):
        self.text = text
        self.language = language


class FakeASR:
    async def transcribe(self, audio: bytes, language_hint: str | None = None):
        return FakeTranscript("WHO ne kaha hai ki 5G se coronavirus phailta hai.",
                              "hi-IN")


def fake_resolve_link(url: str) -> LinkInfo:
    """Offline stand-in for yt-dlp resolve — no network. Any allowlisted URL
    'resolves' to a small reel with a caption and no subtitles."""
    return LinkInfo(
        url=url,
        platform="Instagram (simulated)",
        video_id="FAKE-REEL-1",
        title="Video by demo",
        uploader="demo",
        duration=None,        # mirrors the real Instagram finding: unknown
        caption="(simulated caption) WHO ne kaha 5G se corona phailta hai",
        has_media=True,
        subtitle=None,
    )


async def fake_gather_link_text(info) -> str:
    """Offline stand-in for the whole fetch half (subtitles/download/ASR)."""
    return ("(simulated caption) WHO ne kaha 5G se corona phailta hai\n\n"
            "WHO ne kaha hai ki 5G se coronavirus phailta hai. (simulated reel)")


def apply_fake_stages() -> None:
    """Patch every paid seam and neutralize the API keys behind them."""
    from app.api import routes as R
    from app.config import settings
    from app.engine import chat as C

    # One engine seam now, where there used to be six pipeline stages.
    C.answer = fake_answer
    R.ocr_image = fake_ocr
    R.get_asr_provider = lambda: FakeASR()
    # The link path: resolve touches the network (free but online — a demo
    # must be fully offline) and gather can reach paid Sarvam. Both faked.
    R.resolve_link = fake_resolve_link
    R.gather_link_text = fake_gather_link_text

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
