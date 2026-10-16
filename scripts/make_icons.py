"""Draw the app's icons: one drawing, rendered to every size the app names.

Free and local. Headless Chrome (or Edge) does the rendering: Pillow is not
installed and is not needed. Run it after changing the drawing; it rewrites
static/icon.svg (the favicon), the manifest's three PNGs and the iOS icon,
then checks each PNG's real size.

    .venv\\Scripts\\python.exe scripts\\make_icons.py

pwa-app.md (2026-10-15) has why these four: Chrome installs from 192 and 512
px icons and wants a maskable one for Android's launcher shapes; iOS ignores
both and uses a 180 px apple-touch-icon.
"""
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.render import force_utf8_stdout  # noqa: E402

_STATIC = Path(__file__).resolve().parent.parent / "static"
_ACCENT = "#1d4ed8"                       # the page's --accent, light theme

# A magnifying glass with a tick in its lens, on a 512 grid. The handle is
# as thick as the ring and starts on the ring's centre line, so its round
# cap hides inside the ring: a thicker handle's cap poked out of the joint.
_GLYPH = ('<g fill="none" stroke="#fff" stroke-linecap="round" stroke-linejoin="round">'
          '<circle cx="220" cy="220" r="120" stroke-width="44"/>'
          '<path d="M305 305L404 404" stroke-width="44"/>'
          '<path d="M168 222L206 260L276 186" stroke-width="34"/>'
          '</g>')

# name: (pixels, rounded corners?, glyph scale)
_ICONS = {
    # "any": shown as drawn, so the corners are rounded and transparent.
    "icon-192.png": (192, True, 1.0),
    "icon-512.png": (512, True, 1.0),
    # Maskable: the launcher cuts its own shape and keeps only the central
    # circle of 80% — so full-bleed, with the glyph well inside that circle.
    "icon-maskable-512.png": (512, False, 0.72),
    # iOS rounds the corners itself and shows transparency as black.
    "apple-touch-icon.png": (180, False, 0.8),
}

_BROWSERS = (r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def svg(*, rounded: bool = True, scale: float = 1.0, size: int | None = None) -> str:
    background = (f'<rect width="512" height="512" rx="112" fill="{_ACCENT}"/>' if rounded
                  else f'<rect width="512" height="512" fill="{_ACCENT}"/>')
    glyph = _GLYPH if scale == 1.0 else (
        f'<g transform="translate(256 256) scale({scale}) translate(-256 -256)">'
        f'{_GLYPH}</g>')
    sized = f' width="{size}" height="{size}"' if size else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg"{sized} viewBox="0 0 512 512">'
            f'{background}{glyph}</svg>')


def png_size(path: Path) -> tuple[int, int]:
    head = Path(path).read_bytes()[:24]
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", head[16:24])


def _browser() -> str:
    for candidate in (shutil.which("chrome"), shutil.which("msedge"), *_BROWSERS):
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("No Chrome or Edge found to render the icons with.")


def _render(browser: str, drawing: str, size: int, out: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        page = Path(tmp) / "icon.html"
        page.write_text('<!doctype html><html><body style="margin:0;background:transparent">'
                        f'<div style="display:block;line-height:0">{drawing}</div>'
                        '</body></html>', encoding="utf-8")
        subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                        "--default-background-color=00000000",
                        "--force-device-scale-factor=1", f"--window-size={size},{size}",
                        f"--screenshot={out}", page.as_uri()],
                       check=True, capture_output=True, timeout=120)
    if png_size(out) != (size, size):
        raise SystemExit(f"{out.name} came out {png_size(out)}, not {size}x{size}")


def main() -> int:
    force_utf8_stdout()
    browser = _browser()
    (_STATIC / "icon.svg").write_text(svg() + "\n", encoding="utf-8")
    print("icon.svg")
    for name, (size, rounded, scale) in _ICONS.items():
        out = _STATIC / name
        _render(browser, svg(rounded=rounded, scale=scale, size=size), size, out)
        print(f"{name}: {png_size(out)[0]}x{png_size(out)[1]}, {out.stat().st_size} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
