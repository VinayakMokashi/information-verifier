"""One server per database — taken BEFORE the startup sweep touches anything.

REPRODUCED (docs/research/2026-10-15/audit-ops.md OPS-05): uvicorn runs the
lifespan (init_db + sweep_orphans) before it binds its port, so any second
start against the same database — share_demo.ps1 in REAL mode, a hand-run
uvicorn, a TestClient-based script such as link_smoke.py — marked every
in-flight check of the running copy FAILED, then died on "address already in
use"; those checks still completed, were billed, and were never delivered.

The lock is the operating system's, on a file beside the database, held by
an open handle for the life of the process: it dies with the process, so a
crash or a closed window can never leave the next start locked out (a PID
file could). Within ONE process it is re-entrant — tests open nested
TestClients on one database; another process is what it keeps out.
"""
import os
import sys

_held: dict[str, list] = {}       # lock path -> [open handle, holders in this process]


class AlreadyRunning(RuntimeError):
    """Another live process holds this database."""


def _lock_path(db_path: str) -> str:
    return os.path.abspath(db_path) + ".lock"


def acquire(db_path: str) -> None:
    path = _lock_path(db_path)
    if path in _held:
        _held[path][1] += 1
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle = open(path, "a+b")      # noqa: SIM115 — held open on purpose
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        handle.close()
        raise AlreadyRunning(path) from exc
    _held[path] = [handle, 1]


def release(db_path: str) -> None:
    path = _lock_path(db_path)
    entry = _held.get(path)
    if entry is None:
        return
    entry[1] -= 1
    if entry[1] > 0:
        return
    handle = _held.pop(path)[0]
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    except OSError:
        pass                         # closing the handle releases it anyway
    finally:
        handle.close()
