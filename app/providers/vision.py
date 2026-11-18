"""Image OCR via Claude's vision (settings.vision_model) — no Tesseract.

WhatsApp memes carry overlaid Devanagari/Tamil/Bengali typography on
recompressed low-res images; a general OCR engine mangles them. Vision
reads the text AND the visual context (the chart, the doctored photo,
the caption) in a single pass, which is exactly what a meme needs.

Several pictures (a post's carousel, 2026-11-18) are read in ONE call: one
bounded answer, where a call per picture would multiply the output cap.
"""
import base64

from app.config import settings
from app.providers.llm import async_client

_OCR_PROMPT = (
    "Transcribe ALL text visible in this image exactly as written, including "
    "text in Hindi, Marathi, Tamil, Bengali, or other Indian scripts and any "
    "overlaid meme/caption text. Then, in one sentence, describe any photo, "
    "chart, or visual that itself makes a factual claim (e.g. a graph, a "
    "screenshot, a doctored image). Output only the transcription followed by "
    "that one-sentence description. Do not interpret or fact-check anything."
)

_OCR_MANY_PROMPT = (
    "These are {n} images, in the order they were posted. For EACH one, write "
    "'Image k:' on its own line (k from 1 to {n}), then transcribe ALL text "
    "visible in it exactly as written, including text in Hindi, Marathi, "
    "Tamil, Bengali, or other Indian scripts and any overlaid meme/caption "
    "text, then in one sentence describe any photo, chart, or visual in it "
    "that itself makes a factual claim (e.g. a graph, a screenshot, a doctored "
    "image). Output only that. Do not interpret or fact-check anything."
)

# The whole answer, however many images: the bound on the paid call.
_OCR_MAX_TOKENS = 4000
# Shown with the text when the cap cut it short (invariant 4: what was read
# is shown back, and a cut-off transcription must not pass for a whole one).
_CUT_SHORT = "\n[…the rest of the text could not be read]"


async def ocr_images(images: list[tuple[bytes, str]]) -> str:
    """[(bytes, media type), ...] -> what they say, in one call."""
    prompt = (_OCR_PROMPT if len(images) == 1
              else _OCR_MANY_PROMPT.format(n=len(images)))
    content = [
        {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type,
                       "data": base64.standard_b64encode(data).decode("utf-8")},
        }
        for data, media_type in images
    ]
    content.append({"type": "text", "text": prompt})
    resp = await async_client.messages.create(
        model=settings.vision_model,
        max_tokens=_OCR_MAX_TOKENS,
        messages=[{"role": "user", "content": content}],
    )
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    if text and resp.stop_reason == "max_tokens":
        text += _CUT_SHORT
    return text


async def ocr_image(image_bytes: bytes, media_type: str) -> str:
    return await ocr_images([(image_bytes, media_type)])
