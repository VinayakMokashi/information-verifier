"""Image OCR via Claude's vision (settings.vision_model) — no Tesseract.

WhatsApp memes carry overlaid Devanagari/Tamil/Bengali typography on
recompressed low-res images; a general OCR engine mangles them. Vision
reads the text AND the visual context (the chart, the doctored photo,
the caption) in a single pass, which is exactly what a meme needs.

Several pictures (a post's carousel, 2026-11-18) are read in ONE call: one
bounded answer, where a call per picture would multiply the output cap.
"""
import base64
import struct

from app.config import settings
from app.providers.llm import async_client

# The four types the vision API reads, told by the bytes themselves
# (2026-11-19): a file's name and declared type can be wrong (a WebP saved
# as .jpg, a photo sent as a Telegram file), and the API refuses a declared
# type that does not match what it is sent — after the day's slot is taken.
_SIGNATURES = ((b"\xff\xd8", "image/jpeg"), (b"\x89PNG", "image/png"),
               (b"GIF87a", "image/gif"), (b"GIF89a", "image/gif"))
# Apple's HEIC/HEIF (and AVIF): an ISO 'ftyp' box naming one of these brands.
_HEIF_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis",
                b"mif1", b"msf1", b"avif"}
# JPEG start-of-frame markers, the ones that carry the picture's size.
_JPEG_FRAMES = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def image_type(data: bytes) -> str | None:
    """The media type the bytes are, if the vision API reads it."""
    for head, media_type in _SIGNATURES:
        if data.startswith(head):
            return media_type
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def is_heic(data: bytes) -> bool:
    return data[4:8] == b"ftyp" and data[8:12] in _HEIF_BRANDS


def image_size(data: bytes) -> tuple[int, int] | None:
    """(width, height) from the header; None when it cannot be told, and
    then the API decides."""
    kind = image_type(data)
    try:
        if kind == "image/png" and data[12:16] == b"IHDR":
            return struct.unpack(">II", data[16:24])
        if kind == "image/gif":
            return struct.unpack("<HH", data[6:10])
        if kind == "image/webp":
            chunk = data[12:16]
            if chunk == b"VP8X":
                return (int.from_bytes(data[24:27], "little") + 1,
                        int.from_bytes(data[27:30], "little") + 1)
            if chunk == b"VP8 ":
                width, height = struct.unpack("<HH", data[26:30])
                return width & 0x3FFF, height & 0x3FFF
            if chunk == b"VP8L":
                bits = int.from_bytes(data[21:25], "little")
                return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == "image/jpeg":
            at = 2
            while at + 4 <= len(data):
                if data[at] != 0xFF:
                    return None
                marker = data[at + 1]
                if marker == 0xFF:                      # fill byte
                    at += 1
                    continue
                if marker == 0x01 or 0xD0 <= marker <= 0xD9:   # no length
                    at += 2
                    continue
                if marker in _JPEG_FRAMES:
                    height, width = struct.unpack(">HH", data[at + 5:at + 9])
                    return width, height
                at += 2 + struct.unpack(">H", data[at + 2:at + 4])[0]
    except struct.error:
        return None
    return None

_OCR_PROMPT = (
    "Transcribe ALL text visible in this image exactly as written, including "
    "text in Hindi, Marathi, Tamil, Bengali, or other Indian scripts and any "
    "overlaid meme/caption text. Then, in one sentence, describe any photo, "
    "chart, or visual that itself makes a factual claim (e.g. a graph, a "
    "screenshot, a doctored image). Output only the transcription followed by "
    "that one-sentence description. Do not interpret or fact-check anything."
)

# The visual sentence is asked for only where there is a visual: MEASURED
# 2026-11-19, five text slides each got "No photo, chart, or visual is
# present in this image; …", shown back to the reader as what was read.
_OCR_MANY_PROMPT = (
    "These are {n} images, in the order they were posted. For EACH one, write "
    "'Image k:' on its own line (k from 1 to {n}), then transcribe ALL text "
    "visible in it exactly as written, including text in Hindi, Marathi, "
    "Tamil, Bengali, or other Indian scripts and any overlaid meme/caption "
    "text, then in one sentence describe any photo, chart, or visual in it "
    "that itself makes a factual claim (e.g. a graph, a screenshot, a doctored "
    "image). For an image that is only text, say nothing about visuals. "
    "Output only that. Do not interpret or fact-check anything."
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
