"""Image OCR via Opus 4.8 vision — no Tesseract.

WhatsApp memes carry overlaid Devanagari/Tamil/Bengali typography on
recompressed low-res images; a general OCR engine mangles them. Vision
reads the text AND the visual context (the chart, the doctored photo,
the caption) in a single pass, which is exactly what a meme needs.
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


async def ocr_image(image_bytes: bytes, media_type: str) -> str:
    b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
    resp = await async_client.messages.create(
        model=settings.opus_model,
        max_tokens=4000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": b64},
                    },
                    {"type": "text", "text": _OCR_PROMPT},
                ],
            }
        ],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()
