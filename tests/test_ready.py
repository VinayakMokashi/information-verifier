"""/ready says whether a check would actually work here; /health only that the process answers. Free.

docs/research/2026-10-15/audit-ops.md OPS-18 (and PROJECT_PLAN §11 19): /health
was a constant {"status": "ok"}, so start.ps1's probe, the bot's startup
check and any uptime monitor all accepted an instance whose database was
locked, whose thread pool was starved (the audit measured /health at 10 ms
while /reports took 19 s), that was started without its keys — or that was
the free DEMO server, which the bot would then wire to people as if real.
"""
import asyncio
import time

import pytest

import app.main as M
from app.config import settings


@pytest.fixture()
def everything_present(monkeypatch):
    monkeypatch.setattr(M.shutil, "which", lambda name: f"C:/tools/{name}.exe")


def test_a_working_app_is_ready_and_says_it_is_real(client, everything_present):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "mode": "real",
                           "checks": {"database": True, "keys": True, "ffmpeg": True}}


def test_no_key_is_not_ready(client, everything_present, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    resp = client.get("/ready")
    assert resp.status_code == 503 and resp.json()["checks"]["keys"] is False


def test_no_ffmpeg_is_not_ready(client, monkeypatch):
    monkeypatch.setattr(M.shutil, "which", lambda name: None)
    resp = client.get("/ready")
    assert resp.status_code == 503 and resp.json()["checks"]["ffmpeg"] is False


def test_a_database_that_cannot_be_written_is_not_ready(client, everything_present,
                                                        monkeypatch):
    def locked():
        raise RuntimeError("database is locked")

    monkeypatch.setattr(M, "_probe_database", locked)
    resp = client.get("/ready")
    assert resp.status_code == 503 and resp.json()["checks"]["database"] is False


def test_a_starved_pool_is_not_ready_and_says_so_in_time(client, everything_present,
                                                         monkeypatch):
    """The probe runs where /reports runs — asyncio's default pool — with a
    deadline: a pool full of downloads makes it late, and late is not ready."""
    monkeypatch.setattr(M, "_READY_TIMEOUT_S", 0.2)
    monkeypatch.setattr(M, "_probe_database", lambda: time.sleep(1.0) or True)
    started = time.monotonic()
    resp = client.get("/ready")
    assert resp.status_code == 503 and resp.json()["checks"]["database"] is False
    assert time.monotonic() - started < 1.0


def test_the_demo_server_says_it_is_the_demo(client, everything_present, monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    assert client.get("/ready").json()["mode"] == "demo"


def test_health_stays_the_constant_liveness_answer(client, monkeypatch):
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    assert client.get("/health").json() == {"status": "ok"}
