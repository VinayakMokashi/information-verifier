# Review of the round-3 fixes (re-check F-1..F-13)

status: complete

Scope: commits 1ae3cc3, 5acbbad, 1f23fc2, c584e1d, e039852, 09dc74d
(range `1ae3cc3^..09dc74d`; c5fd569 is docs only), against the findings
in `docs/research/2026-10-16/review-fixes-step5.md`. Priority 1 is the
owner's first real app start on the real database (app/main.py
`_serving`: init_db, scratch.clear, vacuum_once, sweep_orphans,
housekeeping); priority 2 is docs/go-live.md §5.

Method: a `git archive HEAD` extract (HEAD = 97244ee) in the session's
scratch folder (no .env, no data), dummy keys set before `app` is
imported exactly as tests/conftest.py does, DB_PATH pointed into scratch,
synthetic databases only. The real `data\`, `logs\` and `.env` were never
opened. Nothing paid was run; no port was bound; nothing was registered
(Task Scheduler objects were built, not registered; cloudflared was not
run — its version and PE header were read from the MSI's registry entry
and the file). Mutants ran in second and third extracts; the 2026-10-11
code (`git archive 03e22c8`) in a fourth, to build the old database.

The probes named below are in this session's scratch folder
(`…\scratchpad\review-round3\probe\`), which the next session cannot
see; each finding says what its probe does, so it can be rewritten.

**Clean-up:** every synthetic database, WAL, lock, backup and pending
file this review made (`review-round3\dbs\`, and the explorers' temp
folder) was deleted at the end; a header scan of the scratch folder then
found no SQLite file (776 files). No probe process was left running
(checked by command line). pytest's own temporary folders
(`%TEMP%\pytest-of-…`, pruned by pytest) were left to pytest.

## Summary

**First start: safe to start.** **go-live.md §5: the cloudflared and
Task Scheduler blocks are correct; the fallback-account block misses
BACKUP_DIR (G-2).** 8 findings, **0 high, 0 medium, 8 low**; all
CONFIRMED (G-2 by ACL and code, G-8's production trigger plausible).

| ID | Severity | One line |
|---|---|---|
| G-1 | low | find_db_copies.py hides a real copy as "what tests and reviews make" when it is under half the live file's size: a compacted copy at once, any copy once the database grows (1f23fc2, F-1's rule) |
| G-2 | low | The fallback service account is granted Python and ffmpeg but not BACKUP_DIR: the OneDrive backup fails every time, and no housekeeping failure alerts the owner (09dc74d, F-10's rule) |
| G-3 | low | An app start still deletes the working files of asr_probe.py / ab_models.py on the same database (e039852, F-3 named them) |
| G-4 | low | The stop-file test is flaky (failed in a full run): the supervisor sees the file while it is being written, and on Windows the consume fails in silence (5acbbad) |
| G-5 | low | forget.py's new NOTE says "run this again"; the second run finds nothing, exits 1, and never truncates the WAL (e039852, F-7's rule) |
| G-6 | low | When the app alone dies under a living supervisor, its ffmpeg outlives it, 4 of 4 (5acbbad covers the supervisor's death only; pre-existing) |
| G-7 | low | The F-4, F-8 and F-9 calls live in `main()`s no test runs: deleting any one leaves the suite green (mutants M13–M15) |
| G-8 | low | The bot's pending file fails to save in ~1/3 of writes within a second of the last (winerror 5 on the replace), swallowed: a restart can re-deliver or lose a check; the new restarts explorer's I10 fires on HEAD (pre-existing) |

Fixes that covered the case named but not the rule: G-1 (F-1), G-2
(F-10), G-3 (F-3), G-5 (F-7), G-6 (F-4). New defects inside the fixes:
G-1, G-4, G-5. Tests that pass against the broken wiring: G-7. Found by
the range's own new explorer, pre-existing: G-8.

## Fixed (2026-10-18, the same session)

Each one was reproduced first, then fixed with a test seen failing
against the old code, with mutants run, and pushed alone. The full suite
was run on each commit in a separate worktree before its push.

| ID | Commit | What changed |
|---|---|---|
| G-8 | 82b0708 | `app/files.replace()` retries a refused swap (measured on this PC: 631 of 1,000 back-to-back swaps refused; with 10–200 ms retries, 860 of 860 landed). A save that never lands is rewritten at the next poll. The backup uses it too. |
| G-2 | 6eb2e57 | A housekeeping step that raises alerts the owner. The fallback block grants BACKUP_DIR, and its check proves a backup landed. Also the go-live notes: same window, Read-Host, bringing it back, the service's own config.yml. |
| G-4 | 4838389 | The stop file is consumed once the stop is done, retried, and the log says if it could not be. A second flake was MEASURED: a CTRL_BREAK sent just after a start never reaches the child (12 of 12), so the test now waits for both children to be up. |
| G-5 | aaf5398 | A `--yes` run that matches nothing finishes the file (empties the WAL) and says whether it is clean. |
| G-1 | f9fd678 | Every database of this project's schema is listed, whatever its size; only pytest's own folders are collapsed. Orphaned `-wal` files are found by their header. |
| G-3 | 486a795 | Working files go in a folder per process id; an app start clears only the folders of dead processes. "Access denied" counts as alive. |
| G-7 | 7f35db8 | The bot's main() runs with the lock really held by another process, and serve_forever's main() runs in a subprocess. M13, M14 and M15 are each caught. |
| G-6 | ea2e82c | Under the runner (VERIFIER_SUPERVISED=1), the app contains itself at startup, so its ffmpeg dies with it; the job code lives in `app/processes.py`, shared. |

## First-start verdict

**Safe to start.** Nothing in the first start can lose or damage data the
code is not meant to delete, fail the start, or hang it, on a database in
the state HANDOFF §0 describes (1,273,856 bytes, last written 2026-10-12,
an empty `-wal`, a `-shm`). One condition: do not have any other program
open on `data\verifier.db` (a DB browser) while it starts — even then the
start succeeds, the rewrite is simply redone at the next start.

Measured, not assumed (`probe\build_old.py` + `probe\first_start.py` in
the scratch folder; synthetic databases only):

- The synthetic database was built by the 2026-10-11 code itself
  (`git archive 03e22c8`, the last commit before the real file's
  2026-10-12 05:21 write), on top of a pre-pivot legacy schema made with
  the real `sqlite_vec` 0.1.9 (a vec0 `claim_vecs` plus `reports` and
  `claim_cache`), so the inert `claim_vecs` entry the real file carries
  is there. It holds old and recent answers, one PROCESSING and one
  QUEUED orphan, caches, a ledger of 22 rows, a daily count, and rows
  deleted WITHOUT secure_delete. The builder then dies with `os._exit`
  after a TRUNCATE checkpoint, leaving a 0-byte `-wal` and a stale `-shm`,
  as the real folder is.
- HEAD's real lifespan (TestClient, no port bound) on it: startup 1.0 s;
  `PRAGMA integrity_check` ok before and after; the VACUUM ran (the vec0
  entry is copied as a schema row, never instantiated: sqlite 3.45.1
  copies `rootpage=0` tables raw); the marker is written; the WAL is
  emptied; every deleted row's bytes and the legacy tables' bytes are 0 in
  the file and the WAL, every live row is intact; the ledger kept all 22
  rows and gained exactly the orphan's own $0.03 (none for the orphan with
  no bill); `/ready` 200. A second start does nothing more (marker set,
  WAL 0).
- With another connection holding a read transaction through the whole
  start (a DB browser): the start still succeeds in 3.2 s, the log says
  "the one-time rewrite could not finish … tried again at the next
  start", the marker is NOT written, and the next start (reader gone)
  does the rewrite and empties the WAL. No data changed beyond the
  intended prunes.
- Nothing can reach the database mid-VACUUM from outside: uvicorn 0.51
  runs the lifespan before it creates its socket (`server.py:104` then
  `:142`), so the bot's `/ready` poll gets "connection refused" until the
  start is done, and the bot never opens the database itself (it uses
  only the data folder for its own lock and pending file). The instance
  lock is taken before `_serving` runs.
- Disk: the VACUUM writes the whole file once more into the WAL
  (~1.3 MB here) and, only above ~2 MB, a temporary copy too (measured:
  none at this size; see Notes); C: has 177 GB free.
- A kill at any point (not measured; SQLite's WAL design, and the code's
  order): an uncommitted VACUUM's WAL frames are ignored on the next
  open; a committed one whose marker was not written yet is simply redone
  at the next start.
- In the 2026-10-11 code a running check's row got its bill only when it
  finished (`run_check` saves the PROCESSING row with no usage;
  `record_progress` came with OPS-04 on 2026-10-15), which is why an
  orphan in the real file adds nothing to the ledger.

What the owner should expect to see, and why each is right:
- `[startup] the database was rewritten once: …` (once only).
- `[startup] housekeeping: {...'answers_deleted': N...}` — every answer
  created before 2026-09-18 is deleted at this start, as the 30-day
  promise says (the ledger backfill runs FIRST, so their costs stay).
  Expired answer-cache and transcript entries go too.
- `failed N job(s) orphaned by a restart` only if the file has
  QUEUED/PROCESSING rows. Rows written by the 2026-10-11 code carry no
  bill until they finish, so the ledger total should still read
  **$1.7437** on the dashboard afterwards — a different number is worth
  a look.
- A new `data\backups\ledger-<UTC date>.db` (or in BACKUP_DIR), and the
  yt-dlp "N days old" note and the going-live warnings.
- A file `data\verifier.db.lock` stays (by design).

## go-live.md §5 verdict

**The cloudflared block and the Task Scheduler block are correct as
written; paste them.** The fallback-account block works on this PC but
leaves one thing out (G-2: BACKUP_DIR), and it reuses `$dir` from the
block before it, so run it in the same window.

- `cloudflared service install` with no token DOES create the service,
  and starts it: cloudflared's source at the installed version's tag
  (`2026.7.3`, the MSI's DisplayVersion here) has `windowsServiceName =
  "Cloudflared"`, `m.CreateService(windowsServiceName, exepath, config,
  extraArgs...)` with `extraArgs` empty unless a token is given, then
  `s.Start()` (and `s.Delete()` only if that start fails). Started bare,
  it runs no tunnel (F-5), which the next three lines fix.
- The key `HKLM:\SYSTEM\CurrentControlSet\Services\Cloudflared` is the
  service's name exactly (registry keys are case-insensitive anyway).
  Cloudflare's own page, re-fetched today, has the same key (step 13) and
  `cloudflared.exe --config=C:\Windows\System32\config\systemprofile\.cloudflared\config.yml tunnel run`
  (step 14): `--config` before `tunnel run`, as the runbook has it. The
  page's example path has no spaces; this PC's has (`C:\Program
  Files (x86)\cloudflared\cloudflared.exe`, what `Get-Command` returns
  here), so the runbook's quotes around the executable are needed and
  right. The quotes around the `--config` value are stripped by the
  command-line parser; harmless. `Execute` falls back to the ImagePath's
  arguments when the SCM passes none, so the edit takes effect.
- `Set-ItemProperty <key> ImagePath <value>` is positional
  Path/Name/Value; an existing value keeps its kind (REG_EXPAND_SZ).
  `Restart-Service` starts a stopped service too.
- `C:\Windows\System32\config\systemprofile` is the right folder even
  though cloudflared sits in `Program Files (x86)`: its PE header says
  x64 (machine 0x8664, read here without running it), so the service is
  not redirected to `SysWOW64\config\systemprofile` as a 32-bit one
  would be. Run the block in the normal (64-bit) Windows PowerShell, not
  "Windows PowerShell (x86)", or `mkdir`/`copy` land in SysWOW64.
- The copies: the runbook copies config.yml and `<UUID>.json`, not
  `cert.pem` (Cloudflare's step 8). `tunnel run` with a credentials file
  does not need the origin certificate; only create/route/delete do.
- Task Scheduler: built here without registering, the settings come out
  `ExecutionTimeLimit PT0S` (no limit), `RestartCount 999`,
  `RestartInterval PT1M`, `StartWhenAvailable True`, both battery stops
  off, `MultipleInstances IgnoreNew`, `Priority 7`; the action is
  `Execute` = the venv python, `Arguments` = the quoted script path,
  `WorkingDirectory` = the project. The 2026-10-16 re-check validated the
  registration itself (validate-only). Task Scheduler grants the account
  "Log on as a batch job" itself when a task is registered with a
  password (Microsoft's page for that right), so the fallback account
  needs no policy edit.
- The fallback block, evaluated read-only here: `pyvenv.cfg` has exactly
  one `home` line, and the `-match`/`-replace` gives a one-element array
  `C:\Users\Vinayak Mokashi\AppData\Local\Programs\Python\Python312`,
  which exists and which icacls receives as one argument. `Get-Command
  ffmpeg` gives the real file in `WinGet\Packages\Gyan.FFmpeg_…\bin` (on
  PATH directly, not a WinGet `Links` symlink), so the folder granted is
  the one that holds ffmpeg and ffprobe. The PATH line: .NET's
  `GetEnvironmentVariable(…, "Machine")` expands `%…%` and
  `SetEnvironmentVariable` writes REG_SZ — a known way to flatten a
  machine PATH — but here it is already REG_SZ with no `%` entry (read,
  not changed), so it changes nothing else.

## Findings

### G-1. find_db_copies.py finds a real copy by what it is, then hides it as "what tests and reviews make" whenever its size is under half of today's real file — a compacted copy at once, any full copy once the real database grows

- Severity: low
- Status: CONFIRMED (synthetic databases; `probe\finder_sizes.py`)
- Where: `scripts/find_db_copies.py:92-98` (shown only when the size is
  equal to the real file's, or at least half of it; otherwise counted as
  "small … what tests and reviews make"), commit 1f23fc2.
- Rule it breaks: F-1's — find copies by what a file IS, never by name or
  place. Size relative to the live file is a property of the moment, not
  of the copy: the fix moved the filter from the name to the size.
- Evidence: a synthetic "real" database of 600 answers, a full copy taken
  with the backup API, then 480 answers deleted (a prune), a `VACUUM INTO`
  copy of the rest, and later 2,000 new answers:

      real after prune 2846720 | compact copy 622592 | full copy from before 2846720
      === finder, real database as it is now (many free pages) ===
         2846720 … dbs\finder\data\verifier.db  [the real database]
         2846720 … dbs\finder\scratch\copy-today.db  [SAME SIZE AS THE REAL DATABASE — almost certainly a copy: delete it]
      + 1 small database(s) of this project's schema — what tests and reviews make; --all lists them.
      === finder, after the real database grew to 9879552 ===
         9879552 … dbs\finder\data\verifier.db  [the real database]
      + 2 small database(s) of this project's schema — what tests and reviews make; --all lists them.

  The compacted copy holds 120 people's messages and is reported as test
  data from the start. The full copy is shown while the sizes match and
  disappears into the "small" count once the real file passes twice its
  size. Both are ordinary: `VACUUM INTO` is the documented way to copy a
  live SQLite file, and the real file will grow from 1.27 MB once the
  public uses it (a month of answers at the $1 budget). The copies that
  matter most are the old ones, past the notice's 30 days — exactly the
  ones growth hides. HANDOFF §0's "finds no copy of the real database
  anywhere" is only as good as this line.
- Mutant check: n/a (a gap in the fix, not in its test). The two tests
  pin a same-size copy only; neither has a copy of a different size.
- Suggested fix: decide by where a file is, not how big: show every
  database of this project's schema, and collapse only those under
  pytest's own temporary root (`%TEMP%\pytest-of-<user>\`, what the suite
  makes); a review's synthetic databases are deleted at its end anyway
  (CLAUDE.md). Keep the size match as an extra mark, not a gate. Add a
  test with a compacted copy and one with a grown real file.

### G-2. The fallback service account is granted Python and ffmpeg but not BACKUP_DIR: with the runbook's OneDrive folder the daily ledger copy fails every time, and nothing tells the owner

- Severity: low
- Status: CONFIRMED by ACL and code (no second account created, nothing
  registered)
- Where: `docs/go-live.md:161-178` (09dc74d grants `$dir`, the Python
  folder and the ffmpeg folder); `docs/go-live.md:26` and HANDOFF §0 owner
  item 4 (`BACKUP_DIR=` "a OneDrive (or USB) folder"); `app/store/backup.py:38-43`
  (`folder.mkdir` / the copy, which raise); `app/store/repository.py:679-683`
  (housekeeping prints `ledger_backed_up failed` and moves on); no
  `alerts.notify` for any housekeeping step.
- Rule it breaks: F-10's — the service account needs everything the app
  reads or writes outside the project folder. The fix listed the two
  things the finding named.
- Evidence: `icacls C:\Users\Vinayak Mokashi\OneDrive` (read only):

      Everyone:(CI)(DENY)(DC)  NT AUTHORITY\SYSTEM:(OI)(CI)(F)
      BUILTIN\Administrators:(OI)(CI)(F)  VINAYAK45\Vinayak Mokashi:(OI)(CI)(F)

  — the same three principals F-10 found on the profile; a local standard
  account is none of them. Under that account, `backup_ledger()` raises
  PermissionError at startup and every 6 hours; housekeeping logs one line
  to `logs\app-*.log` and records -1. The money record then never leaves
  the laptop, which is the whole point of BACKUP_DIR ("a backup on the
  same disk survives a deleted file, not a dead disk", backup.py). The
  supervisor's /ready check does not cover it, so "Start-ScheduledTask …
  /ready says ready" passes.
- Suggested fix: in the fallback block, grant the account Modify on
  BACKUP_DIR too (or say: point BACKUP_DIR at a folder outside your
  profile, e.g. a USB drive, and grant it), and make the check name it:
  after the task's first start, `logs\app-<today>.log` has no
  "housekeeping … failed" line and a `ledger-<date>.db` appeared in
  BACKUP_DIR. Better still, the rule in code: a housekeeping step that
  fails (the backup, and the 30-day prune above all) alerts the owner,
  at most daily, as the other failures already do.

### G-3. An app start still deletes the working files of an operator script on the same database — F-3's fix covers the demo, not the scripts F-3 itself named

- Severity: low
- Status: CONFIRMED (`probe\operator_scratch.py`, synthetic database)
- Where: `app/store/scratch.py:20-25` (`folder()` = `data/tmp/<db file
  name>`, e039852); `app/main.py:401` (`scratch.clear()` at every start);
  `scripts/asr_probe.py:33` (`normalize_to_wav`) and `scripts/ab_models.py:32`
  (`resolve_link`), which decode and download in `scratch.workdir()` with
  the `.env`'s database — the app's own — and never take its lock.
- Rule it breaks: F-3's — the folder a process clears must be exactly
  what its lock covers. F-3's evidence names these scripts ("exposed the
  same way to any app restart, which serve_forever.py now makes routine");
  the fix separated databases, and these scripts share the app's.
- Evidence: one process stages a voice note in `scratch.workdir()` on
  `dbs\op\data\verifier.db` without the lock, as asr_probe.py does, then
  a child runs the app's real lifespan on the same database:

      operator's working file: data\tmp\verifier.db\tmpnuq2x29i\src.ogg exists: True
      app start rc 0 | said: ['[startup] removed 1 working file(s) a stopped run left behind']
      operator's working file after the app started: GONE (deleted under the running script)

  Both scripts decode before they pay (ASR comes after the decode), so the
  cost is a failed paid-script run, not money; but under serve_forever an
  app restart can come at any minute.
- Mutant check: n/a (the fix's test, `tests/test_working_files.py`, pins
  two different databases only).
- Suggested fix: the rule, in `scratch`: a process that does not hold the
  database's lock gets its own folder (`data/tmp/<db name>.<pid>`), and
  `clear()` empties only the lock holder's folder plus folders whose pid
  is no longer alive. Or
  simplest: `workdir()` takes the lock-holder's folder only when
  `instance` says this process holds the lock, and a per-pid folder under
  `data\tmp` otherwise.

### G-4. The stop file's own test is flaky: the supervisor can see the file while the test is still writing it, and on Windows the "consume" then fails in silence

- Severity: low
- Status: CONFIRMED (failed in a full run of the extract's suite; the
  mechanism reproduced deterministically by `probe\stopfile_race.py`)
- Where: `scripts/serve_forever.py:281-290` (`_stop_requested`: `exists()`,
  then `unlink()` with `except OSError: pass`), commit 5acbbad;
  `tests/test_serve_forever.py:156-177` (`stop_file.write_text("")` while
  the `quick` fixture ticks the supervisor fast).
- Rule it breaks: "a green suite" must not depend on timing (CLAUDE.md:
  wait on conditions, not durations); and the code says the file is
  "consumed" when it may not be.
- Evidence: the extract's full suite (run beside this review's probes,
  so the machine was loaded):

      FAILED tests/test_serve_forever.py::test_a_stop_file_stops_both_in_order_and_is_consumed
      >  assert not stop_file.exists(), "a stale stop file would stop the next boot"
      Captured stdout call:
      03:24:16 [serve_forever] stop requested (serve_forever.stop)
      03:24:16 [serve_forever] stopping
      03:24:16 [serve_forever] stopped
      2 failed, 1314 passed … pytest exit 1

  The supervisor saw the file and stopped, but the file was still there.
  `probe\stopfile_race.py` holds the file open while the supervisor
  polls, as `write_text` does for an instant:

      stop requested (serve_forever.stop) … stopping … stopped
      supervisor stopped while the writer held the file: True
      stop file left behind: True

  Windows refuses to delete a file another handle has open without
  FILE_SHARE_DELETE (CPython's `open` does not pass it); the error is
  swallowed. The test file passes alone (18 passed). In production the
  stop still happens and `main()` deletes a stale file at the next start,
  so nothing is lost; but anything holding the new file for an instant
  (Defender scanning it, an editor) leaves it behind, unsaid.
- Mutant check: n/a (the test is right to want the file gone; it races).
- Suggested fix: in the test, make the file appear whole (`write_text` to
  `serve_forever.stop.tmp`, then `os.replace`), as `New-Item` effectively
  does. In the code, retry the unlink once the supervisor has stopped its
  children (the writer is long gone by then), and log if it still fails
  ("the stop file stays until the next start removes it"), so the log
  tells the truth.

### G-5. forget.py's new NOTE says "close any program reading the database and run this again" — but the second run finds nothing to delete, says "No check matches", exits 1, and never truncates the WAL

- Severity: low
- Status: CONFIRMED (`probe\forget_again.py`, synthetic database)
- Where: `scripts/forget.py:117-122` (the NOTE), `:83-88` (no match →
  return 1 before anything else), `app/store/repository.py:565`
  (`truncate_wal()` only inside `forget()`), commit e039852.
- Rule it breaks: F-7's — never report a deletion as finished when it is
  not, and say what finishes it. The fix's remedy is one that cannot work.
- Evidence: an answer saved, a reader holding a snapshot, forget.py run
  as a separate process (as the owner runs it, beside the app), the
  reader closed, then forget.py run again exactly as the NOTE says:

      saved; secret in {'db': 0, '-wal': 30}
      1st run with a reader open: (0, "NOTE: something is reading the database, so its file still holds the deleted text's earlier copy until the next housekeeping (within 6 hours")
      reader closed; secret in {'db': 0, '-wal': 30}
      2nd run, as the NOTE says: (1, 'No check matches. A reel is found by its link; …')
      after the 2nd run; secret in {'db': 0, '-wal': 30}

  (Same result with an idle connection held open meanwhile, as the
  running app has between operations.) The deleted message stays in
  `verifier.db-wal` after the advised step, and the owner is told the
  check cannot be found — which reads like the first run failed. The WAL
  is emptied only when the app's housekeeping next runs, or by chance when
  some process's close is the database's last.
- Mutant check: `test_forget_says_when_the_file_still_holds_the_old_copy`
  pins only that the NOTE is printed; no test runs the advice.
- Suggested fix: every forget.py run, matching or not, ends with
  `truncate_wal()` and says whether the file is clean now — then "run
  this again" is true. (Or the NOTE says only what is true: "the app's
  next housekeeping, within 6 hours, finishes it".) Test it by running
  the advice: second run with the reader gone → file clean.

### G-6. When the APP dies under a living supervisor (a crash it then restarts from), the app's ffmpeg still outlives it, 4 of 4 — F-4's fix covers the supervisor's death only

- Severity: low
- Status: CONFIRMED (`probe\app_crash_orphan.py`, run with the venv's
  `python.exe` as Task Scheduler runs it; `ping` stands in for ffmpeg, as
  in F-4's own reproduction)
- Where: `scripts/serve_forever.py:135-149` (`contain_self`, 5acbbad) and
  `:194-204` (`Child.start`); the venv launcher's own job
  (KILL_ON_JOB_CLOSE | SILENT_BREAKAWAY_OK, F-4's evidence);
  `app/providers/media.py` (ffmpeg with its 120 s timeout, enforced by the
  app process).
- Rule it breaks: F-4's consequence, which is about the app's restart: an
  ffmpeg that outlives the process enforcing its 120 s timeout runs
  unbounded, and holds a person's voice note open in `data\tmp` while
  the restarted app's `scratch.clear()` runs (it skips open files: "the
  next start tries again").
- Evidence: the supervisor contains itself (as `main()` does), starts an
  "app" child through the venv launcher; the app starts a grandchild and
  then dies (`os._exit(1)`, a crash):

      supervisor contained itself: True
      run 0: app exited (1); its grandchild 46508 alive while the supervisor lives: True
      run 1: … True   run 2: … True   run 3: … True
      orphans: 4 of 4

  Why: the app interpreter's immediate job is its launcher's, which
  allows silent breakaway, so its children break away from it and stop at
  the supervisor's job, which does not. The supervisor's job now holds
  them (that is F-4's fix, and they die with the supervisor), but nothing
  kills them when the app alone dies or is killed by `Child.stop()`
  (`proc.kill()` kills the launcher, its job kills the interpreter only).
  Pre-existing, not introduced by 5acbbad; under serve_forever an app
  restart is routine, a supervisor death is not. (The probe killed its
  orphans; none were left.)
- Mutant check: n/a (no test kills the app alone).
- Suggested fix: the rule "a decode never outlives the process that bounds
  it": the app contains ITSELF at startup in its own kill-on-close job
  that forbids breakaway (the same `contain_self`, called from the
  lifespan, Windows only). Its ffmpeg's immediate job is then the app's,
  and dies with it. Test it like this probe: the app dies, its grandchild
  must be gone.

### G-7. Three of the fixes live in a `main()` that no test runs: deleting any of the three calls leaves the whole suite green

- Severity: low
- Status: CONFIRMED (mutants in a second extract, `probe\mutants.py`)
- Where: `scripts/serve_forever.py:363` (`contain_self()`, F-4) and
  `:371` (`STOP_FILE.unlink(missing_ok=True)`, F-8), 5acbbad;
  `scripts/telegram_bot.py:1282` (`if not take_the_bot_lock()`, F-9),
  c584e1d.
- Rule it breaks: CLAUDE.md, "a green suite is not a working product" —
  the bot was once broken for a whole commit while its tests passed on
  the parts. Each test here calls the helper, never the place it is
  wired in.
- Evidence (each mutant alone, the named test files run):

      M13 F-9: main() never takes the bot lock: SURVIVED | 129 passed
      M14 F-4: main() never contains itself: SURVIVED | 11 passed
      M15 F-8: a stale stop file is not removed at start: SURVIVED | 11 passed

  For comparison the store fixes' tests catch theirs: M5 (F-13), M6
  (F-3), M10 (F-11), M11 and M12 (F-7) and M16 (F-12) all CAUGHT. The
  F-4 test even writes `getattr(S, 'contain_self', lambda: None)()` —
  "what main() does first" — instead of running main(). A refactor of
  either `main()` that drops a line would undo the fix with no test
  noticing; for M15 the cost is the first boot after an orderly stop
  ending at once.
- Mutant check: the three above.
- Suggested fix: test the wiring, not only the parts. serve_forever:
  run `main()` in a subprocess with `ROOT`/`STOP_FILE`/`app_argv`/
  `bot_argv` pointed at a scratch folder and stub children (it already
  takes no network), with a stale stop file present: it must start both
  and be inside its job (IsProcessInJob), then stop on a fresh stop file.
  The bot: run `main()` with the getMe and the app status faked while a
  holder process has the lock: it must print "already running" and never
  reach `Dispatcher(...)`.

### G-8. The bot's pending file fails to save in about a third of writes that come within a second of the last (Windows "access denied" on the replace), and the failure is swallowed: the restarts explorer's own I10 fires on HEAD

- Severity: low
- Status: CONFIRMED (the mechanism and its rate measured here; a
  production restart inside the window is PLAUSIBLE, not reproduced)
- Where: `scripts/telegram_bot.py:855-865` (`PendingStore._write`:
  write `.tmp`, `os.replace` onto the file, `except OSError: print`);
  pre-existing (OPS-07 / S5-1), exercised by c584e1d's new
  `scripts/bot_explorer_restarts.py`, whose I10 ("the file on disk never
  holds an entry older than a day after a write") catches it.
- Rule it breaks: OPS-07's — the file is what a restart resumes from, so
  it must say what memory says; and S5-1's "at most a day" on disk.
- Evidence:
  - HEAD's restarts explorer, seeds 2000–3999, all output kept:

        6 [bot] could not save the pending checks: PermissionError
        violations by invariant: {'I10': 1}
          first I10: seed=3696: I10 chat 1's entry is a day old and still on disk

    (Seeds 0–1999 and 6000–8999 were clean on HEAD; one run of 0–1999 on
    mutant M9 had 4 I10, and a rerun of the same seeds on the same mutant
    none. A single seed does not reproduce: it depends on timing, not on
    the seed.)
  - `probe\replace_fail.py`, the same write-then-`os.replace` pattern on
    a file in this session's scratch folder:

        gap  0.0 s, 3000 writes: {'ok': 1193, 'replace: PermissionError winerror=5': 1807}
        gap 0.05 s,  400 writes: {'replace: PermissionError winerror=5': 87, 'ok': 313}
        gap  0.5 s,  120 writes: {'ok': 78, 'replace: PermissionError winerror=5': 42}
        gap  2.0 s,   60 writes: {'ok': 60}
        gap  5.0 s,   30 writes: {'ok': 30}

    The replace onto a file written a moment ago is refused (winerror 5)
    — the pattern npm's graceful-fs retries for, blamed on antivirus
    scanning the fresh file; which process held it here was not
    identified. `probe\pending_write_fail.py` with the real class: 5,000
    checks back to back, 2,520 failed writes, and 838 times a DELIVERED
    job stayed on disk.
  - When it fails, memory is right and the file is the previous one. A
    restart before the next good write then resumes from it: an answer
    already delivered is delivered again, and a check just submitted is
    missing — the very loss OPS-07 exists to prevent (its answer is
    never handed over by itself, and a re-send is checked anew: free only
    if the answer cache matches it exactly, and a voice note's
    transcription is bought again either way). Writes come within a
    second of each other exactly at a restart (`__init__` writes, then
    each resumed done job pops at once) and in bursts from several chats;
    a bot crash-looping under serve_forever restarts inside that window.
    A quiet bot never rewrites, so a stale entry also stays past its day.
- Mutant check: n/a (pre-existing; no test makes a write fail).
- Suggested fix: retry the replace a few times over ~1 s (as graceful-fs
  does); if it still fails, keep a "dirty" flag and rewrite at the next
  `tidy()` (each poll), so the file converges on memory within one long
  poll. Test with an `os.replace` that fails twice, and keep I10 in the
  explorer as the guard.

## Checked and sound

- **The first start** (see the verdict above): VACUUM over the inert
  vec0 entry, an empty WAL with a stale -shm, a reader during the start,
  a second start, kill points, disk, uvicorn's bind order, the bot never
  opening the database, the ledger total, the backup. All measured on
  synthetic databases built by the 2026-10-11 code.
- **e039852, F-7** (truncate): the checkpoint holds writers for at most
  1 s now (its own busy timeout), and `busy == 0` is the right test for
  "the log is empty" in TRUNCATE mode. housekeeping retries every 6 h and
  says `wal_not_emptied`. (The NOTE's advice is G-5.)
- **e039852, F-11** (VACUUM): guarded at startup; marked only after a
  truncate that reported empty; a reader makes it return False and the
  next start redo it (measured above, and the commit's test). Redoing it
  is idempotent. A committed VACUUM whose truncate failed is completed by
  any later successful checkpoint anyway; only the marker waits.
- **e039852, F-13** (ledger): every ledger write goes through
  `SpendLedger.record` (grep: routes.fail_job, job.run_check, the two
  sweeps, the backfill, ab_models.py); restore matches by `ledger_ref`;
  the DELETE + INSERT are one transaction. The sweep-after-restore case
  counts once.
- **e039852, F-3** (scratch per database): the demo's start no longer
  clears the real app's folder (the commit's test; G-3 is the scripts'
  case). Nothing globs `data\*.db` and trips on the new
  `data\tmp\verifier.db\` directory (grep), and find_db_copies walks
  files only.
- **5acbbad, F-4** (job object): `contain_self()` runs before any child
  exists. Microsoft's rule for SILENT_BREAKAWAY_OK in a job chain: a
  process breaks away from its immediate job and up the chain until it
  reaches a job that does not permit it. The supervisor's job does not,
  so the app's launcher (born in it), the interpreter (in the launcher's
  job, nested in it) and the ffmpeg that breaks away from the launcher's
  job all stay in the supervisor's job, and die with the supervisor
  (the commit's six-cold-starts test; G-6 is the app dying alone). The
  job handle is not inheritable (`CreateJobObjectW(None, …)`).
- **5acbbad, F-8** (stop file): stops the bot first, gives the app 300 s
  (uvicorn's graceful shutdown waits for request tasks, and checks run as
  BackgroundTasks inside the request's task), exits 0, so Task
  Scheduler's restart-on-failure does not bring it back; a stale file is
  removed at start. (Its test's race is G-4.)
- **c584e1d, F-2** (expiry): the store calls the Dispatcher back the
  moment any write drops a chat, and `expire()` reports every drop since
  the last call. The callback runs inside another chat's write; it only
  removes the dropped chats' marks, and a lock only when no handler of
  that chat is active (`dispatch` counts a handler before its task
  exists; a resumed `_deliver_late` counts itself at its first step, and
  the only thing that can run before that step is the poll loop's first
  `tidy()`, when that chat has no lock yet and its entry, just loaded, is
  under a day old).
- **c584e1d, F-6** (hand-over): counted in `in_flight` and `active` from
  the start, decided and delivered under the chat's lock, released in
  `finally`. The check-and-pop of `pending` is synchronous on both
  paths, so no double delivery either way.
- **c584e1d, F-9** (one bot): the lock is per data folder, taken after the
  free getMe and before anything else; a second copy exits 0 with a
  message, and serve_forever just retries it with its backoff.
- **1ae3cc3, F-12** (bot privacy text): `/privacy` and `/delete` say "our
  copy", the Sarvam sentence comes from `legal.sarvam_line()` behind the
  one switch, and every copy the bot's "30 din" covers is within 30 days
  (answers 30, cache ≤ 7, transcripts 30, the pending file ≤ 1).
- **Explorers, run from the extract with TEMP in scratch** (the restarts
  one writes only synthetic pending files there, removed at its end):
  `bot_explorer.py 2000` → "violations by invariant: none";
  `bot_explorer_restarts.py 3000 6000` (seeds 6000–8999, past the 4,000
  the commit reports) and `2000 0` → "violations by invariant: none";
  `2000 2000` → one I10, which is G-8 (a failed save), not the fixes:
  no I1 (paid while undelivered), I2, I3/I4 (double delivery), I5, I7,
  I8 or I9 in any of 9,000 seeds.
- **No copy of the real database in %TEMP%** by exact size (a metadata-only
  search; nothing opened), consistent with HANDOFF §0.
- **The suite on the extract**: 1314 passed, 2 failed, pytest exit 1, in
  a run sharing the CPU with this review's probes (11 min 36 s). The two:
  G-4, and the `test_logs` one in Notes. Both files alone: 18 passed,
  exit 0.
- **Mutants caught by the fixes' tests** (`probe\mutants.py`, one at a
  time in a second extract): M5 the restored-row check removed (F-13), M6
  the old per-directory folder (F-3), M10 the marker before the truncate
  (F-11), M11 the 30 s truncate wait and M12 a truncate that always says
  clean (F-7), M16 a fixed Sarvam sentence in the bot (F-12); and in the
  bot, M8 the hand-over not counted in flight (F-6). Surviving: G-7's
  three, and M7, M9 (Notes).

## Notes, not findings

- **The VACUUM's temporary copy goes to %TEMP% — but not at the real
  file's size.** Measured (`probe\vacuum_tempfile*.py`, TMP pointed into
  scratch): a 49 MB database's VACUUM wrote a 49 MB `etilqs_*` file to
  TMP, and a 5 MB one a 5 MB file, each deleted at the end; a 1.33 MB one
  (the real file's size) wrote none — it fits SQLite's page cache. So the
  first start leaves nothing in %TEMP%. If the rewrite is ever redone on a
  grown database (a reader blocked it), a full copy of people's messages
  sits in %TEMP% for the seconds it takes — S5-17's "never the system's
  temp folder". `PRAGMA temp_store=MEMORY` on the VACUUM's connection
  removes it (measured: none seen, same speed).
- **F-11's premise was slightly wide.** VACUUM was not the only write at
  startup that a held writer can fail: `sweep_orphans()` saves each
  orphan unguarded (only when there are orphans), and on this first start
  `init_db()` creates the two new tables (`daily_budget`, `ready_probe`).
  Both wait 30 s and then fail the start loudly; nothing is damaged, and
  nothing on this PC holds a write. Recorded so nobody assumes the start
  is write-proof.
- **Old working-file location.** Entries in `data\tmp\` itself (where
  344ef13–e039852 put them) are never cleared now that the folder is
  `data\tmp\<db name>\`. Only a demo hard-stopped in that window could
  have left one.
- **Mutant M7 survives** (224 ledger tests green): `record()` keeping the
  restored row on a LIVE finish would count twice — the commit says "a
  live finish replaces it", untested. The path needs a job's ledger row
  backed up, lost and restored before that job's own finish, so it is
  close to unreachable.
- **Mutant M9 survives** (129 bot tests green): `_deliver_late` without
  the chat lock. `in_flight` alone already stops the paid check; the lock
  only orders the replies (the answer before "not checked"). Not pinned.
- **`_deliver_late` counts `in_flight` through its whole wait** (up to
  4.5 min). If its entry expires meanwhile — only an entry already
  ≥ 23 h 55 min old at the restart — that chat's new messages are told
  "not checked" until the wait ends, instead of being checked.
- **`_forget` drops `prompted` unconditionally**, where `_let_go` keeps it
  while the chat has a pending entry. Through `expire()`'s delayed list a
  chat that re-entered `pending` since its drop could lose a fresh mark;
  that needs no `tidy()` for a whole 4.5-minute wait, against one per
  long poll, so it is not reachable today. `if chat_id not in
  self.pending` there would make it impossible.
- **Bot /privacy and Google.** It lists Anthropic, Sarvam and Telegram as
  keeping "their copy" and leaves out Google, which receives the start of
  the text. The web notice describes no Google retention either.
- **go-live.md small points.** `Read-Host "Windows password"` shows the
  password as it is typed (it is not kept in PSReadLine's history). The
  fallback block uses `$dir` from the block before it. "Taking it
  offline" does not say how to bring it back (`Start-ScheduledTask
  "Information Verifier"`, or a reboot). With the owner's own account and
  nobody signed in, OneDrive's client is not running: the backups land in
  the folder and leave the laptop only at the next sign-in. Later edits
  to `%USERPROFILE%\.cloudflared\config.yml` do not reach the service,
  which reads its own copy.
- **/ready through the tunnel.** Only `/dashboard` and `/api/v1/admin/`
  are fenced; `/ready` is public and writes a row on every call. It is
  tiny and Cloudflare is in front; pre-existing, not from this range.
- **`contain_self()`'s result is ignored**: if Windows refused the job,
  nothing is logged and the per-child assignment (the racy one) is all
  that is left.
- **find_db_copies**: a `-wal` left after its main file was deleted holds
  pages of messages and is not found (no SQLite header); `path.stat()`
  is not guarded against a file vanishing mid-walk. For the record, a
  metadata-only `find` (names and sizes, nothing opened) lists non-empty
  `*.db-wal` files left in %TEMP% outside pytest's folders by earlier
  sessions and tools: `…\4b88200f-…\scratchpad\pwa-check-1\demo.db-wal`,
  `…\4b88200f-…\scratchpad\supervise-smoke-1\demo.db-wal`,
  `…\09bde991-…\scratchpad\launcher_test.db-wal`,
  `%TEMP%\live_nn356c7i\live.db-wal`, `%TEMP%\tmptd0t0sn1\demo.db-wal`,
  `%TEMP%\freeze_*\t.db-wal` (two), plus Chrome's GPU caches. By their
  names they are demo or test databases, not the real one (none was
  opened); a `demo.db` holds whatever was typed into the free demo, so
  the owner may simply delete those folders.
- **One more full-suite failure, not reproduced:**
  `tests/test_logs.py::test_a_startup_line_reaches_a_piped_log_at_once`
  saw no startup line within its 20 s in the same loaded run as G-4, and
  passed alone. Its run printed only `assert ([])`, so no mechanism is
  named here.
