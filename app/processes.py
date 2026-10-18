"""What a process starts dies with it, however it dies; and is a process
still running? Windows job objects and liveness, in one place.

The unattended runner (scripts/serve_forever.py) contains itself, so the
app and the bot die with it (re-check F-4). The app, when that runner
starts it, contains itself too, so its ffmpeg dies with IT: a crash the
runner then restarts from left the decode running on, past the 120 s
timeout only the app enforces, holding a voice note open (review G-6).
"""
import os

_WINDOWS = os.name == "nt"
_job = [None]


def _kill_on_close_job():
    """A Windows job object that kills every process in it when its last
    handle closes — when this process ends, cleanly or not. None elsewhere,
    or if Windows refuses (best effort: the children then merely outlive)."""
    import ctypes
    from ctypes import wintypes

    class _IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_ulonglong) for name in (
            "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
            "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

    class _Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_longlong),
                    ("PerJobUserTimeLimit", ctypes.c_longlong),
                    ("LimitFlags", wintypes.DWORD),
                    ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t),
                    ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t),
                    ("PriorityClass", wintypes.DWORD),
                    ("SchedulingClass", wintypes.DWORD)]

    class _Extended(ctypes.Structure):
        _fields_ = [("BasicLimitInformation", _Basic),
                    ("IoInfo", _IoCounters),
                    ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t),
                    ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateJobObjectW.restype = wintypes.HANDLE
    kernel32.CreateJobObjectW.argtypes = (ctypes.c_void_p, wintypes.LPCWSTR)
    kernel32.SetInformationJobObject.argtypes = (wintypes.HANDLE, ctypes.c_int,
                                                 ctypes.c_void_p, wintypes.DWORD)
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        return None
    info = _Extended()
    info.BasicLimitInformation.LimitFlags = 0x2000     # KILL_ON_JOB_CLOSE
    if not kernel32.SetInformationJobObject(job, 9, ctypes.byref(info),
                                            ctypes.sizeof(info)):   # 9: extended limits
        return None
    return job


def _assign(handle) -> bool:
    import ctypes
    from ctypes import wintypes

    if _job[0] is None:
        _job[0] = _kill_on_close_job()
    if _job[0] is None:
        return False
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.AssignProcessToJobObject.argtypes = (wintypes.HANDLE, wintypes.HANDLE)
    return bool(kernel32.AssignProcessToJobObject(_job[0], handle))


def contain_self() -> bool:
    """Put THIS process in the kill-on-close job before it starts anything,
    so every descendant is born inside it. MEASURED (re-check F-4): putting
    each child in after Popen lost a race against the venv's python.exe — a
    launcher that starts the interpreter at once — and in about half of cold
    starts the interpreter, and the ffmpeg it runs, were born outside the
    job and outlived a hard kill. -> whether it took."""
    if not _WINDOWS:
        return False
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    return _assign(kernel32.GetCurrentProcess())


def process_alive(pid: int) -> bool:
    if not _WINDOWS:
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
        # beside the owner's own script) refuses to be opened, yet runs.
        return ctypes.get_last_error() == 5                          # access denied
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x102     # WAIT_TIMEOUT: running
    finally:
        kernel32.CloseHandle(handle)
