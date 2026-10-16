"""What the server writes down: nobody's address or post, and nothing lost to a buffer. Free.

docs/research/2026-10-15/audit-ops.md:
- OPS-11: uvicorn's access log printed every visitor's IP and every job id,
  and a job id opens that person's message through GET /reports — replaying
  a logged id returned "My sister Priya (ward 14, Pune) says...". The app's
  own prints named the exact reel ("transcript cache hit for
  v2:instagram:<id>") and copied yt-dlp's error text, URL and post id
  included.
- OPS-08: one worker was only the default; WEB_CONCURRENCY changes it.
- OPS-20: piped (a service manager, a log file), stdout is block-buffered:
  diagnostics arrived hours late, and a killed process lost them.
"""
import os
import subprocess
import sys
import textwrap
import threading
from pathlib import Path

import pytest

from app.providers.links import log_safe

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("raw", [
    "ERROR: [Instagram] ABCdef123: Unable to download webpage: "
    "https://www.instagram.com/reel/ABCdef123/?igsh=c2VjcmV0",
    "ERROR: [youtube] dQw4w9WgXcQ: Video unavailable",
    "Client error '404' for url 'https://www.facebook.com/share/r/1Ab2Cd3E/'",
])
def test_a_platform_error_is_logged_without_its_post(raw):
    safe = log_safe(raw)
    for secret in ("ABCdef123", "dQw4w9WgXcQ", "1Ab2Cd3E", "https://", "igsh"):
        assert secret not in safe
    assert safe                                      # still says what happened


def test_a_cached_transcript_is_logged_by_platform_not_by_post(client, monkeypatch, capsys):
    import app.api.routes as R

    def cached(key):                 # synchronous, like the real one (it runs in a thread)
        return "WHO ne kaha 5G se corona phailta hai"

    monkeypatch.setattr(R._repo.transcripts, "get", cached)
    resp = client.post("/api/v1/verify/link",
                       json={"url": "https://www.youtube.com/watch?v=jjjjjjjjjjj"})
    assert resp.status_code == 202
    out = capsys.readouterr().out
    assert "transcript cache hit" in out
    # The fake link's id is FAKE-REEL-1, and the cache key is "v2:<platform>:<id>".
    assert "FAKE-REEL" not in out and "v2:" not in out


@pytest.mark.parametrize("name, workers", [
    ("start.ps1", "--workers 1"),
    ("scripts/share_demo.ps1", '"--workers", "1"'),
])
def test_the_launchers_run_one_worker_unbuffered_and_without_an_access_log(name, workers):
    text = (ROOT / name).read_text(encoding="utf-8")
    assert workers in text
    assert "--no-access-log" in text
    assert "PYTHONUNBUFFERED" in text


def test_a_startup_line_reaches_a_piped_log_at_once(tmp_path):
    """The audit's reproduction: the server with stdout PIPED, as a service
    manager runs it, its startup line read at once — not after 8 KB more,
    and not never, when the process is killed. No PYTHONUNBUFFERED here: the
    app must not depend on whoever starts it remembering it."""
    child = textwrap.dedent("""
        import sys, time
        sys.path.insert(0, sys.argv[1])
        from fastapi.testclient import TestClient
        from app.main import app
        with TestClient(app):
            time.sleep(30)
    """)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONUNBUFFERED"}
    env["DB_PATH"] = str(tmp_path / "piped.db")
    proc = subprocess.Popen([sys.executable, "-c", child, str(ROOT)], cwd=tmp_path,
                            env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace")
    first = []
    reader = threading.Thread(target=lambda: first.append(proc.stdout.readline()),
                              daemon=True)
    reader.start()
    reader.join(20)
    proc.kill()
    proc.wait(10)
    assert first and "[startup]" in first[0], "the startup line was held in a buffer"
