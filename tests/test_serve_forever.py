"""The unattended runner keeps the app and the bot up, and cleans up after itself. Free.

Step 4 of the launch: on a PC serving the public 24/7, Task Scheduler starts
scripts/serve_forever.py at boot with nobody signed in. These run it against
small stand-in children (python -c ...), never the real app or bot, with
every wait bounded — a supervisor test that hangs on the bug is not a test.
"""
import os
import subprocess
import sys
import threading
import time
from datetime import date, timedelta
from pathlib import Path

import pytest

from scripts import serve_forever as S

ROOT = Path(__file__).resolve().parent.parent


def _py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def _wait(condition, timeout=15.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if condition():
            return True
        time.sleep(0.05)
    return False


def _log(logs: Path, name: str) -> str:
    path = logs / f"{name}-{date.today().isoformat()}.log"
    return path.read_text(encoding="utf-8") if path.exists() else ""


@pytest.fixture()
def quick(monkeypatch):
    """Pauses in tenths of a second instead of seconds and minutes."""
    monkeypatch.setattr(S, "_FIRST_PAUSE_S", 0.1)
    monkeypatch.setattr(S, "_MAX_PAUSE_S", 0.4)
    monkeypatch.setattr(S, "_TICK_S", 0.05)


def _supervise(app, bot, *, ready=lambda: True, notify=lambda kind, text: None):
    supervisor = S.Supervisor(app, bot, ready=ready, notify=notify)
    stop = threading.Event()
    thread = threading.Thread(target=supervisor.run, args=(stop,), daemon=True)
    thread.start()
    return supervisor, stop, thread


def _end(supervisor, stop, thread):
    stop.set()
    thread.join(30)
    assert not thread.is_alive(), "the supervisor did not stop"
    assert not supervisor.app.running() and not supervisor.bot.running()


def test_a_child_that_stops_is_started_again_and_the_owner_told(tmp_path, quick):
    told = []
    app = S.Child("app", _py("print('app up', flush=True); import time; time.sleep(30)"), tmp_path)
    bot = S.Child("bot", _py("print('bot run', flush=True); raise SystemExit(1)"), tmp_path)
    supervisor, stop, thread = _supervise(app, bot,
                                          notify=lambda kind, text: told.append((kind, text)))
    try:
        assert _wait(lambda: _log(tmp_path, "bot").count("bot run") >= 3), _log(tmp_path, "bot")
    finally:
        _end(supervisor, stop, thread)
    assert any(kind == "bot-restart" and "exit code 1" in text for kind, text in told)
    assert _log(tmp_path, "app").count("app up") == 1       # the healthy one was left alone


def test_the_pause_doubles_to_a_cap_and_resets_after_a_long_run(tmp_path):
    child = S.Child("bot", _py("pass"), tmp_path)
    pauses = []
    started = 0.0
    for _ in range(9):                         # quick crashes, one after another
        child.started = started
        child.stopped(now=started + 1)
        pauses.append(child.due - (started + 1))
        started = child.due
        child.restarted()
    assert pauses[:4] == [5.0, 10.0, 20.0, 40.0] and max(pauses) == S._MAX_PAUSE_S
    child.started = 1000.0                     # then a run that lasted
    child.stopped(now=1000.0 + S._STABLE_S)
    assert child.due - (1000.0 + S._STABLE_S) == S._FIRST_PAUSE_S


def test_children_run_in_the_project_folder_wherever_it_starts(tmp_path, monkeypatch, quick):
    """Task Scheduler starts in C:\\Windows\\System32; the app reads .env and
    its database path from the working directory (audit-ops OPS-21)."""
    monkeypatch.chdir(tmp_path)
    app = S.Child("app", _py("import os; print('cwd=' + os.getcwd(), flush=True); "
                             "import time; time.sleep(30)"), tmp_path)
    bot = S.Child("bot", _py("import time; time.sleep(30)"), tmp_path)
    supervisor, stop, thread = _supervise(app, bot)
    try:
        assert _wait(lambda: "cwd=" in _log(tmp_path, "app"))
    finally:
        _end(supervisor, stop, thread)
    assert f"cwd={ROOT}" in _log(tmp_path, "app")


def test_hindi_reaches_the_log_intact(tmp_path, quick):
    """Piped, a child's print uses the ANSI code page, and Devanagari kills it
    (measured before, [[harness-stdout-encoding-differs]]): UTF-8 is forced."""
    app = S.Child("app", _py("print('यह दावा झूठा है', flush=True); "
                             "import time; time.sleep(30)"), tmp_path)
    bot = S.Child("bot", _py("import time; time.sleep(30)"), tmp_path)
    supervisor, stop, thread = _supervise(app, bot)
    try:
        assert _wait(lambda: "यह दावा झूठा है" in _log(tmp_path, "app")), _log(tmp_path, "app")
    finally:
        _end(supervisor, stop, thread)


def test_the_bot_starts_only_once_the_app_answers(tmp_path, quick):
    answering = threading.Event()
    app = S.Child("app", _py("import time; time.sleep(30)"), tmp_path)
    bot = S.Child("bot", _py("print('bot up', flush=True); import time; time.sleep(30)"),
                  tmp_path)
    supervisor, stop, thread = _supervise(app, bot, ready=answering.is_set)
    try:
        time.sleep(0.5)
        assert not bot.running(), "the bot started before the app answered"
        answering.set()
        assert _wait(lambda: "bot up" in _log(tmp_path, "bot"))
    finally:
        _end(supervisor, stop, thread)


def test_stopping_ends_both_children(tmp_path, quick):
    app = S.Child("app", _py("import time; time.sleep(60)"), tmp_path)
    bot = S.Child("bot", _py("import time; time.sleep(60)"), tmp_path)
    supervisor, stop, thread = _supervise(app, bot)
    assert _wait(lambda: app.running() and bot.running())
    _end(supervisor, stop, thread)


def test_old_logs_are_deleted_and_the_rest_kept(tmp_path):
    today = date(2026, 10, 16)
    old = tmp_path / f"app-{(today - timedelta(days=S.KEEP_DAYS + 1)).isoformat()}.log"
    recent = tmp_path / f"bot-{(today - timedelta(days=S.KEEP_DAYS - 1)).isoformat()}.log"
    other = tmp_path / "notes.txt"
    for path in (old, recent, other):
        path.write_text("x", encoding="utf-8")
    assert S.prune_logs(tmp_path, today) == 1
    assert not old.exists() and recent.exists() and other.exists()


def test_a_stop_file_stops_both_in_order_and_is_consumed(tmp_path, quick):
    """Re-check F-8: under Task Scheduler nothing can send the supervisor a
    Ctrl+C — End and a reboot are hard kills — so its ordered stop never
    ran. A file it watches is a stop it can receive unattended."""
    stop_file = tmp_path / "serve_forever.stop"
    # Stopped only once each child is truly up, as in real use. MEASURED
    # (review G-4's follow-up, 12 of 12 runs): a CTRL_BREAK sent within
    # moments of a start never reaches the child, which the venv's launcher
    # has not started yet, so the bot was killed at its 15 s grace every
    # time and the test failed whenever the app then took a moment too.
    up = {name: tmp_path / f"{name}.up" for name in ("app", "bot")}
    app, bot = (S.Child(name, _py(f"import pathlib, time; pathlib.Path({str(up[name])!r})"
                                  ".write_text('up'); time.sleep(60)"), tmp_path)
                for name in ("app", "bot"))
    supervisor = S.Supervisor(app, bot, ready=lambda: True, notify=lambda k, t: None,
                              stop_file=stop_file)
    thread = threading.Thread(target=supervisor.run, args=(threading.Event(),),
                              daemon=True)
    thread.start()
    try:
        assert _wait(lambda: all(path.exists() for path in up.values()))
        stop_file.write_text("", encoding="utf-8")
        thread.join(30)
        assert not thread.is_alive(), "the stop file did not stop it"
        assert not app.running() and not bot.running()
        assert not stop_file.exists(), "a stale stop file would stop the next boot"
        assert "stop requested" in _log(tmp_path, "supervisor")
    finally:
        app.stop(1)
        bot.stop(1)


def _stop_file_held_open(tmp_path, refusals):
    """A stop file whose deletion Windows refuses `refusals` times, as it
    does while its writer still holds it — New-Item's own instant, an
    editor, the antivirus (review G-4: the stop test failed so in a full
    run, and the file stayed behind without a word)."""
    class HeldOpen(type(tmp_path)):
        left = refusals

        def unlink(self, missing_ok=False):
            if HeldOpen.left:
                HeldOpen.left -= 1
                raise PermissionError(13, "The process cannot access the file")
            return super().unlink(missing_ok=missing_ok)

    path = HeldOpen(tmp_path / "serve_forever.stop")
    path.write_text("", encoding="utf-8")
    return path


def _stop_with(tmp_path, stop_file):
    app = S.Child("app", _py("import time; time.sleep(60)"), tmp_path)
    bot = S.Child("bot", _py("import time; time.sleep(60)"), tmp_path)
    supervisor = S.Supervisor(app, bot, ready=lambda: True, notify=lambda k, t: None,
                              stop_file=stop_file)
    thread = threading.Thread(target=supervisor.run, args=(threading.Event(),),
                              daemon=True)
    thread.start()
    try:
        thread.join(30)
        assert not thread.is_alive(), "the stop file did not stop it"
    finally:
        app.stop(1)
        bot.stop(1)


def test_a_stop_file_held_open_when_seen_is_still_consumed(tmp_path, quick):
    stop_file = _stop_file_held_open(tmp_path, 1)
    _stop_with(tmp_path, stop_file)
    assert not stop_file.exists(), "a stale stop file would stop the next boot"


def test_a_stop_file_that_cannot_be_removed_is_said_so(tmp_path, quick):
    stop_file = _stop_file_held_open(tmp_path, 99)
    _stop_with(tmp_path, stop_file)
    assert "the next start removes it" in _log(tmp_path, "supervisor")


@pytest.mark.skipif(os.name != "nt", reason="the Windows job object")
def test_the_supervisor_is_inside_its_job_before_it_starts_anything(tmp_path):
    """The deterministic half of F-4 (the race below is only probable):
    main() puts the supervisor itself in the kill-on-close job FIRST, so
    every descendant is born inside it. In a subprocess — never pytest's
    own process."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "import ctypes, sys\n"
        "from ctypes import wintypes\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from scripts import serve_forever as S\n"
        "getattr(S, 'contain_self', lambda: None)()\n"
        "k = ctypes.WinDLL('kernel32', use_last_error=True)\n"
        "k.IsProcessInJob.argtypes = (wintypes.HANDLE, wintypes.HANDLE,"
        " ctypes.POINTER(wintypes.BOOL))\n"
        "k.GetCurrentProcess.restype = wintypes.HANDLE\n"
        "inside = wintypes.BOOL(0)\n"
        "if S._job[0] is not None:\n"
        "    k.IsProcessInJob(k.GetCurrentProcess(), S._job[0], ctypes.byref(inside))\n"
        "print('inside' if inside.value else 'outside', flush=True)\n", encoding="utf-8")
    out = subprocess.run([sys.executable, str(probe)], capture_output=True, text=True,
                         timeout=60).stdout
    assert out.strip() == "inside", out


_GRANDPARENT = (
    "import os, subprocess, sys, time\n"
    "kid = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
    "print(kid.pid, flush=True)\n"
    "time.sleep(120)\n")


@pytest.mark.skipif(os.name != "nt", reason="the Windows job object")
def test_nothing_the_children_start_outlives_the_supervisor(tmp_path):
    """REPRODUCED by re-check F-4: the venv's python.exe is a launcher that
    starts the interpreter at once, and a child was put in the job only
    AFTER Popen returned — so in about half of cold starts the interpreter
    (and the ffmpeg it runs) were born outside it, and outlived a hard kill
    of the supervisor. Six cold starts: a grandchild must never survive."""
    holder = tmp_path / "holder.py"
    holder.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from pathlib import Path\n"
        "from scripts import serve_forever as S\n"
        "getattr(S, 'contain_self', lambda: None)()   # what main() does first\n"
        f"child = S.Child('app', [sys.executable, '-c', {_GRANDPARENT!r}], Path(sys.argv[1]))\n"
        "child.start(0.0)\n"
        "time.sleep(120)\n", encoding="utf-8")
    survivors = []
    for run in range(6):
        logs = tmp_path / f"logs{run}"
        supervisor = subprocess.Popen([sys.executable, str(holder), str(logs)])
        try:
            assert _wait(lambda: "app-" in "".join(p.name for p in logs.glob("*"))
                         and _log(logs, "app").strip(), timeout=20), "no grandchild"
            grandchild = int(_log(logs, "app").split()[-1])
            supervisor.kill()                  # a hard kill: no clean-up code runs
            supervisor.wait(10)
            if not _wait(lambda: not S.process_alive(grandchild), timeout=10):
                survivors.append(grandchild)
        finally:
            if supervisor.poll() is None:
                supervisor.kill()
    for pid in survivors:                       # never leave strays behind
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True)
    assert not survivors, f"{len(survivors)} of 6 grandchildren outlived the supervisor"


@pytest.mark.skipif(os.name != "nt", reason="the Windows job object")
def test_children_die_with_the_supervisor_however_it_dies(tmp_path):
    """Task Scheduler's "End", a crash or a closed window kills the
    supervisor without a word. Its children must not outlive it: an orphaned
    app keeps the database lock and an orphaned bot fights the next one for
    Telegram's single poller."""
    holder = tmp_path / "holder.py"
    holder.write_text(
        "import sys, time\n"
        f"sys.path.insert(0, {str(ROOT)!r})\n"
        "from pathlib import Path\n"
        "from scripts import serve_forever as S\n"
        "child = S.Child('sleeper', [sys.executable, '-c', 'import time; time.sleep(120)'],"
        " Path(sys.argv[1]))\n"
        "child.start(0.0)\n"
        "print(child.proc.pid, flush=True)\n"
        "time.sleep(120)\n", encoding="utf-8")
    supervisor = subprocess.Popen([sys.executable, str(holder), str(tmp_path)],
                                  stdout=subprocess.PIPE, text=True)
    try:
        child_pid = int(supervisor.stdout.readline())
        assert S.process_alive(child_pid)
        supervisor.kill()                      # no clean-up code runs: TerminateProcess
        supervisor.wait(10)
        assert _wait(lambda: not S.process_alive(child_pid), timeout=10), \
            "the child outlived its supervisor"
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
