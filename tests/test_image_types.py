"""What a picture IS, told by its bytes (2026-11-19). Free — vision is faked.

The image route trusted the type a file was DECLARED as and handed it to
the vision API, which refuses a type that does not match the bytes: a
WebP saved as .jpg, a photo sent as a Telegram file with the wrong name.
That refusal came after the day's slot was taken. An iPhone's HEIC photo
got the generic "doesn't look like a picture", and a scrolling screenshot
taller than the API's 8,000 pixels failed after the slot was taken.
"""
import struct

from app.api import limits, routes as R
from app.config import settings
from app.providers import vision as V


def _png(width=1080, height=2400):
    return (b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
            + struct.pack(">II", width, height) + b"\x08\x06\x00\x00\x00" + b"0" * 64)


def _webp(width=1080, height=1920):
    # The extended (VP8X) header: 24-bit width-1 and height-1.
    return (b"RIFF" + struct.pack("<I", 100) + b"WEBP" + b"VP8X"
            + struct.pack("<I", 10) + b"\x00" * 4
            + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
            + b"0" * 64)


def _jpeg(width=1080, height=2400):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof0 = (b"\xff\xc0" + struct.pack(">H", 17) + b"\x08"
            + struct.pack(">HH", height, width) + b"\x03" + b"\x00" * 9)
    return b"\xff\xd8" + app0 + sof0 + b"0" * 64


HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"0" * 64


def _reading(monkeypatch):
    read = []

    async def ocr(images):
        read.append(list(images))
        return "Image 1: words"

    monkeypatch.setattr(R, "ocr_images", ocr)
    return read


def _post(client, name, data, declared):
    return client.post("/api/v1/verify/image", files={"file": (name, data, declared)})


# -- the bytes decide ----------------------------------------------------------

def test_the_type_read_from_the_bytes_is_what_the_vision_call_is_told(client, monkeypatch):
    read = _reading(monkeypatch)
    resp = _post(client, "saved.jpg", _webp(), "image/jpeg")       # a WebP named .jpg
    assert resp.status_code == 202, resp.text
    assert [t for _, t in read[0]] == ["image/webp"]


def test_a_picture_with_no_declared_type_is_still_read(client, monkeypatch):
    read = _reading(monkeypatch)
    resp = _post(client, "shot", _png(), "application/octet-stream")
    assert resp.status_code == 202, resp.text
    assert [t for _, t in read[0]] == ["image/png"]


def test_bytes_that_are_no_picture_are_refused_whatever_they_are_called(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    read = _reading(monkeypatch)
    resp = _post(client, "notes.png", b"hello, not a picture", "image/png")
    assert resp.status_code == 415
    assert read == [] and limits.used_today() == 0


def test_an_iphone_heic_photo_is_told_what_to_send_instead(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    read = _reading(monkeypatch)
    resp = _post(client, "IMG_0001.HEIC", HEIC, "image/heic")
    assert resp.status_code == 415
    assert "HEIC" in resp.json()["detail"] and "screenshot" in resp.json()["detail"]
    assert read == [] and limits.used_today() == 0


# -- the vision API's own size limit -------------------------------------------

def test_a_picture_taller_than_the_api_reads_is_refused_before_any_spend(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    read = _reading(monkeypatch)
    resp = _post(client, "scroll.png", _png(1080, 9000), "image/png")
    assert resp.status_code == 413
    assert "parts" in resp.json()["detail"]
    assert read == [] and limits.used_today() == 0


def test_a_tall_but_readable_screenshot_goes_through(client, monkeypatch):
    read = _reading(monkeypatch)
    assert _post(client, "tall.png", _png(1080, 8000), "image/png").status_code == 202
    assert len(read) == 1


def test_the_size_is_read_from_every_format_the_api_takes():
    assert V.image_size(_png(1080, 2400)) == (1080, 2400)
    assert V.image_size(_webp(1440, 1800)) == (1440, 1800)
    assert V.image_size(_jpeg(720, 9001)) == (720, 9001)
    gif = b"GIF89a" + struct.pack("<HH", 320, 240) + b"0" * 32
    assert V.image_size(gif) == (320, 240)
    # Unknown, never guessed: the API decides then.
    assert V.image_size(b"\xff\xd8\xff\xd9") is None
    assert V.image_size(b"\x89PNG") is None


def test_the_type_is_read_from_every_format_the_api_takes():
    assert V.image_type(_png()) == "image/png"
    assert V.image_type(_jpeg()) == "image/jpeg"
    assert V.image_type(_webp()) == "image/webp"
    assert V.image_type(b"GIF87a" + b"0" * 10) == "image/gif"
    assert V.image_type(HEIC) is None and V.is_heic(HEIC)
    assert V.image_type(b"%PDF-1.4") is None and not V.is_heic(b"%PDF-1.4")
