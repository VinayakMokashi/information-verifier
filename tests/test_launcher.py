"""The one-click launcher (start.ps1 + start.cmd). Free: never runs it.

Run for real on 2026-10-10: start.cmd with the app and bot already up
(started nothing), the demo guard (refused), and the fresh start through a
copy moved to port 8010 with a stand-in bot (both windows, app up in 8 s).
These pin what breaks silently.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _non_ascii_offset(path: Path) -> int | None:
    for i, byte in enumerate(path.read_bytes()):
        if byte > 127:
            return i
    return None


@pytest.mark.parametrize("name", ["start.ps1", "start.cmd"])
def test_the_launcher_is_plain_ascii(name):
    """Windows PowerShell 5.1 reads a .ps1 without a BOM as ANSI: one em dash
    in a printed string comes out as mojibake (share_demo.ps1's header shows
    it), and a curly quote can change how a line parses."""
    assert _non_ascii_offset(ROOT / name) is None


def test_the_ascii_check_does_catch_a_non_ascii_file():
    # share_demo.ps1 has an em dash in its header comment.
    assert _non_ascii_offset(ROOT / "scripts" / "share_demo.ps1") is not None


@pytest.mark.skipif(not shutil.which("powershell.exe"), reason="needs Windows PowerShell")
def test_the_launcher_parses():
    path = str(ROOT / "start.ps1").replace("'", "''")
    probe = ("$errors = $null; "
             "[void][System.Management.Automation.Language.Parser]::ParseFile("
             f"'{path}', [ref]$null, [ref]$errors); $errors.Count")
    out = subprocess.run(["powershell.exe", "-NoProfile", "-Command", probe],
                         capture_output=True, text=True, timeout=120)
    assert out.stdout.strip() == "0", out.stdout + out.stderr


def test_the_launcher_runs_the_app_the_way_it_must_run():
    """One worker (the stream registry and the rate limiter are in memory) —
    EXPLICITLY since 2026-10-16: the default is only a default, and
    WEB_CONCURRENCY changes it (audit-ops OPS-08) — and no auto-reload (a
    saved file would restart a check mid-answer)."""
    text = (ROOT / "start.ps1").read_text(encoding="ascii")
    assert "-m uvicorn app.main:app --workers 1" in text
    assert "--reload" not in text and "--workers 2" not in text
    assert "serve_demo" in text           # the guard against fake answers
