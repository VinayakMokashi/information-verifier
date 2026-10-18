"""Where a check's working files go: the person's voice note, its decoded
WAV, a reel's audio — never the system's temp folder.

A temporary directory is removed when its `with` block ends. A hard stop —
the app window closed, a reboot, the unattended runner's job object — runs no
`with` exit, and Windows never empties %TEMP%: a copy of someone's voice note
stayed there indefinitely, outside every deletion the privacy notice
promises (review S5-17). Under the data folder instead, emptied at startup
(app/main.py) once the app holds the single-instance lock — except what a
process still running is working on.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

from app.config import settings


def root() -> Path:
    """data/tmp/<database file name>: exactly the database this process's
    lock covers. The directory alone let the free demo (data/demo.db) empty
    the real app's (data/verifier.db) files mid-decode (re-check F-3)."""
    path = Path(os.path.abspath(settings.db_path))
    return path.parent / "tmp" / path.name


def folder() -> Path:
    """This process's own folder under root(). The app holds the database's
    lock, but an operator script on the same database (asr_probe.py,
    ab_models.py) cannot take it while the app runs — and an app start,
    routine under serve_forever, deleted the file under the running script
    (review G-3). By process id, so a start can tell whose work is live."""
    return root() / str(os.getpid())


def workdir() -> tempfile.TemporaryDirectory:
    """A fresh directory under folder(), removed when its block ends."""
    path = folder()
    path.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=path)


def _alive(pid: int) -> bool:
    if sys.platform != "win32":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True
    # Never os.kill here: on Windows any signal but CTRL_C/CTRL_BREAK is
    # TerminateProcess.
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | query
    if not handle:
        # Another account's process (the fallback service account's app
        # beside the owner's script) refuses to be opened, yet runs.
        return ctypes.get_last_error() == 5                          # access denied
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x102     # WAIT_TIMEOUT: running
    finally:
        kernel32.CloseHandle(handle)


def clear() -> int:
    """Remove what stopped runs left behind; never what another live process
    is working on. Called at startup, so this process has nothing live of
    its own yet. -> entries removed."""
    base, removed = root(), 0
    if not base.is_dir():
        return 0
    for entry in base.iterdir():
        if (entry.is_dir() and entry.name.isdigit() and int(entry.name) != os.getpid()
                and _alive(int(entry.name))):
            continue
        try:
            if entry.is_dir():
                shutil.rmtree(entry)
            else:
                entry.unlink()
            removed += 1
        except OSError:
            pass                 # held open by something: the next start tries again
    return removed
