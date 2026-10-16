"""Where a check's working files go: the person's voice note, its decoded
WAV, a reel's audio — never the system's temp folder.

A temporary directory is removed when its `with` block ends. A hard stop —
the app window closed, a reboot, the unattended runner's job object — runs no
`with` exit, and Windows never empties %TEMP%: a copy of someone's voice note
stayed there indefinitely, outside every deletion the privacy notice
promises (review S5-17). Under the data folder instead, emptied at startup
(app/main.py) once the app holds the single-instance lock, so no running
copy's work is ever touched.
"""
import os
import shutil
import tempfile
from pathlib import Path

from app.config import settings


def folder() -> Path:
    """data/tmp/<database file name>: exactly what this process's lock
    covers. The directory alone let the free demo (data/demo.db) empty the
    real app's (data/verifier.db) files mid-decode (re-check F-3)."""
    path = Path(os.path.abspath(settings.db_path))
    return path.parent / "tmp" / path.name


def workdir() -> tempfile.TemporaryDirectory:
    """A fresh directory under folder(), removed when its block ends."""
    path = folder()
    path.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=path)


def clear() -> int:
    """Remove what a stopped run left behind. -> entries removed."""
    root, removed = folder(), 0
    if not root.is_dir():
        return 0
    for entry in root.iterdir():
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed += 1
        except OSError:
            pass                 # held open by something: the next start tries again
    return removed
