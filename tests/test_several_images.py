"""Several images in one check (2026-11-18). Free — the vision step is faked.

A friend asked "I cant post multiple images?": the page took one file, and
the bot checked only the first photo of an album, telling the others "Yeh
naya message check nahi hua". Now up to max_images_per_check images go to
ONE vision call (one output cap, invariant 5), and words the person wrote
with them — a Telegram photo's caption — are checked with them.
"""
from app.api import limits, routes as R
from app.config import settings
from app.providers import usage, vision


def _reading(monkeypatch):
    read = []

    async def ocr(images):
        read.append(list(images))
        return "\n".join(f"Image {i}: words {i}" for i in range(1, len(images) + 1))

    monkeypatch.setattr(R, "ocr_images", ocr)
    return read


def _shots(n):
    return [("file", (f"s{i}.png", b"\x89PNG" + bytes([i]), "image/png"))
            for i in range(n)]


def _post(client, files, **data):
    return client.post("/api/v1/verify/image", files=files, data=data)


def _report(client, resp):
    assert resp.status_code == 202, resp.text
    return client.get(f"/api/v1/reports/{resp.json()['job_id']}").json()


def test_several_images_are_read_in_one_call_and_checked_once(client, monkeypatch):
    import scripts.fake_stages as F

    read = _reading(monkeypatch)
    report = _report(client, _post(client, _shots(3)))

    assert report["status"] == "COMPLETE"
    assert len(read) == 1 and len(read[0]) == 3            # one paid reading
    assert [t for _, t in read[0]] == ["image/png"] * 3
    assert "Image 3: words 3" in report["source_text"]     # shown back
    assert F.CALLS["answer"] == 1                          # one check


def test_one_image_is_still_one_image(client, monkeypatch):
    read = _reading(monkeypatch)
    _report(client, _post(client, {"file": ("a.png", b"\x89PNG", "image/png")}))
    assert len(read[0]) == 1


def test_more_than_the_cap_is_refused_before_anything_is_read(client, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    limits.reset()
    read = _reading(monkeypatch)

    resp = _post(client, _shots(settings.max_images_per_check + 1))

    assert resp.status_code == 413
    assert str(settings.max_images_per_check) in resp.json()["detail"]
    assert read == [] and limits.used_today() == 0         # nothing bought, nothing kept


def test_an_image_past_the_apis_own_limit_is_refused_before_reading(client, monkeypatch):
    """Past the API's 10 MB (base64) a check failed AFTER the slot was taken."""
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "max_image_bytes", 1000)
    limits.reset()
    read = _reading(monkeypatch)

    resp = _post(client, {"file": ("big.png", b"\x89PNG" + b"0" * 2000, "image/png")})

    assert resp.status_code == 413 and read == []
    assert limits.used_today() == 0


def test_one_file_that_is_not_an_image_refuses_them_all(client, monkeypatch):
    read = _reading(monkeypatch)
    files = _shots(1) + [("file", ("notes.txt", b"hello", "text/plain"))]
    assert _post(client, files).status_code == 415 and read == []


def test_the_persons_own_words_go_with_the_images(client, monkeypatch):
    """A photo's caption can be the claim itself: a real photo, from the
    wrong flood."""
    _reading(monkeypatch)
    report = _report(client, _post(client, _shots(1),
                                   note="Yeh kal Mumbai ki baadh ki photo hai"))
    assert "Yeh kal Mumbai ki baadh ki photo hai" in report["source_text"]
    assert "Image 1: words 1" in report["source_text"]


def test_a_note_longer_than_a_telegram_caption_is_refused_before_reading(client, monkeypatch):
    """The note is a photo's caption; Telegram's own limit is 1,024. Longer,
    it would only push the pictures' text past the engine's bound."""
    read = _reading(monkeypatch)
    assert _post(client, _shots(1), note="x" * 1025).status_code == 422
    assert read == []
    assert _report(client, _post(client, _shots(1), note="x" * 1024))["status"] == "COMPLETE"


def test_the_page_lets_a_person_pick_several_images_and_sends_them_all():
    import re
    from pathlib import Path

    page = (Path(__file__).resolve().parent.parent / "static" / "index.html"
            ).read_text(encoding="utf-8")
    picker = re.search(r'<input type="file" id="image"[^>]*>', page)
    assert picker and "multiple" in picker.group(0)
    voice = re.search(r'<input type="file" id="media"[^>]*>', page)
    assert voice and "multiple" not in voice.group(0)     # one voice note at a time
    # Every picked file goes, each as a "file" part, to the one route.
    assert "[...$(inputId).files]" in page
    assert 'fd.append("file", f)' in page


def test_the_image_reservation_covers_the_most_images_read_at_once():
    """Reserved before any spend, it must cover the worst case (config's
    rule): every image at Sonnet 5's high resolution (4,784 tokens), the
    reading's whole output cap, and the dearest check measured (~$0.19)."""
    price = usage._PRICES[settings.vision_model]
    reading = (settings.max_images_per_check * 4784 * price["in"]
               + vision._OCR_MAX_TOKENS * price["out"]) / 1e6
    assert settings.budget_reserve_usd["image"] >= reading + 0.19
