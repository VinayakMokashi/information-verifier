"""A check's working files never outlive it, however the app stops. Free.

Traced by review S5-17: a voice note being decoded — the person's own
recording — was staged in %TEMP%, and removed only when its `with` block
ended. A hard stop (the window closed, a reboot, the unattended runner's job
object) runs no exit, and Windows never empties %TEMP%. The copy stayed
outside every deletion the privacy notice promises. Working files now live
under the data folder, which the app empties at startup.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.providers import links, media
from app.store import scratch


@pytest.fixture()
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "data" / "verifier.db"))
    return tmp_path / "data"


def _staged_by(call, monkeypatch) -> list[Path]:
    """Where `call` hands ffmpeg its input; ffmpeg itself never runs."""
    staged = []

    def stop(args):
        staged.append(Path(args[args.index("-i") + 1]))
        raise media.MediaError("stopped before ffmpeg")

    monkeypatch.setattr(media, "_run", stop)
    monkeypatch.setattr(media, "_probe_duration", lambda path: 1.0)
    with pytest.raises(media.MediaError):
        call()
    return staged


def test_a_decode_stages_the_upload_under_the_data_folder(data, monkeypatch):
    staged = _staged_by(lambda: media.normalize_to_wav(b"OggS", "voice.ogg",
                                                       max_seconds=300), monkeypatch)
    assert staged and staged[0].parent.parent == scratch.folder()
    assert scratch.folder().is_relative_to(data)
    assert not staged[0].exists()            # and gone once the block ended


def test_splitting_for_asr_stages_there_too(data, monkeypatch):
    staged = _staged_by(lambda: media.split_wav(b"RIFF", 29), monkeypatch)
    assert staged and staged[0].parent.parent == scratch.folder()


def test_a_reel_download_stages_there_too(data, monkeypatch):
    import yt_dlp

    used = []

    def refuse():
        used.append(True)
        raise OSError("stopped before the download")

    class NoNetwork:              # a broken version must not reach the network
        def __init__(self, *a, **kw):
            raise OSError("yt-dlp reached in a test")

    monkeypatch.setattr(scratch, "workdir", refuse)
    monkeypatch.setattr(yt_dlp, "YoutubeDL", NoNetwork)
    with pytest.raises(OSError):
        links.download_link_audio("https://www.instagram.com/reel/DAbCdEfGhIj/", 10_000)
    assert used, "the download staged its file somewhere else"


def test_startup_clears_what_a_killed_decode_left(data):
    from app.main import app

    leftover = scratch.folder() / "tmpdead" / "src.ogg"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"someone's voice note")
    with TestClient(app):
        pass
    assert not leftover.exists()


def test_one_databases_start_never_clears_anothers_work(data, monkeypatch):
    """REPRODUCED by re-check F-3: the working folder was the database's
    DIRECTORY plus tmp, while the single-instance lock is per database FILE.
    The free demo (data/demo.db) starting beside the real app
    (data/verifier.db) emptied the real app's files mid-decode — a voice
    note then refused as unreadable, a funded reel failed."""
    with scratch.workdir() as live:
        staged = Path(live) / "src.ogg"
        staged.write_bytes(b"a voice note, mid-decode")
        monkeypatch.setattr(settings, "db_path", str(data / "demo.db"))
        scratch.clear()                       # the demo's start
        survived = staged.exists()
        monkeypatch.setattr(settings, "db_path", str(data / "verifier.db"))
    assert survived, "another database's start deleted it"


_OPERATOR = """
import sys
from pathlib import Path
from app.store import scratch
with scratch.workdir() as live:
    staged = Path(live) / "src.ogg"
    staged.write_bytes(b"a voice note, mid-decode")
    print(staged, flush=True)
    sys.stdin.readline()                     # until the test says the app started
"""


def test_an_app_start_never_clears_a_live_operator_scripts_work(data, tmp_path):
    """REPRODUCED by review G-3: asr_probe.py and ab_models.py decode in
    scratch.workdir() on the app's own database, without its lock (the app
    holds it), and an app start — serve_forever makes those routine —
    deleted the file under the running script. F-3's fix separated
    databases; these share one."""
    import os
    import subprocess
    import sys
    import threading

    from app.store import instance

    env = dict(os.environ, DB_PATH=settings.db_path,
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    script = subprocess.Popen([sys.executable, "-c", _OPERATOR], cwd=tmp_path, env=env,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    said = []
    reader = threading.Thread(target=lambda: said.append(script.stdout.readline()),
                              daemon=True)
    reader.start()
    reader.join(60)
    try:
        assert said and said[0].strip(), "the operator script never staged its file"
        staged = Path(said[0].strip())
        dead = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                              capture_output=True, text=True, check=True).stdout.strip()
        left = scratch.folder().parent / dead / "tmpgone" / "src.ogg"
        left.parent.mkdir(parents=True)
        left.write_bytes(b"what a killed run left")
        instance.acquire(settings.db_path)            # as the app's start does
        try:
            scratch.clear()
        finally:
            instance.release(settings.db_path)
        assert staged.exists(), "the app's start deleted a running script's file"
        assert not left.exists(), "what a dead process left must still go"
    finally:
        script.communicate("\n", timeout=30)
