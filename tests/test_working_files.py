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
    assert staged and staged[0].parent.parent == data / "tmp"
    assert not staged[0].exists()            # and gone once the block ended


def test_splitting_for_asr_stages_there_too(data, monkeypatch):
    staged = _staged_by(lambda: media.split_wav(b"RIFF", 29), monkeypatch)
    assert staged and staged[0].parent.parent == data / "tmp"


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

    leftover = data / "tmp" / "tmpdead" / "src.ogg"
    leftover.parent.mkdir(parents=True)
    leftover.write_bytes(b"someone's voice note")
    with TestClient(app):
        pass
    assert not leftover.exists()
