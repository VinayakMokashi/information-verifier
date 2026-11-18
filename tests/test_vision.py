"""The vision step: several pictures, ONE bounded paid call. Free — the
Anthropic client is replaced; nothing leaves the machine.

Since 2026-11-18 a post's pictures (and, later, several uploaded images) are
read together. One call keeps one output cap; a call per picture would
multiply it, and invariant 5 wants every paid call bounded before it is made.
"""
import asyncio
from types import SimpleNamespace

from app.providers import vision as V


def _record(monkeypatch, text="Image 1: a\nImage 2: b", stop="end_turn"):
    calls = []

    async def create(**kw):
        calls.append(kw)
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                               stop_reason=stop)

    monkeypatch.setattr(V.async_client.messages, "create", create)
    return calls


def test_several_pictures_are_one_call_under_one_cap(monkeypatch):
    calls = _record(monkeypatch)
    out = asyncio.run(V.ocr_images([(b"a", "image/jpeg"), (b"b", "image/png")]))

    assert len(calls) == 1
    content = calls[0]["messages"][0]["content"]
    assert [c["type"] for c in content] == ["image", "image", "text"]
    assert [c["source"]["media_type"] for c in content[:2]] == ["image/jpeg", "image/png"]
    assert "2 images" in content[-1]["text"]
    assert calls[0]["max_tokens"] == V._OCR_MAX_TOKENS <= 4000
    assert out == "Image 1: a\nImage 2: b"


def test_one_picture_is_asked_exactly_as_before(monkeypatch):
    calls = _record(monkeypatch, text="WHO ne kaha")
    assert asyncio.run(V.ocr_image(b"a", "image/jpeg")) == "WHO ne kaha"
    content = calls[0]["messages"][0]["content"]
    assert len(content) == 2 and content[-1]["text"] == V._OCR_PROMPT


def test_a_reading_cut_off_by_the_cap_says_so(monkeypatch):
    """Invariant 4 shows the reader what was read; a transcription the cap
    cut off must not pass for the whole text."""
    _record(monkeypatch, text="Image 1: the first half", stop="max_tokens")
    out = asyncio.run(V.ocr_images([(b"a", "image/jpeg")]))
    assert out.startswith("Image 1: the first half")
    assert "could not be read" in out
