"""The page installs as an app: a manifest, its icons, no service worker. Free.

Step 5 of the launch (docs/research/2026-10-15/pwa-app.md, verified): Chrome
installs a site with HTTPS, a manifest with name/short_name, icons at 192 and
512 px, start_url, a standalone display and an explicit id — and no longer
needs a service worker. None is shipped on purpose: a service worker that
caches the page serves a stale one after every deploy. iOS ignores the
install prompt and maskable icons, and uses an apple-touch-icon instead.
A reel shared into the installed app (Android's share sheet) only FILLS the
box: the person still taps Check, so every limit still applies.
"""
import json
import struct
from pathlib import Path

import pytest

_STATIC = Path(__file__).resolve().parent.parent / "static"
PAGE = (_STATIC / "index.html").read_text(encoding="utf-8")


def _manifest() -> dict:
    return json.loads((_STATIC / "manifest.webmanifest").read_text(encoding="utf-8"))


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    return struct.unpack(">II", head[16:24])


def test_the_manifest_is_served_as_a_manifest(client):
    """StaticFiles takes the type from Python's mimetypes, which on Windows
    the registry can override (pwa-app.md F10) — so pin what is served."""
    resp = client.get("/manifest.webmanifest")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")
    assert resp.json()["name"] == "Information Verifier"


def test_the_manifest_has_what_chrome_installs_from():
    m = _manifest()
    assert m["id"] == "/" and m["start_url"] == "/" and m["scope"] == "/"
    assert m["display"] == "standalone"
    assert m["name"] and 0 < len(m["short_name"]) <= 12   # fits under a launcher icon
    assert m["background_color"] and m["theme_color"]
    assert "prefer_related_applications" not in m


def test_the_icons_are_there_at_the_sizes_the_manifest_names():
    icons = _manifest()["icons"]
    wanted = {("192x192", "any"), ("512x512", "any"), ("512x512", "maskable")}
    assert {(i["sizes"], i.get("purpose", "any")) for i in icons} == wanted
    for icon in icons:
        assert icon["type"] == "image/png"
        width, height = map(int, icon["sizes"].split("x"))
        assert _png_size(_STATIC / icon["src"]) == (width, height), icon["src"]


@pytest.mark.parametrize("path", ["/icon-192.png", "/icon-512.png",
                                  "/icon-maskable-512.png", "/apple-touch-icon.png"])
def test_the_icons_are_served_as_images(client, path):
    resp = client.get(path)
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/png"


def test_the_page_links_the_manifest_and_the_ios_icon():
    assert '<link rel="manifest" href="manifest.webmanifest">' in PAGE
    assert '<link rel="apple-touch-icon" href="apple-touch-icon.png">' in PAGE
    assert _png_size(_STATIC / "apple-touch-icon.png") == (180, 180)
    assert '<link rel="icon" href="icon.svg" type="image/svg+xml">' in PAGE
    assert (_STATIC / "icon.svg").read_text(encoding="utf-8").startswith("<svg")
    assert PAGE.count('<meta name="theme-color"') == 2      # light and dark


def test_no_service_worker_is_registered():
    """Decided (pwa-app.md): none. Installing no longer needs one, and one
    that caches the page would serve the old page after a deploy."""
    assert "serviceWorker" not in PAGE


def test_the_install_button_appears_only_when_it_can_work():
    assert 'id="install"' in PAGE
    button = PAGE[PAGE.index('id="install"') - 80:PAGE.index('id="install"') + 80]
    assert "hidden" in button                                # hidden until...
    assert '"beforeinstallprompt"' in PAGE                   # ...Chrome offers it,
    assert "display-mode: standalone" in PAGE                # never once installed
    assert 'id="iosHint"' in PAGE and "Add to Home Screen" in PAGE   # iOS: say how


def test_on_ios_only_a_browser_that_can_install_shows_the_button():
    """Review S5-15: links travel by Telegram and WhatsApp, and an iPhone
    opens them in that app's own browser, which has no Add to Home Screen —
    yet the button showed there (only Instagram's and Facebook's were known).
    Safari, Chrome and Firefox for iOS all carry "Safari/" in their user
    agent; a bare in-app web view does not."""
    start = PAGE.index("const IOS =")
    ios = PAGE[start:PAGE.index("$(\"install\").addEventListener", start)]
    assert "Safari\\/" in ios, "the iOS button does not ask for a real browser"
    assert "Open this page in Safari" in PAGE   # for in-app browsers that pass as Safari


def test_a_share_fills_the_box_and_never_sends_it():
    m = _manifest()["share_target"]
    assert m["action"] == "/" and m["method"] == "GET"
    # Without it Chrome's manifest parser warns (measured over DevTools).
    assert m["enctype"] == "application/x-www-form-urlencoded"
    assert m["params"] == {"title": "title", "text": "text", "url": "url"}
    start = PAGE.index("function takeShared(")
    share = PAGE[start:PAGE.index("\n}", start)]
    assert "box.value =" in share
    for sends in ("submit(", ".click()", "fetch("):
        assert sends not in share, f"a share would {sends} on its own"
    # Read once, then gone from the address bar: a reload must not refill
    # the box over whatever the person typed since.
    assert "history.replaceState" in share
