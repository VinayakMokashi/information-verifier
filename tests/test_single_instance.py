"""One server per database: a second copy refuses BEFORE it touches anyone's checks. Free.

docs/research/2026-10-15/audit-ops.md OPS-05, reproduced there
(second_instance.py): uvicorn runs the lifespan (init_db + sweep_orphans)
BEFORE it binds its port, so any second start against the same database —
share_demo.ps1 in REAL mode, a hand-run uvicorn, a TestClient-based script
such as link_smoke.py — marked every in-flight check FAILED ("The server
restarted while this check was running"), then died on "address already in
use". The bot relayed that failure for a check that still completed, was
billed, and was never delivered.
"""
import os
import subprocess
import sys
import textwrap
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.models.answer import Answer, JobStatus
from app.store.db import init_db
from app.store.repository import AnswerRepository

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The FIRST copy, as another process. Before the lock existed there was
# nothing to hold — the row below is simply "running" — which is exactly the
# situation the second copy used to sweep.
_FIRST_COPY = textwrap.dedent("""
    import sys, time
    sys.path.insert(0, sys.argv[2])
    try:
        from app.store import instance
        instance.acquire(sys.argv[1])
    except ImportError:
        pass
    print("running", flush=True)
    time.sleep(60)
""")


def _first_copy(db):
    first = subprocess.Popen([sys.executable, "-c", _FIRST_COPY, db, _REPO_ROOT],
                             stdout=subprocess.PIPE, text=True)
    assert first.stdout.readline().strip() == "running"
    return first


def test_a_second_copy_never_fails_the_first_copys_checks(tmp_path, monkeypatch, capsys):
    from app.main import app

    db = str(tmp_path / "shared.db")
    monkeypatch.setattr(settings, "db_path", db)
    init_db()
    running = Answer(job_id=uuid.uuid4().hex, status=JobStatus.PROCESSING,
                     created_at=datetime.now(timezone.utc),
                     input_text="a check the first copy is running")
    AnswerRepository().save(running)
    first = _first_copy(db)
    try:
        refused = False
        try:
            with TestClient(app):
                pass
        except Exception:  # noqa: BLE001 — a refused startup is the point
            refused = True
        assert AnswerRepository().get(running.job_id).status is JobStatus.PROCESSING, \
            "the second copy failed the first copy's running check"
        assert refused, "the second copy started anyway"
        assert "already running" in capsys.readouterr().out
    finally:
        first.kill()
        first.wait(10)


def test_once_the_first_copy_is_gone_the_next_starts(tmp_path, monkeypatch):
    """The lock is the OS's, held by an open file: it dies with its process,
    so a crash can never leave the app unable to start."""
    from app.main import app

    db = str(tmp_path / "shared.db")
    monkeypatch.setattr(settings, "db_path", db)
    init_db()
    first = _first_copy(db)
    first.kill()
    first.wait(10)
    with TestClient(app) as c:
        assert c.get("/health").status_code == 200


def test_the_same_process_may_open_the_app_twice(client):
    """Tests (and nothing else) open nested TestClients on one database: the
    lock is per process, so the second lifespan in the SAME process passes."""
    from app.main import app

    with TestClient(app) as again:
        assert again.get("/health").status_code == 200
