# Re-check of the step-5 review's fixes, and of step 4's runner

status: complete

Adversarial review (2026-10-16) of the commits that fixed the 18 findings in
[review-step5.md](review-step5.md) — 2e4562c, ebbe0aa, 300f375, ed88772,
df14115, 344ef13, ae85077 — and of the two step-4 commits never reviewed:
8a15b30 (`scripts/serve_forever.py`) and 800d26c (`docs/go-live.md`).
Findings are appended below the moment each is reproduced; "in progress"
above means the review was interrupted — re-run it, seeded from this file.

## Findings

Reproductions run from the scratch folder `review-fixes\` (no `.env`; every
key `invalid-audit-key`; DB_PATH inside that folder), against HEAD b6d8784.
No database copy of the real data was opened; files were judged by name,
size, date and the code that made them.

### F-1. Two more full copies of the real database are still on disk — S5-10's fix deleted the three copies its search found, and that search could not find these

- Severity: medium
- Status: CONFIRMED (by name, size, date and the script that wrote one; the
  files themselves were not opened)
- Where:
  1. `C:\Users\VINAYA~1\AppData\Local\Temp\upgrade_xdwvsb6c\copy.db` —
     1,273,856 bytes, 15 Oct 23:41. Made by the session scratch script
     `4b88200f-…\scratchpad\upgrade_copy.py` (also 15 Oct 23:41), whose
     docstring reads "does today's schema start cleanly on a COPY of the
     real database?" and which does `work = tempfile.mkdtemp(prefix=
     "upgrade_")` then `src.backup(dst)` from `real_db` (its argv[2]).
  2. `%TEMP%\claude\c--Users-…-Information-Verifier\2be1a3d1-e04f-4a17-b595-a8b7cbdd2694\scratchpad\verifier.db.before-upgrade`
     — 1,273,856 bytes, 22 Sep 20:04 (beside `PROJECT_PLAN.before0922`
     and `old_bot.py` from the same session).
- Evidence: `ls -la data/` gives the real `verifier.db` as 1,273,856 bytes
  with its `-shm` last touched 15 Oct 23:41 (the read-only open of the
  backup API); copy 1 is the same byte size, made the same minute. A
  `find` of every file in `%TEMP%` of exactly 1,273,856 bytes returns these
  two and nothing else. The three copies S5-10 listed are gone, but S5-10
  searched `-iname "*verifier*.db" -o -iname "*copy*.db"` over
  `%TEMP%\claude\…` only, and 300f375 deleted exactly the three it listed:
  - copy 1 is in `%TEMP%` itself — `tempfile.mkdtemp()`'s default, one
    level above every folder searched;
  - copy 2 is in a searched folder, but its name ends `.before-upgrade`,
    which neither pattern matches.
  Copy 2 holds whatever the real table held on 22 Sep, so it is past the
  notice's 30 days on 22 Oct; copy 1 on 14 Nov at the latest. No
  `forget.py` run or prune reaches either. 300f375's CLAUDE.md rule
  ("delete it … the moment the measurement ends") looks forward only; the
  commit that wrote it says "All three are deleted now" without a search
  that could have found the others.
- Suggested fix: delete both now (with any `-wal`/`-shm`). Find copies by
  the rule, not by name or place: every file under `%TEMP%` (all of it,
  not only `claude\`) and the repo whose size is a multiple of 4096 and
  whose first 16 bytes are `SQLite format 3\0`, then decide by size and
  date, never by reading rows. Scripts that copy the real database should
  take the destination folder explicitly (the scratch folder), never
  `tempfile.mkdtemp()`'s default.

### F-2. A chat whose day ran out stays in the bot's `prompted` set for the life of the process whenever another chat writes first — S5-2's rule, broken by S5-1's fix

- Severity: low
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:819-820` (`_write()` calls
  `_drop_expired()` and throws its list away), `:794-799` (`expire()` then
  finds nothing to report), `:1094-1101` (`tidy()` discards `prompted` only
  for the chats `expire()` returns), `:1080-1092` (`_let_go` ran long ago,
  while the entry was still pending, so it kept the mark).
- Evidence: `review-fixes\repro_prompted_leak.py` — chat 777's wait gives
  up (pending + prompted), a day and a minute pass in the same process,
  then either the poll loop's tidy-up or another chat's submit comes first:

                    tidy first: pending={} on_disk={} prompted=set() locks=[]
       other chat writes first: pending={} on_disk={} prompted={777} locks=[]
      RESULT: chat 777 stays in memory (prompted) past its day, until it writes again or the bot restarts

  The step-5 review's own S5-1 reproduction (`review-fixes\rerun\
  repro_bot_memory.py`, re-run at HEAD with only the clock seam moved to
  `PendingStore._clock`) shows the same: its step 3 is exactly "another
  chat's write" three days on —

      on disk   : {'888': {'job': 'job-of-another-chat', 'at': 1792435439.66}}
      in memory : pending = {888: 'job-of-another-chat'}  prompted = {777}  locks = []
      RESULT: dropped

  — so the fix passes the finding's disk half and fails S5-2's memory half
  in the finding's own scenario. Every `pending[chat] = job` (each submit)
  and every `pop` (each delivery) goes through `_write()`, so on a bot with
  any traffic the other chat's write usually wins the race against the next
  `tidy()` (one per long poll, up to 50 s apart). The mark is the person's Telegram chat id; it
  leaves only when that chat writes again — exactly what S5-2 reported for
  `prompted` ("a chat whose wait gave up stays until it writes again"), on
  the 24/7 server `serve_forever.py` keeps up for weeks, against the
  notice's "kept in the server's memory to count today's checks … the
  Telegram bot notes your chat number until your answer is delivered (at
  most a day)" (`app/api/privacy.html:86-89`). It is memory only, and
  harmless to behaviour (a stale mark without a pending entry changes no
  decision), so low.
- Suggested fix: make the store the one place that knows what expired —
  `_write()` keeps the dropped chats in a list that `expire()` returns (or
  an `on_expire` callback the Dispatcher passes in) — and test it with the
  other chat's write first, which the commit's tests never order that way.

### F-3. Starting the free demo server while the real app runs deletes the real app's working files: the lock is per database file, the folder it "protects" is per directory

- Severity: low
- Status: CONFIRMED
- Where: `app/store/scratch.py:20-21` (`folder()` = the database's
  DIRECTORY + `tmp`), `:31-45` (`clear()` removes every entry);
  `app/main.py:396-402` ("Safe here: this process holds the database's
  lock"); `app/store/instance.py:26-27` (the lock is `<db file>.lock`);
  `scripts/serve_demo.py:18` and `scripts/demo_offline.py:22`
  (`./data/demo.db`, beside the real `./data/verifier.db`), `:34`
  (`port=8000`, the real app's port).
- Evidence: `review-fixes\repro_shared_scratch.py` — this process holds
  `shared-data\real.db`'s lock with a voice note staged mid-decode in
  `scratch.workdir()`; a child runs the app's lifespan on
  `shared-data\demo.db`, as `serve_demo.py`'s start does:

      real app's working file : shared-data\tmp\tmpj4t5bege\src.ogg exists: True
      child: demo app started and stopped on demo.db | rc 0
      child said: [startup] removed 1 working file(s) a stopped run left behind
      real app's working file after the demo started: GONE (deleted under the running check)

  uvicorn runs the lifespan before it binds (instance.py's own docstring),
  so `serve_demo.py` — a "$0" command in CLAUDE.md's table — clears the
  live app's `data\tmp` and only then dies on "address already in use":
  the OPS-05 shape the single-instance lock was built to stop. A voice note
  caught between its write and ffmpeg's read is then refused as unreadable
  (422, untrue); a reel's download vanishing fails a job that was already
  funded (`fail_job` keeps the reservation and the person's daily check).
  Operator scripts that decode outside the app (`asr_probe.py`,
  `ab_models.py`) are exposed the same way to any app restart, which
  `serve_forever.py` now makes routine. The window is the seconds of a
  decode, so it is rare.
- Suggested fix: key the working folder by the database file, not its
  directory (`<db file>.tmp\`, or `tmp\<db file name>\`), so that the
  folder a process clears is exactly the one its lock covers.

### F-4. The app's own subprocesses (ffmpeg, yt-dlp's ffmpeg) outlive serve_forever in about half of its starts: the job is assigned after the venv launcher has already started the interpreter

- Severity: low
- Status: CONFIRMED (8 cold starts, measured; Task Scheduler itself not run)
- Where: `scripts/serve_forever.py:178-181` (`Popen`, THEN `_contain`),
  `:120-132` (`_contain` imports ctypes and builds the job on its first
  call — the app's start at boot), `:52-53`/`:57` (`sys.executable` is
  `.venv\Scripts\python.exe`, CPython's venv launcher, which starts the
  base interpreter in a job of its own with
  `JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK`); the claim at `:19-22` ("they
  die with it, however it dies").
- Evidence: `review-fixes\repro_job_nesting_cold.py` — each run a fresh
  process that, like serve_forever, has not imported ctypes; it `Popen`s
  the venv python with `CREATE_NEW_PROCESS_GROUP`, calls the real
  `_contain`, and the supervised interpreter starts a grandchild (`ping`,
  standing in for ffmpeg); then the outer process is killed, as Task
  Scheduler's End or a crash does:

      run 1: in serve_forever's job (launcher, interpreter, grandchild) = ['True', 'False', 'False']; alive after it was killed: ['grandchild']
      run 2: ... = ['True', 'True', 'True']; alive after it was killed: nothing
      ...
      run 5-7: ['True', 'False', 'False'] ... ['grandchild']   (4 of 8 runs)
      cleanup: strays left: none | killed by cleanup: [31648, 46804, 47400, 9864]

  With ctypes already imported (a restart later in the same run;
  `repro_job_nesting.py`) all three were inside in 3 of 3 runs. So the
  race bites the FIRST start, which is the app's — the process that runs
  ffmpeg (`app/providers/media.py`, `normalize_to_wav`/`split_wav`) and
  yt-dlp's post-processing. The interpreter itself still dies (through the
  launcher's own job when the launcher is killed); its children escape,
  because the launcher's job lets them break away silently and the
  supervisor's job does not hold the interpreter. An escaped ffmpeg has
  lost the 120 s timeout its parent enforced ("a crafted file must not pin
  a worker forever"), and it holds a person's voice note open in
  `data\tmp` while the restarted app's `scratch.clear()` runs — which
  skips files held open ("the next start tries again"), so the note stays
  until the NEXT restart, weeks away under serve_forever (S5-17's leftover,
  moved, not removed).
- Suggested fix: put serve_forever itself in the job before it starts
  anything (`AssignProcessToJobObject(job, GetCurrentProcess())` in
  `main()`), so every descendant is born inside a job that does not allow
  breakaway; test it the way above (cold, eight runs, a grandchild).

### F-5. go-live.md's cloudflared service runs no tunnel: it leaves out the registry step that makes the service run `tunnel run` with the copied config

- Severity: medium
- Status: CONFIRMED by trace (Cloudflare's own page and cloudflared's
  source, read 2026-10-17; cloudflared was not run, per this review's
  rules)
- Where: `docs/go-live.md:113-129` (mkdir + copy the config and credentials
  into `C:\Windows\System32\config\systemprofile\.cloudflared`, edit
  `credentials-file`, then `cloudflared service install`; the check
  "Get-Service cloudflared shows Running, and the site still loads after
  closing the `tunnel run` window").
- Evidence: Cloudflare's "Run as a service — Windows" page for a locally
  managed tunnel (fetched 2026-10-17) has, after `cloudflared.exe service
  install` and the copies, step 13 "In the Registry Editor, go to
  `Computer\HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Services\Cloudflared`"
  and step 14 "modify `ImagePath` to … `C:\Cloudflared\bin\cloudflared.exe
  --config=C:\Windows\System32\config\systemprofile\.cloudflared\config.yml
  tunnel run`" (then `sc start cloudflared` if it does not start).
  go-live.md has neither. cloudflared's source (master,
  `cmd/cloudflared/`): `installWindowsService` fills `extraArgs` only in
  the token branch, so without a token the service is registered as the
  bare executable; the service's `Execute` then falls back to `os.Args`
  ("fall back to the arguments from ImagePath"); `main.go`'s action sends
  an invocation with no arguments and no flags to `handleServiceMode`
  ("cloudflared was started without any flags"), whose `AppService`
  `handleConfigUpdate` starts services only for `c.Forwarders`, with
  "// TODO: TUN-1451 - tunnels". The `tunnel:`/`ingress:` in config.yml
  are never read on that path. So
  `Get-Service` reports Running — the first half of the doc's check passes
  — and the site goes down the moment the `tunnel run` window closes. The
  check then fails with no next step in the doc, and HANDOFF's step 4 waits
  on this page. home-tunnel.verification.md F11 records that Cloudflare's
  Windows-service page was "not re-fetched"; the runbook was written from
  the research's one-line summary of it.
- Suggested fix: add the ImagePath edit as a command (`Set-ItemProperty
  'HKLM:\SYSTEM\CurrentControlSet\Services\Cloudflared' ImagePath
  '"<path to cloudflared.exe>" --config="C:\Windows\System32\config\systemprofile\.cloudflared\config.yml" tunnel run'`,
  quoted for the spaces, with `(Get-Command cloudflared).Source` for the
  path), then `Restart-Service cloudflared`. Keep the "closing the window"
  check: it is the one that catches this.

### F-6. After a restart, a message that arrives while the bot is handing over the previous answer is checked and paid for automatically — the restart path delivers outside the chat's lock and the in-flight count (found by extending the explorer)

- Severity: low
- Status: CONFIRMED (explorer: 10 of 6,000 seeds, every one on the resumed
  job; one traced step by step)
- Where: `scripts/telegram_bot.py:1113-1130` (`_deliver_late`: `pending.pop`
  at `:1128`, then two awaited sends at `:1129-1130`, holding neither
  `locks[chat]` nor an `in_flight`/`active` count); `:1049-1051`
  (`dispatch` decides `busy` from `pending` and `in_flight` only); the
  rule it breaks, `handle_message`'s docstring at `:859-863` ("A message
  that arrives while the chat's previous check is undelivered is NEVER
  checked automatically"). Pre-existing since the restart path (OPS-07),
  not introduced by df14115 — but df14115's commit names the explorer as
  its proof, and the shipped explorer never calls `resume()`.
- Evidence: `review-fixes\explorer_ext.py` (the shipped explorer plus a
  persisted `PendingStore` on a fake clock, a previous run's entry resumed
  at start, `tidy()` and a day passing at random points; the shipped
  invariants kept, relaxed only for entries that expired by design):

      seeds run: 2000
      violations by invariant: {'I8': 18, 'I9-prompted': 18, 'I1': 4}
        first I1: seed=759: I1 chat 2 submitted 'c2-m1 5G se corona phailta hai sach' while j0 (done) was undelivered
      seeds run: 4000   (seeds 2000-5999)
      violations by invariant: {'I8': 29, 'I9-prompted': 29, 'I1': 6}

  (I8/I9 are F-2. Nothing else in 6,000 seeds: no unanswered message, no
  double delivery, no lock or handler count left, no day-old entry on
  disk, no hang.) `review-fixes\trace_seed.py 759`:

      pending.pop(2) -> j0  (by Dispatcher._deliver_late)
      send start chat 2 by Dispatcher._deliver_late: 'Aapka pichla check pura hua:'
      dispatch chat 2: 'c2-m1 5G se corona phailta hai sach' busy=False
      send done  chat 2: 'Aapka pichla check pura hua:'
      send start chat 2 by Dispatcher._deliver_late: 'REPORT-j0 ...'
      send start chat 2 by Dispatcher._run: '🔎 Checking… thoda time lagega (1–3 min).'
      SUBMIT chat 2: 'c2-m1 5G se corona phailta hai sach'
      send done  chat 2: 'REPORT-j0 ...'

  The window is the two Telegram sends, each up to three attempts with a
  30 s timeout and 3 s backoff (`_tg_retry`) — on this machine, where
  Telegram was measured slow, seconds to minutes. It opens exactly when a
  person is most likely to write: right after a restart (serve_forever,
  a Windows Update reboot), while waiting for an answer. No double
  delivery and no lost reply in 6,000 seeds; the cost is one automatic
  paid check of a message the bot's own rule says to hold (a repeat of a
  COMPLETE, cached claim stays free).
- Suggested fix: in `_deliver_late`, decide and deliver under
  `locks.setdefault(chat_id, asyncio.Lock())`, counted in `active` (and
  let go through `_let_go`), so a message arriving meanwhile queues behind
  it and is judged with `busy_on_arrival`; keep `explorer_ext.py`'s
  restart and expiry actions in `scripts/bot_explorer.py`.

### F-7. truncate_wal() lets any open reader stall every write in the app for ~30 s, and then gives up silently — the WAL is not truncated exactly when someone is reading

- Severity: low
- Status: CONFIRMED (mechanism measured; the trigger in production is an
  owner habit, PLAUSIBLE)
- Where: `app/store/db.py:156-163` (`PRAGMA wal_checkpoint(TRUNCATE)` on a
  connection with the 30 s busy timeout, result ignored);
  `app/store/repository.py:551` (every `forget()`, run by forget.py in a
  second process) and `:659-661` (housekeeping, every 6 hours).
- Evidence: `review-fixes\repro_truncate_blocks_writers.py` and
  `repro_truncate_write_fails.py`, the app's own `get_conn`,
  `truncate_wal`, `AnswerRepository.save` and `DailyQuota.take` on a
  scratch database, one connection holding a read transaction:

      reader held    5 s, no checkpoint     : the app's write took   0.0 s
      reader held    5 s, with truncate_wal(): the app's write took   5.1 s; truncate_wal took   5.5 s
      reader held past the 30 s busy timeout: the TRUNCATE checkpoint returned after 32.8 s with busy=1 (1 = gave up, silently: no exception), WAL now 37112 bytes

      (40 s reader) truncate_wal()             :  32.8 s, ok (None)
                    a finished answer's save   :  32.5 s, ok (None)
                    a claim's daily-slot take  :  32.4 s, ok (True)

  Under WAL a reader never blocks a writer — the reason the app uses WAL
  (db.py:117-121). A TRUNCATE checkpoint takes the writer lock and then
  waits for readers, so with it every save, ledger write and claim waits
  for whoever is reading: here 32 s, within one second of their own 30 s
  busy timeout (past it they fail — fail-closed 503s for claims, and the
  OPS-06 "finished but could not be saved" path for answers). Then the
  checkpoint returns `busy=1`, which nothing reads: forget.py prints
  "Deleted …" and the deleted message's earlier page versions stay in
  `verifier.db-wal` until a later truncate succeeds — S5-11's guarantee
  fails silently in the one situation it is tested against. The app's own
  readers are milliseconds long, so the trigger is a reader from outside:
  a DB browser left open on the real file (OPS-06's own example), or any
  script holding a cursor.
- Suggested fix: run the truncate on a connection with a short busy
  timeout (`PRAGMA busy_timeout=1000`) so it can never hold writers for
  long; read its result row, and when `busy` is 1, say so (forget.py: "the
  file still holds the old copy until the next housekeeping — close any
  program reading the database and run again") and retry at the next
  housekeeping rather than report success.

### F-8. Under Task Scheduler the supervisor's ordered stop never runs: "End" and every reboot are hard kills, so the runbook's "Taking it offline" drops checks in flight with no bot-first ordering

- Severity: low
- Status: PLAUSIBLE (traced; Task Scheduler not run, per this review's rules)
- Where: `scripts/serve_forever.py:326-333` (stop only on SIGINT, SIGTERM
  or SIGBREAK — console events), `:306-309` (the ordered stop lives in
  `run()`'s `finally`); `docs/go-live.md:164-165` ("Task Scheduler → … →
  End … Its children stop with it"); the commit's claim "stops the bot
  first, then the app, on Ctrl+C or a stop signal".
- Evidence: the console itself is not the problem — measured
  (`repro_ctrl_break.py`, and `repro_ctrl_break_detached.py` with the
  supervisor started DETACHED): the venv launcher's interpreter always gets
  a console, and `Child.stop()`'s CTRL_BREAK reached a SIGBREAK handler
  through the launcher in 0.1 s, exit code 0, both times. The problem is
  that nothing ever asks it to stop: a task registered "whether user is
  logged on or not" runs in session 0, and the runbook offers no way to
  send that console a Ctrl+C or Ctrl+Break. Task Scheduler's End uses `TerminateProcess` (Microsoft
  documents `-DisallowHardTerminate` as "the task cannot be terminated by
  using TerminateProcess"), and a reboot ends console processes without a
  signal Python maps. So the `finally` never runs: no "stopping" line in the
  supervisor log, no bot-first order, and the app and bot die together
  through the job object (F-4's escapees aside) —
  `repro_job_nesting_cold.py` kills its supervisor the same way and none of
  its children got a signal. Every check in flight is paid for and becomes
  "The server restarted while this check was running" at the next start.
  (Even the graceful path keeps only 15 s, shorter than a 1–3 minute check;
  the order mostly stops NEW submissions.)
- Suggested fix: give the supervisor a stop it can receive unattended —
  e.g. it polls for `data\serve_forever.stop` each tick, then stops the bot,
  waits for the app's running checks to end (or a few minutes), stops the
  app and exits 0 — and make the runbook's "Taking it offline" create that
  file and wait for "stopping" in `logs\supervisor-<today>.log` before End.

### F-9. With the runbook's fallback service account, "Everything stops: run start.cmd" starts a second Telegram bot beside the supervisor's

- Severity: low
- Status: PLAUSIBLE (the detection gap measured; two pollers not run)
- Where: `start.ps1:21-24` (`Get-PythonRunning` matches `CommandLine`
  from `Get-CimInstance Win32_Process`), `:79-85` (starts a bot when none is
  found); `docs/go-live.md:150-153` (the separate LOCAL standard account
  for the service) and `:161` ("Everything stops: sign in, run
  `start.cmd`"); `scripts/telegram_bot.py` has no single-instance lock
  (serve_forever has one, `serve_forever.py:319-325`, for itself only).
- Evidence: from this (non-elevated) session, WMI gives `<null>` for the
  command line of every process owned by another account:

      elevated: False
      Name        ProcessId owner CommandLine
      svchost.exe      1840       <null>
      svchost.exe      1972       <null>   …

  So when serve_forever runs as the service account, the owner's
  `start.cmd` finds the app (its `/health` answers: "already running") but
  not the bot, and opens a second one. "Everything stops" is how a
  cloudflared or network outage looks from a phone while serve_forever is
  fine, so the runbook leads straight there. Telegram allows one
  `getUpdates` poller: the two alternate on 409 Conflicts (each retrying
  every 5 s), each update reaches whichever polled, both rewrite the one
  `data\bot_pending.json` from their own memory (so a restart can no
  longer resume the other's checks — OPS-07), and the per-chat lock and
  `busy` judgement no longer see a chat's whole burst. The API's
  one-check-at-a-time rule still stops a double payment for overlapping
  checks.
- Suggested fix: a single-instance lock in the bot itself
  (`instance.acquire` on `data\telegram_bot`, as serve_forever does), so a
  second copy refuses whoever starts it and whatever account it runs as;
  and in the runbook, "Everything stops" first checks
  `logs\supervisor-<today>.log` before starting anything.

### F-10. The runbook's fallback account cannot start the service at all: the venv's interpreter and ffmpeg live in the owner's profile, which only the owner can read, and the runbook grants only the project folder

- Severity: medium
- Status: CONFIRMED (by `pyvenv.cfg` and the folders' own ACLs, read with
  `icacls`; no second account was created)
- Where: `docs/go-live.md:150-153` ("If your account signs in with a PIN
  or a Microsoft account and this fails, the research's advice is a
  separate **local** standard account for the service. That account needs
  read and write access to the project folder."), `:139-140` (the action
  runs `$dir\.venv\Scripts\python.exe`).
- Evidence:

      base python: home = C:\Users\Vinayak Mokashi\AppData\Local\Programs\Python\Python312
      ffmpeg: C:\Users\Vinayak Mokashi\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_…\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe
      icacls …\Python312 : NT AUTHORITY\SYSTEM:(OI)(CI)(F)  BUILTIN\Administrators:(OI)(CI)(F)  VINAYAK45\Vinayak Mokashi:(OI)(CI)(F)
      icacls C:\Users\Vinayak Mokashi : the same three (plus one app-container SID)

  `.venv\Scripts\python.exe` is CPython's venv launcher: it reads
  `pyvenv.cfg` and starts `home\python.exe`, a folder a standard account
  other than the owner cannot read. So the task's process fails before any
  of serve_forever runs; the runbook's check ("restart the PC … the site
  answers and the bot replies") fails with nothing in `logs\` to say why.
  Had the interpreter started, ffmpeg would be missing for that account
  too — it is in the owner's per-user WinGet folder and on the owner's
  PATH only — and `/ready` would refuse every voice note and reel.
  home-tunnel.md (F11) names "ffmpeg on PATH" for the service account;
  the runbook dropped it. This is the path the runbook sends the owner
  down when registering with his own account fails, which its own
  verification calls common for Microsoft-account and PIN sign-ins.
- Suggested fix: for the fallback, either install Python for all users
  (and recreate the venv from it) and ffmpeg machine-wide, or grant the
  service account read+execute on exactly the interpreter folder and the
  ffmpeg folder (`icacls <folder> /grant "<account>:(OI)(CI)RX"`) and put
  ffmpeg on that account's PATH; then a check that runs as that account
  before the reboot (`runas /user:<account> "<venv python> -c \"import
  app.main\""` and `/ready` from it).

### F-11. The one-time VACUUM is the only unguarded write at startup: an open write transaction on the database now stops the app from starting, where before it only slowed the start

- Severity: low
- Status: CONFIRMED (measured on scratch databases with the app's own
  `vacuum_once`; the startup consequence by code trace)
- Where: `app/main.py:404-408` (`await asyncio.to_thread(vacuum_once)`, no
  `try`), `app/store/db.py:136-153`; compare `app/store/repository.py:
  665-669` (each housekeeping step catches its own failure) and
  `db.py:207-…` (`init_db` on an existing database only reads:
  `CREATE … IF NOT EXISTS`, the version check).
- Evidence: `review-fixes\repro_vacuum_reader.py`:

      nothing held                : vacuum_once -> True after 0.0 s
      a reader held 40 s          : vacuum_once -> True after 32.8 s (still running after 5 s: True)
      a writer held 40 s          : vacuum_once -> 'RAISED OperationalError: database is locked' after 32.8 s (still running after 5 s: True)

  Raised inside the lifespan, that is a failed start: start.cmd's window
  shows a traceback; serve_forever restarts it every 5 s → 5 min until the
  writer lets go, alerting the owner hourly. Before 344ef13 the same held
  writer cost a slower start (each blocked housekeeping step logs its
  "database is locked" and moves on) — the app still came up. A held
  reader (a DB browser left open) costs the first start 33 s and then
  leaves the rewrite in the WAL: `vacuum_once`'s own TRUNCATE gives up as
  in F-7 while the `meta` flag already says it is done, so the file keeps
  the old free pages until a later checkpoint completes. It runs once, so
  the window is the first start after the upgrade — the one the commit's
  NOTE asks the owner to expect.
- Suggested fix: catch and log the VACUUM's failure at startup (the flag
  is only written after success, so the next start tries again), and set
  the flag only after the checkpoint reports `busy=0`.

### F-12. The bot still tells Telegram users their message "is deleted after 30 days" — S5-4 and S5-14 corrected the web notice only, and for bot users the bot's text is the whole notice

- Severity: medium
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:127-129` (`privacy_text`: "Message aur
  jawab {30} din baad delete ho jaate hain"), `:152-156` (`delete_text`:
  "Aapka message aur jawab {30} din mein apne-aap delete ho jaate hain"),
  `:133-135` (the full notice is linked only when `public_url("privacy")`
  exists, i.e. once PUBLIC_HOSTS is set); against `app/api/legal.py:76-80`
  and `privacy.html:62-64` as ebbe0aa and ae85077 left them.
- Evidence: `review-fixes\repro_bot_privacy_claims.py`, switch at its
  default (today's state), no public address yet:

      web notice, Sarvam line   : ['videos, to turn it into text. Sarvam may keep it, under its own terms.</li>']
      web notice, 'In short'    : ['checked. We delete our copy after 30 days; the services keep']
      bot /privacy links notice : False
      bot /privacy              : • Message aur jawab 30 din baad delete ho jaate hain. …
      bot /delete               : … Aapka message aur jawab 30 din mein apne-aap delete ho jaate hain.

  S5-4's rule was "a promise the code cannot check needs either a switch
  or wording that is true until the switch is thrown"; S5-14's, "say
  exactly what is ours". Both were applied to the web page, which is not
  public yet. The bot is public now, it is where voice notes reach Sarvam
  today, and its `/privacy` has no notice to link to — so Telegram users
  read an unqualified "deleted after 30 days" while Sarvam keeps their
  audio under its own terms (indefinitely until the owner's dashboard
  change, policy-legal.md F10) and Anthropic may keep flagged content for
  up to two years (privacy.html:103-107). The same pattern S5-9 found
  (a fix keyed to the web surface, the bot missed).
- Suggested fix: the bot's two lines say "our copy" and carry the same
  Sarvam sentence as the notice, from one place both read (e.g. a
  `legal.sarvam_line()` used by `legal.render` and `privacy_text`), with
  a test that the bot's text changes with `SARVAM_ZERO_RETENTION` too.

### F-13. After a ledger restore, the stale-row sweeps count a check twice: S5-12's fix taught the backfill about hashed rows, not the other INSERT-OR-IGNORE writer

- Severity: low
- Status: CONFIRMED (the whole chain run with the app's own functions;
  its preconditions are rare)
- Where: `app/store/repository.py:288-299` (the backfill skips an answer
  whose `ledger_ref` is among the restored rows), `:574-578`
  (`_record_abandoned` → `record(..., overwrite=False)`, keyed by the raw
  job id, no such check), called by `sweep_orphans` (`:603`, every
  start) and `sweep_stale` (`:638`, every few minutes);
  `app/engine/job.py:212-216` (the ledger row is written even when the
  finished answer could not be saved, leaving that row PROCESSING);
  `app/store/backup.py:86-90` (restore's promise: "never doubles the
  money").
- Evidence: `review-fixes\repro_ledger_sweep_double.py`:

      1. save failed, ledger written   : (1, 0.16)
      2. daily backup                   : ledger-2026-10-16.db
      3. ledger lost, restored          : 1 row(s) -> (1, 0.16)
      4. next start: sweep_orphans()    : 1 row(s) failed -> (2, 0.32)
         and housekeeping's backfill    : (2, 0.32) (one check that cost $0.16)

  The restored row carries `ledger_ref(job_id)`; the sweep's INSERT OR
  IGNORE carries the job id, so nothing conflicts and the money is
  counted twice in the record CLAUDE.md calls "the spend truth". Five other
  orders of backup, loss, restore, backfill and a second restore were
  lossless and counted once (`repro_ledger_orders.py`); the sixth, a live
  `record(overwrite=False)` after a restore, doubled — the same write the
  sweeps make.
- Suggested fix: put the rule in the one writer, not in a caller —
  `SpendLedger.record` refuses (or replaces) when a row with
  `ledger_ref(job_id)` exists — and test it through `sweep_orphans`, not
  only through the backfill.

## Summary

13 findings: **0 high, 4 medium, 9 low**. 11 CONFIRMED (F-5 by trace of
Cloudflare's page and cloudflared's source; the rest by reproduction), 2
PLAUSIBLE (F-8, F-9: Task Scheduler and a second account could not be run).

- Medium: F-1 (two more full copies of the real database on disk), F-5
  (the cloudflared service runs no tunnel), F-10 (the fallback service
  account cannot start Python), F-12 (the bot still says "deleted after 30
  days").
- Low: F-2 (`prompted` keeps a chat id past its day), F-3 (the demo's start
  clears the live app's working files), F-4 (ffmpeg escapes the job in
  half of cold starts), F-6 (restart path: a message during the hand-over
  is checked automatically; pre-existing, found by the extended explorer),
  F-7 (the WAL truncate makes readers stall writers, then gives up
  silently), F-8 (no ordered stop under Task Scheduler), F-9 (start.cmd can
  start a second bot), F-11 (the one-time VACUUM can fail the start),
  F-13 (a restore plus a sweep counts a check twice).
- Fixes that covered the case named but not the rule behind it: 300f375
  (F-1), df14115's S5-1 against S5-2 (F-2), 344ef13's S5-17 (F-3, F-4),
  S5-11 (F-7) and S5-12 (F-13), ebbe0aa and ae85077 on the web only (F-12).
  New defects in code never reviewed before: F-4, F-5, F-8, F-9, F-10
  (step 4), F-11 (344ef13).

Checked and found sound:
- 2e4562c (S5-3): the original midnight repro now refuses with forget_idle
  at 00:00:10 as without it. The refusal is raised inside the lock before
  anything is taken (`reserve` unadmits; the two-phase `fund` releases
  through `_quota`, with `spend.day` still None). `fund` takes its day one
  database read before the lock, so the 5-minute grace covers both paths,
  and days are ISO strings, so `>` is chronological. Residual, measured
  with the commit's own `_day_ago` seam: a claim stalled past 5 minutes is
  still judged on an emptied table (forget_idle clears without
  re-dating). Only a sleeping machine stalls that long, and go-live.md sets
  sleep to Never.
- ebbe0aa (S5-4): the web notice's Sarvam sentence follows the switch
  both ways, no other web page claims retention, and the app
  (PUBLIC_HOSTS) and the bot both warn while it is unset. The bot's own
  wording is F-12.
- 300f375 (S5-10): the three listed copies are gone, with no -wal/-shm
  left. F-1 covers the other two.
- ed88772 (S5-7, 8, 18): all four original repros pass. A reel is found
  by its link and its transcript goes; a pasted address works; a cached
  repeat saves once and a deletion in between stays done; a viral
  forward's `--yes` deletes nothing without `--all`, and the listing shows
  India time. No other writer re-saves a finished row: `fail_job` and the
  sweeps act only on QUEUED/PROCESSING rows, checkpoints are conditional
  UPDATEs, and `_finish` only reads. Every `forget()` caller takes the
  3-field result. Keeping `input_text` as sent changes nothing that reads
  it: the cache key comes from the gathered text, and the page shows the
  link as text.
- df14115 (S5-5, 6, 9, 13): the original repros pass.
  - Every never-submitted kind leaves the claim checked.
  - `/status` and `/result` deliver a waiting answer.
  - "/privacy?", "/stop." and "/cancel please" are commands; "/startup…"
    and "/helpline…" claims are checked.
  - The bot warns at start, and `/delete` is honest.
  The shipped explorer (2,000 seeds) is clean. The extended one (6,000
  seeds, with expiry, `tidy()` and `resume()`) found no double payment for
  one check, no double delivery and no unanswered message. Locks, `active`
  and `in_flight` never outlive their handlers, and no day-old entry stays
  on disk; only F-2 and F-6 appeared.
- 344ef13 (S5-11, 12, 16, 17):
  - Every live connection goes through `get_conn`, so `secure_delete`
    covers all of them.
  - The remanence repro finds the message 0 times in the file and the WAL.
  - The ledger-keys repro's backup holds only a 64-hex reference, which
    opens nothing.
  - The stream repro gets a 404. Every terminal stream event follows the
    final save attempt, so the finished-stream row check cannot race a
    job's save.
  - Five orders of backup, loss, restore, backfill and a second restore
    are lossless and count once.
  - Nothing depends on rowids that VACUUM may renumber.
  - Startup runs lock → init_db → clear → vacuum → sweeps → housekeeping,
    with the backup last, and `truncate_wal` never runs on the event loop.
  - The suite run with DB_PATH at a canary file never created it.
- ae85077 (S5-14, 15): the cache TTLs (7 days, 1 day) sit inside "we delete
  our copy after 30 days". The iOS rule works: Safari, Chrome and Firefox
  for iOS carry "Safari/" and bare web views do not, and the hint's last
  line covers in-app browsers that pass as Safari.
- serve_forever.py:
  - Logs go only to `logs\` (git-ignored). The only job ids it can log are
    of jobs already gone (404).
  - No spin: a 1 s tick, and restart pauses from 5 s doubling to 5 min,
    reset after a 10-minute run.
  - One supervisor at a time: its own lock, exit code 3.
  - CTRL_BREAK reaches a SIGBREAK handler through the venv launcher, even
    when started detached; uvicorn 0.51 handles SIGBREAK.
  - The launcher and the interpreter always die with it; F-4 is about
    their children.
  - Restart alerts are sent from a script with no event loop.
- go-live.md:
  - `-ExecutionTimeLimit ([TimeSpan]::Zero)` lifts Task Scheduler's 3-day
    default.
  - `-RestartCount 999` passes Task Scheduler's own validation (validate
    only, nothing registered), despite the schema's unsignedByte.
  - The action's quoting survives the spaces in the path.
  - The ingress fence comes first, and its regex covers both local-only
    routes. The app's `is_this_machine` refuses tunnel traffic anyway.
- Suite on a `git archive b6d8784` snapshot: 1291 passed, pytest exit 0.
  The real `data\verifier.db` was not opened; its size and timestamps are
  unchanged; no stray processes remain.

Notes, not findings: Task Scheduler's default priority 7 runs the app, the
bot and ffmpeg below normal priority on a PC the owner also uses. A bare
job id typed in capitals is not found by forget.py, but the page does not
accept one either. An unknown command plus two words ("/check 5G se
corona") gets the help text, not a check.

Correction (2026-10-17, measured offline with `classify_message`): the
example has three words, and "/check 5G se corona" IS checked as text.
The help text comes for one or two words after an unknown command
("/check 5G se"), as `_COMMAND_WORDS_MAX = 2` intends.
