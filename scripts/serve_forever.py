"""Keep the app and the Telegram bot running, unattended (step 4 of the launch).

On the PC that serves the public 24/7, Task Scheduler starts this at boot,
with nobody signed in (docs/go-live.md has the steps). It starts the app,
starts the bot once the app answers, and starts either one again when it
stops. The pause before a restart doubles from 5 s up to 5 minutes, so a
crash loop cannot spin, and drops back to 5 s after a run of 10 minutes.
The owner hears of each restart on Telegram (OWNER_CHAT_ID, at most hourly).

What start.ps1's two windows showed goes to logs/app-YYYY-MM-DD.log and
logs/bot-YYYY-MM-DD.log instead, the last 14 days kept. Neither the app nor
the bot prints a visitor's address or a message (audit-ops OPS-11), so
neither do these files.

    .venv\\Scripts\\python.exe scripts\\serve_forever.py        # Ctrl+C stops both

Its children always run in the project folder, whatever folder it was
started in (a scheduled task starts in C:\\Windows\\System32): the app reads
.env and its database path from there (audit-ops OPS-21). And they die with
it, however it dies (a Windows job object): an orphaned app keeps the
database lock, and an orphaned bot fights the next one for Telegram's
single poller.
"""
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
KEEP_DAYS = 14

_FIRST_PAUSE_S = 5.0
_MAX_PAUSE_S = 300.0
_STABLE_S = 600.0            # a run this long resets the pause
_TICK_S = 1.0
_STOP_GRACE_S = 15.0         # then it is killed
_ORDERLY_GRACE_S = 300.0     # a stop file: a long check gets to finish (~5 min max)
STOP_FILE = ROOT / "data" / "serve_forever.stop"
_ALREADY_RUNNING = 3         # this script's own exit code when a copy already runs
_HEALTH = "http://127.0.0.1:8000/health"
_WINDOWS = os.name == "nt"
_DATED_LOG = re.compile(r"^[a-z]+-(\d{4}-\d{2}-\d{2})\.log$")


def app_argv() -> list[str]:
    # One worker and no access log, exactly as start.ps1 runs it (OPS-08/11).
    return [sys.executable, "-m", "uvicorn", "app.main:app",
            "--workers", "1", "--no-access-log"]


def bot_argv() -> list[str]:
    return [sys.executable, str(ROOT / "scripts" / "telegram_bot.py")]


def _app_answers() -> bool:
    try:
        with urllib.request.urlopen(_HEALTH, timeout=2) as resp:
            return resp.status == 200
    except OSError:
        return False


# -- children die with this process, however it dies (Windows) ----------------

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


def _contain(proc: subprocess.Popen) -> None:
    """Belt and braces for a child: already inside if contain_self() took."""
    if _WINDOWS:
        _assign(int(proc._handle))


def process_alive(pid: int) -> bool:
    if not _WINDOWS:
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid)  # SYNCHRONIZE | query
    if not handle:
        return False
    try:
        return kernel32.WaitForSingleObject(handle, 0) == 0x102     # WAIT_TIMEOUT: running
    finally:
        kernel32.CloseHandle(handle)


# -- one supervised process -----------------------------------------------------

class Child:
    """One process, its output copied line by line into the day's log."""

    def __init__(self, name: str, argv: list[str], logs: Path = LOGS):
        self.name, self.argv, self.logs = name, argv, Path(logs)
        self.proc: subprocess.Popen | None = None
        self.started = 0.0
        self.due: float | None = None    # when a stopped child may start again
        self.pause = _FIRST_PAUSE_S

    def start(self, now: float) -> None:
        self.logs.mkdir(parents=True, exist_ok=True)
        # UTF-8: piped, a child's print would use the ANSI code page, and
        # the first Devanagari word would kill it.
        env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8")
        # Its own process group, so CTRL_BREAK reaches it and nothing else.
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if _WINDOWS else 0
        self.proc = subprocess.Popen(self.argv, cwd=ROOT, env=env,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, creationflags=flags)
        _contain(self.proc)
        self.started, self.due = now, None
        threading.Thread(target=self._copy, args=(self.proc.stdout,), daemon=True).start()

    def _copy(self, stream) -> None:
        for raw in iter(stream.readline, b""):
            stamp = datetime.now()
            line = raw.decode("utf-8", "replace").rstrip("\r\n")
            try:
                with open(self.logs / f"{self.name}-{stamp.date().isoformat()}.log",
                          "a", encoding="utf-8") as f:
                    f.write(f"{stamp:%H:%M:%S} {line}\n")
            except OSError:
                pass                     # a full disk must not stop the child
        stream.close()

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stopped(self, now: float) -> None:
        """It was found stopped: when may it start again? Not by its exit
        code — MEASURED, 3 is uvicorn's "could not start" (a second copy on
        the database, OPS-05; a taken port) AND what Windows' C runtime exits
        with after a CTRL_BREAK, so it says nothing certain. The doubling
        bounds any loop: pauses of 5, 10, 20 … 300 s try a start that always
        fails about seven times in its first ten minutes, then every five."""
        if now - self.started >= _STABLE_S:
            self.pause = _FIRST_PAUSE_S
        self.due = now + self.pause

    def restarted(self) -> None:
        self.pause = min(self.pause * 2, _MAX_PAUSE_S)

    def stop(self, grace_s: float | None = None) -> None:
        if not self.running():
            return
        try:
            if _WINDOWS:
                self.proc.send_signal(signal.CTRL_BREAK_EVENT)   # uvicorn shuts down
            else:
                self.proc.terminate()
        except (OSError, ValueError):
            pass
        try:
            self.proc.wait(_STOP_GRACE_S if grace_s is None else grace_s)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(10)


def prune_logs(logs: Path, today: date) -> int:
    """Delete dated logs older than KEEP_DAYS. -> files deleted."""
    oldest = today - timedelta(days=KEEP_DAYS)
    gone = 0
    for path in Path(logs).glob("*.log"):
        dated = _DATED_LOG.match(path.name)
        if dated and date.fromisoformat(dated.group(1)) < oldest:
            try:
                path.unlink()
                gone += 1
            except OSError:
                pass
    return gone


class Supervisor:
    def __init__(self, app: Child, bot: Child, *, ready=_app_answers, notify=None,
                 now=time.monotonic, stop_file: Path | None = None):
        self.app, self.bot = app, bot
        self.ready, self.now = ready, now
        self._notify = notify
        # Unattended, nothing can send it a Ctrl+C: Task Scheduler's End and a
        # reboot are hard kills (re-check F-8). This file is a stop it can
        # receive — taken by an orderly stop that lets running checks finish.
        self.stop_file = stop_file
        self._orderly = False

    def _stop_requested(self) -> bool:
        if self.stop_file is None or not self.stop_file.exists():
            return False
        try:
            self.stop_file.unlink()          # consumed: the next boot starts
        except OSError:
            pass
        self._log(f"stop requested ({self.stop_file.name})")
        self._orderly = True
        return True

    def _log(self, text: str) -> None:
        stamp = datetime.now()
        line = f"{stamp:%H:%M:%S} [serve_forever] {text}"
        print(line, flush=True)
        try:
            self.app.logs.mkdir(parents=True, exist_ok=True)
            with open(self.app.logs / f"supervisor-{stamp.date().isoformat()}.log",
                      "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass

    def _tell_owner(self, kind: str, text: str) -> None:
        if self._notify is None:
            from app.providers import alerts      # after main() has moved to ROOT
            self._notify = alerts.notify
        try:
            self._notify(kind, text)
        except Exception as exc:  # noqa: BLE001 — an alert must never stop the tending
            self._log(f"could not tell the owner: {type(exc).__name__}")

    def _tend(self, child: Child) -> None:
        now = self.now()
        if child.proc is None:
            child.start(now)
            self._log(f"started the {child.name} (pid {child.proc.pid})")
        elif child.running():
            return
        elif child.due is None:
            code, ran = child.proc.returncode, now - child.started
            child.stopped(now)
            self._log(f"the {child.name} stopped (exit code {code}) after {ran:.0f} s; "
                      f"starting it again in {child.due - now:.0f} s")
            self._tell_owner(f"{child.name}-restart",
                             f"The {child.name} stopped (exit code {code}) and is "
                             "being started again.")
        elif now >= child.due:
            child.start(now)
            child.restarted()
            self._log(f"started the {child.name} again (pid {child.proc.pid})")

    def run(self, stop: threading.Event) -> None:
        last_day = None
        try:
            while not stop.is_set() and not self._stop_requested():
                if date.today() != last_day:
                    last_day = date.today()
                    prune_logs(self.app.logs, last_day)
                self._tend(self.app)
                # The bot refuses to start against an app that is not up.
                if self.bot.proc is not None or (self.app.running() and self.ready()):
                    self._tend(self.bot)
                stop.wait(_TICK_S)
        finally:
            self._log("stopping")
            self.bot.stop()              # first: no new checks submitted
            # An orderly stop gives running checks time to finish: uvicorn's
            # graceful shutdown waits for them (their stream connections).
            self.app.stop(_ORDERLY_GRACE_S if self._orderly else None)
            self._log("stopped")


def main() -> int:
    os.chdir(ROOT)                       # .env, before anything reads settings
    sys.path.insert(0, str(ROOT))
    from app.store import instance
    from scripts.render import force_utf8_stdout

    force_utf8_stdout()
    # First, before any child exists: every descendant is born in the job
    # (re-check F-4).
    contain_self()
    lock = str(ROOT / "data" / "serve_forever")
    (ROOT / "data").mkdir(exist_ok=True)
    try:
        instance.acquire(lock)
    except instance.AlreadyRunning:
        print("[serve_forever] already running — not starting a second copy.")
        return _ALREADY_RUNNING
    STOP_FILE.unlink(missing_ok=True)    # a stale one must not stop this boot
    stop = threading.Event()
    for name in ("SIGINT", "SIGTERM", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: stop.set())
    try:
        Supervisor(Child("app", app_argv()), Child("bot", bot_argv()),
                   stop_file=STOP_FILE).run(stop)
    finally:
        instance.release(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
