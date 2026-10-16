"""What gets installed is what was tested. Free.

docs/research/2026-10-15/audit-ops.md OPS-24, reproduced there: every
requirement was an open lower bound and nothing was locked, so a fresh
install pulled anthropic 1.14.0 — a major release on httpx2 that the app's
SDK patching (providers/usage.instrument) never ran against — and installed
pytest into the running app.
"""
import re
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _lock() -> dict[str, str]:
    pins = {}
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, _, pinned = line.partition("==")
            pins[name.lower().replace("_", "-")] = pinned
    return pins


def test_every_lock_line_is_an_exact_pin():
    for line in (ROOT / "requirements.lock").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            assert re.fullmatch(r"[A-Za-z0-9_.\-]+==[A-Za-z0-9_.+\-]+", line), line


def test_the_lock_is_what_this_suite_is_running_on():
    """Upgrade a package without re-locking (scripts/lock_requirements.py),
    and this fails: the lock must name what was tested."""
    drift = {name: (pinned, version(name)) for name, pinned in _lock().items()
             if version(name) != pinned}
    assert drift == {}


def test_yt_dlp_is_not_frozen_and_pytest_is_not_shipped():
    lock = _lock()
    assert "yt-dlp" not in lock, "yt-dlp must keep up with the platforms (OPS-25)"
    assert "pytest" not in lock
    app = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert not re.search(r"^pytest", app, re.MULTILINE)
    assert "pytest" in (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")


def test_an_unlocked_install_cannot_cross_a_major_version():
    """The caps in requirements.txt: anthropic 1.x is a different HTTP layer."""
    app = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    for package, cap in (("anthropic", "<1"), ("fastapi", "<1"), ("pydantic", "<3"),
                         ("httpx", "<1")):
        line = next(l for l in app.splitlines() if l.startswith(package))
        assert cap in line, line
