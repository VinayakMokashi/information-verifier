# Review — the 2026-10-18 to 2026-10-28 session's code commits

status: complete (2026-11-10; a fresh, adversarial reviewer)

HEAD reviewed: 7ae8487a82a894e9b2ff569881dbcf9f971f535a (7ae8487, 2026-10-28)

## Summary

**Nothing high or medium; nothing that endangers money, the live site's
availability, or data beyond a rare edge.** 5 findings, **0 high, 0
medium, 5 low**, all CONFIRMED (H-1's frequency PLAUSIBLE). Every
commit's own test fails against its broken version (10 mutants, all
caught). G-6 holds under the production job nesting with a real ffmpeg.

| ID | Severity | Live? | One line |
|---|---|---|---|
| H-2 | low | **yes** | The page's CSS arrows are in the accessible names: "Check →", every chip "… →", every source "… ↗" (7d84246) |
| H-5 | low | **yes** | Light theme: the AI/18+ disclaimer line and the new "Try one" label are 2.99:1 (`--ink-3`; the colour predates 7d84246, which weighed contrast for the button only) |
| H-1 | low | code is live; rare | A dead run's voice note survives an app start when its pid now belongs to any live process — after a reboot ≈4%; "access denied" counts any SYSTEM process (486a795, G-3's rule only by number) |
| H-3 | low | operator tool | `forget.py --yes` with a mistyped id ends: "The database file is clean now: no earlier copy of the deleted text is left in it." (aaf5398, new in the fix) |
| H-4 | low | operator tool | find_db_copies labels a full copy of the database "the app's own backup" because of its folder (f9fd678, G-1's rule only by folder) |

Fixes that covered the case named but not the rule: H-1 (G-3: liveness
by number), H-4 (G-1: identity by folder). New defects inside the fixes:
H-3 (G-5). The page: H-2, H-5. The rest is under "Checked and sound"
(G-2, G-4, G-6, G-7, G-8, 5455a6e, 7d78981 have no finding) and "Notes".

**Clean-up:** the demo server on port 8020 and the probe's headless
Chrome were stopped (checked by command line: none left; 8020 closed).
Every synthetic database, WAL, lock, backup and planted voice note
(`review-session\dbs\`), the three Chrome profiles, the mutant extract
and the explorers' temp folder were deleted; a header scan of the
review's scratch folder then found `294 files scanned, 0 SQLite or WAL
files`. Port 8000, the scheduled task, the cloudflared service, the real
`data\` and `.env` were never touched (the real `logs\` was read only);
https://informationverifier.com/ answered 200 at the end. pytest's own
temporary folders (`%TEMP%\pytest-of-…`, from the baseline and mutant
runs, pruned by pytest) were left to pytest. The probes named here are
in this session's scratch (`…\scratchpad\review-session\probe\`), which
the next session cannot see; each finding says what its probe does.

## Scope

The code commits of the 2026-10-18 to 2026-10-28 session:

- 82b0708 G-8: app/files.py replace() retry; PendingStore unsaved flag rewritten at tidy(); backup.py uses it
- 6eb2e57 G-2: housekeeping failures alert the owner
- 4838389 G-4: serve_forever consumes the stop file after the stop; the test waits for children to be up
- aaf5398 G-5: forget.py --yes with no match finishes the WAL
- f9fd678 G-1: find_db_copies lists every project-schema DB except pytest's folders; orphaned -wal
- 486a795 G-3: scratch working files per process id; clear() keeps live processes' folders
- 7f35db8 G-7: tests that run both main()s
- ea2e82c G-6: app/processes.py (job object + liveness); the app contains itself when VERIFIER_SUPERVISED=1
- 5455a6e: disclaimers say "written by AI", no model name
- 7d78981: VERIFIER_ENV_FILE — the test suite reads no .env
- 7d84246: the page redesign (static/index.html)

Not in scope: the live logs (bot ReadTimeouts, the 2026-11-03 app errors) —
the main session is investigating those.

## Method

- Work only in a `git archive HEAD` extract in this session's scratch folder
  (`…\scratchpad\review-session\repo`); no `.env`, no `data\`. The live site,
  its scheduled task, the cloudflared service and the real `data\` are not
  touched; `.env` is not read.
- For each commit: (1) does it cover the rule or only the named case; (2) did
  it add a defect; (3) would its test fail against the broken version (a
  mutant in a second extract).
- Probes set `VERIFIER_ENV_FILE=""` and dummy keys before importing `app`, and
  point DB_PATH into scratch. Any server binds a port other than 8000.
- Spend nothing: no paid scripts, no API calls; GETs to the public site only.
- G-7 is test code only: its own mutants (M13–M15) were not re-run; its
  main() driver was read (it stubs `ready`, `notify` and the logs folder,
  so it never reaches the live app on port 8000 or the owner's phone).
- The page: the extract served by a demo-mode server on port 8020 (the fake
  stages applied as serve_demo.py does), headless Chrome with throwaway
  profiles, accessible names and layout read over CDP.

## Findings

### H-1 — low — CONFIRMED (mechanism), PLAUSIBLE (frequency): a dead run's voice note survives an app start when its pid belongs to any live process (486a795, G-3)

- **Where:** `app/store/scratch.py` `clear()`, with `app/processes.py`
  `process_alive()`.
- **Rule it breaks:** S5-17's — what a hard stop left mid-decode is removed
  at the next start, so a voice note never outlives the privacy notice's
  promise ("your message … deleted after 30 days"). G-3 keeps a folder whose
  name is the pid of *a* live process, not of *the* process that made it.
  Windows reuses pids, and "access denied" counts as alive, so every SYSTEM
  process and every other account's process counts too.
- **Evidence** (probe `g3_clear.py`: a synthetic `data\tmp\verifier.db\<pid>\tmpdead\voice-note.ogg`
  under scratch, named after explorer.exe's pid and lsass.exe's pid, then
  `scratch.clear()` as the app's start calls it). It printed:
  `process_alive: {14216: True, 1700: True}` / `removed: 0` /
  `14216 voice note still there: True` / `1700 voice note still there: True`.
- **How often:** not after a crash-restart — probe `pid_reuse.py`, shaped
  like serve_forever (venv launcher + interpreter, `os._exit`, a new start):
  `trials=40 pause=0.0s: old pid alive at next start 0`. After a **reboot**
  (the S5-17 case: "a reboot, the unattended runner's job object"), any
  pid is fair game: this PC had `count=436` processes over pids up to
  `maxId=45940` (≈11,500 slots, pids are multiples of 4), so ≈4% of the
  time; more for the low pids a boot hands out (the live log shows the app
  at 6616, 5892, 5384 after the 2026-10-31 restarts). The file then stays
  until a start finds that pid free — under serve_forever, the next crash
  or reboot, which can be weeks.
- **Mutant check:** none needed — this is the shipped code's behaviour, not
  a test gap. The G-3 test itself depends on the same assumption: its
  "dead" pid is a child that just exited, and it asserts that folder goes;
  it would flake if Windows reused that pid at once (0 of 40 here).
- **Suggested fix, as a rule:** a folder is kept only while *the process
  that made it* is provably alive — its identity, not its number: name it
  `<pid>-<creation time>` and compare with `GetProcessTimes`, or have the
  process hold a lock file in it that `clear()` tries to delete first (a
  held file refuses; rmtree only after that succeeds). Either also answers
  "access denied" without guessing.

### H-2 — low — CONFIRMED: the CSS arrows are read aloud — "Check →", every chip "… →", every source link "… ↗" (7d84246, the page; live)

- **Where:** `static/index.html`, `.send::after { content: "→"; }`,
  `.chip::after { content: " →"; }`, `a.src::after { content: "↗"; … }`.
- **Rule it breaks:** decoration must not change what a control is called.
  CSS generated content is part of an element's accessible name (the
  accname spec, and Chrome does it), so a screen reader announces the
  arrows — "Check right arrow", "… north east arrow" — and voice control
  must match the arrow too. The commit chose CSS for the Check arrow so
  `setBusy()` cannot drop it; the accessible name was not considered.
- **Evidence** (probe `axnames.py`: headless Chrome 156 over CDP,
  `Accessibility.getFullAXTree` on the extract's page served by a demo
  server on port 8020, non-ignored buttons and links). It printed, for the
  empty page: `button  'Check →'`,
  `button  'Drinking hot water kills the coronavirus →'`,
  `button  'NASA confirmed 6 days of total darkness →'`, and the
  Hindi chip ending `… है →'`; for an answered page:
  `link    'BOOM No, 5G Does Not Spread Coronavirus ↗'` (and the same
  for WHO and Alt News). The live page is the same file (a GET of
  https://informationverifier.com/ differs from HEAD only by Cloudflare's
  injected challenge script), so this is live.
- **Mutant check:** no test covers accessible names; the 273 page tests
  pass either way. A test could pin that no `::before`/`::after` with
  visible text lacks an alt (`/ ""`).
- **Suggested fix, as a rule:** generated text that is decoration carries
  an empty alternative: `content: "→" / "";` (Chrome 77+, Safari 17.4+,
  Firefox 128+; an older browser drops the declaration and simply shows no
  arrow). The same for the chips and `a.src::after`.

### H-3 — low — CONFIRMED: `forget.py --yes` with a mistyped id ends by saying the deleted text is gone (aaf5398, G-5)

- **Where:** `scripts/forget.py` `main()`, the no-match branch's new
  `_finish_the_file()` call, and its message.
- **Rule it breaks:** re-check F-7's — a deletion tool never reports as
  done what is not. G-5 made the no-match `--yes` run finish the WAL, which
  is right for "run the same command again", but the same branch is also
  where a **mistyped or wrong id** lands, and there it now ends on a line
  that reads as success. The owner answering a deletion request (the
  privacy notice's promise) skims to the last line.
- **Evidence** (probe `g5_forget.py`: a fresh synthetic database in
  scratch, `forget.main([...])` with an id that was never stored, then a
  `--text` that matches nothing). It printed, both times:
  `No check matches. A reel is found by its link; … After 30 days a check is deleted anyway.`
  `The database file is clean now: no earlier copy of the deleted text is left in it.`
  `---- exit code 1`. Nothing was ever deleted; the script cannot know
  whether an earlier run deleted anything, yet speaks of "the deleted
  text".
- **Mutant check:** the G-5 test follows the advice only (delete → reader
  closes → run again) and asserts `"clean"` — it would pass unchanged
  with any wording; nothing pins what a wrong id prints.
- **Suggested fix, as a rule:** a run that deleted nothing says so in its
  last words. E.g. print first "Nothing was deleted by this run", and only
  then, neutrally, "the database's log is empty: whatever an earlier run
  deleted is gone from the file" — or finish the WAL silently and keep
  the exit code 1 as the signal. Test: `--yes` with an unknown id prints
  no sentence that says something was deleted or is "clean of" it.

### H-4 — low — CONFIRMED: find_db_copies calls a full copy of the database "the app's own backup" when it sits in the backups folder (f9fd678, G-1)

- **Where:** `scripts/find_db_copies.py` `main()`: `elif backups in resolved.parents: what = "the app's own backup"`,
  tested before the orphaned-WAL, same-size and project-schema labels.
- **Rule it breaks:** F-1's and G-1's — a copy is known by what it IS
  ("by header and table names, never by name or folder"). The backup
  label is given by folder alone. The app's backups hold only
  `spend_ledger`, `daily_checks`, `daily_budget` (backup.py `_TABLES`); a
  file there with `answers` is people's messages, and BACKUP_DIR is meant
  to be a OneDrive folder, i.e. off this machine.
- **Evidence** (probe `g1_backups.py`: a synthetic database made by
  `init_db()` in scratch, copied whole to `data\backups\verifier.db.before-upgrade`
  — F-1's own name for a real copy — then `find_db_copies.main([scratch])`).
  It printed: `tables in the copy: ['answer_cache', 'answers', 'daily_budget', 'daily_checks', 'meta', 'ready_probe', 'spend_ledger', 'transcript_cache']`
  and `69632 … \data\backups\verifier.db.before-upgrade  [the app's own backup]`
  — the same size as the real one (`69632 … \data\verifier.db  [the real database]`),
  which would otherwise have read "SAME SIZE AS THE REAL DATABASE — almost
  certainly a copy: delete it".
- **Mutant check:** the G-1 tests plant copies elsewhere; none plants a
  message-holding file in the backups folder, so the folder-first order is
  unpinned.
- **Suggested fix, as a rule:** "the app's own backup" only for a file in
  the backups folder whose tables are a subset of backup.py's `_TABLES`;
  anything else there falls through to the content labels like any other
  file.

### H-5 — low — CONFIRMED: in the light theme the AI disclaimer and the new "Try one" label are 2.99:1 (7d84246 kept it and added one; the colour predates it; live)

- **Where:** `static/index.html`: `--ink-3: #8b93a1` on `--bg: #fbfbfa`,
  used for `.hint` (the line 5455a6e rewrote: "I'm an AI, and I can be
  wrong … For ages 18+ … terms … privacy notice", .74rem), the new
  `.empty .try` ("TRY ONE", .78rem), and older small text (`header .tag`,
  `.basis`, which carries "· AI-written" on every answer).
- **Rule it breaks:** the redesign's own — its commit fixed the Check
  button because "white on that light blue was 2.3:1, under any contrast
  rule" — applied to the button only. WCAG AA asks 4.5:1 for text this
  size. The line it leaves faint is the one the project treats as a legal
  must (Anthropic's AI disclosure and the 18+ notice, "on screen whenever a
  check can be sent").
- **Evidence** (the WCAG relative-luminance formula over the page's own
  tokens): light `#8b93a1` on `#fbfbfa` = `2.9887`; on the composer's
  white `3.0946`; dark `#737b8a` on `#0d0f13` = `4.5021` (passes by a
  hair). For comparison the redesign's new pairs pass: white on
  `#0e7490` 5.36, `#0b1220` on `#7aa2ff` 7.52, the eyebrow 5.99 / 6.42.
  The token was introduced in 2602338, so the faint hint predates this
  session; 7d84246 is where contrast was last weighed and the new label
  joined it.
- **Mutant check:** no test checks contrast.
- **Suggested fix, as a rule:** text that must be read — the disclosure
  above all — uses a token that meets 4.5:1 in both themes (`--ink-2`,
  5.92:1 light, already defined); keep `--ink-3` for decoration (the
  arrows) and placeholders.

## Checked and sound

- **The suite on the extract:** `1335 passed, 1 warning in 150.46s`,
  `FULL_PYTEST_EXIT=0` (pytest's own exit code, not through a pipe).
- **Each commit's test fails against its broken version** (probe
  `mutants.py`, one mutant at a time in a second extract, pytest's own
  exit code): G-8 without the unsaved rewrite `exit 1 (CAUGHT)`; G-8 with
  a bare `os.replace` `exit 1`; G-4 without the consumption `exit 1`; G-6
  with the app never containing itself `exit 1` (14 s); G-2 without the
  alert `exit 1`; G-5 without the finish `exit 1`; 7d78981 with
  `env_file=".env"` always `exit 1`; 5455a6e with "(Claude)" back in the
  bot's tag `exit 1`; G-3 with every pid alive `1 failed, 5 passed` and
  with every pid dead `1 failed, 5 passed`.
- **G-6 under the production nesting** (probe `g6_nested.py`): a
  supervisor that contained itself starts, through the venv launcher with
  `VERIFIER_SUPERVISED=1`, an app that runs its real lifespan, starts a
  REAL ffmpeg (`-re`, 120 s) and dies by `os._exit` while the supervisor
  lives on: `ffmpeg … alive 1 s after the app died (supervisor still alive): False`,
  3 of 3, and no "could not put" line. `second contain_self() in one process: True`.
  The live logs (read only) carry no "could not put the app in its own
  job" line since 2026-10-28, so it took live too. The app starts only
  ffmpeg as a subprocess (`app/providers/media.py`; yt-dlp runs
  in-process), and nothing asks for breakaway.
- **serve_forever imported from C:\Windows\System32** (as Task Scheduler
  can) loads no settings early: `app.config loaded at import: False False`.
- **G-8 and the bot's concurrency:** `bot_explorer.py` and
  `bot_explorer_restarts.py` (2,000 seeds each, run from the extract with
  TEMP pointed into scratch): `violations by invariant: none`, `EXIT=0`,
  and 0 "could not save" lines. The 0.4 s worst-case retry blocks the
  bot's loop only on a refused swap (the commit measured median 2 ms).
- **G-3 after a crash-restart:** `trials=40 pause=0.0s: old pid alive at next start 0`
  (probe `pid_reuse.py`) — the routine serve_forever case is fine; H-1 is
  the reboot case.
- **7d78981 if VERIFIER_ENV_FILE ever reached the app** (probe
  `envleak.py`, app with no .env read): money fails closed — `/ready: 503 … "keys":false`
  and a paid check addressed to the public name `403 {"detail":"Checks can only be sent from the Information Verifier page itself."}`.
  (What it does NOT do is under Notes.)
- **5455a6e:** no disclaimer names the model (the page's hint, the
  footer's "· AI-written", the bot's /start and answer tag, the terms).
  The privacy notice and the bot's /privacy still name Claude as the
  recipient, as decided.
- **The page** (extract served by a demo-mode server on port 8020,
  headless Chrome 156, throwaway profiles in scratch):
  - 390 px (CDP device metrics), empty and answered:
    `clientWidth=390 scrollWidth=390 unclipped-overflow=[]` both times;
    screenshots light and dark, desktop and phone, look as the commit
    describes.
  - Without `:has()` (its 3 rules deleted from the loaded page's
    stylesheet over CDP, as an old browser drops them):
    `stripe: rgb(38, 43, 53) display block` — a grey edge, nothing broken.
  - The stripe cannot be set by the model: sources render outside
    `.answer` with `.name.trusted`, not `.pill`, and the prose renders as
    text (invariant 3).
  - The named sources are on the list: `altnews.in`, `boomlive.in`,
    `pib.gov.in` (crawler-verified core) and `who.int`.
  - "no sign-up" is true (Turnstile and a cookie, no account); the new
    colour pairs pass AA (white on `#0e7490` 5.36, `#0b1220` on `#7aa2ff`
    7.52, eyebrow 5.99 / 6.42, the headline's gradient ends 5.17 / 7.71).
  - The composer's new `:focus-within` border is the textarea's first
    focus cue (it has `outline: 0`): an improvement.

## Notes, not findings

- **The top edge is the tier's colour, not the verdict's.** A debunked
  claim covered by fact-checkers gets a green edge over "This is false."
  (the demo answer, dark and light screenshots). The CSS comment says so
  honestly; the commit title calls it "the verdict's colour". The pill was
  already green, so this is consistent — but in a fact-checking tool green
  reads as "true" at a glance. A design call for Vinayak, not a defect.
- **"any language"** (the new eyebrow, and the older lead): text, yes;
  voice notes go to Sarvam Saaras (`language_code: "unknown"`), which is
  built for Indic languages and English. The copy predates this session.
- **VERIFIER_ENV_FILE leaking into production would be silent.** Money is
  safe (above), but nothing says no .env was read: OWNER_CHAT_ID is empty,
  so no alert fires (the supervisor's own alerts included); the bot finds
  no token, returns, and is restarted forever; `/privacy` publicly reads
  "write to the contact address, which is published here before the
  service opens to the public"; the database is `./data/verifier.db`
  relative to the folder — under serve_forever, the real one. Only a
  deliberate setting could cause it (conftest sets it in pytest's own
  process). A cheap guard: the app, bot and serve_forever print which env
  file they read, and a supervised process refuses VERIFIER_ENV_FILE.
- **7d78981's "the suite reads nothing from the owner's .env"** is true
  except by design: `test_isolation._paths()` builds
  `Settings(_env_file=".env")` from the working folder, loading every key
  into a (repr-hidden) object for one path comparison. In the prescribed
  worktree run there is no .env, so it compares with the worktree's own
  default — harmless, the session fixture is the real wall.
- **G-8, the last failed save before a stop:** the bot dies on CTRL_BREAK
  with no handler, so an unsaved state is not written at shutdown. It
  needs five refusals inside 0.4 s (0 of 860 measured) and then a stop
  before the next poll — negligible. The restarts explorer injects no
  save failures, so its clean run does not exercise G-8's path.
- **G-4, main()'s own removal is unguarded:** `STOP_FILE.unlink(missing_ok=True)`
  raises if the file still cannot be deleted at the next start, before
  anything starts or logs (the supervisor log says "the next start removes
  it"). The task's `-RestartCount 999` every minute retries. It needs a
  file held across a whole stop and start (or a read-only attribute):
  contrived.
- **The orderly stop has never run on the live system:** no
  `supervisor-*.log` has "stopping"/"stopped" (only 2026-10-28 and
  2026-10-31 exist, starts only). HANDOFF's to-do 3 ("restart via the
  stop file") will be its first real run; read the log for "stopped"
  before Start-ScheduledTask, as go-live.md says.
- **The API description is public:** https://informationverifier.com/docs
  answers 200 and `/openapi.json` says "one Claude-style answer with its
  sources". Not a disclaimer, so outside 5455a6e's decision; mention only
  in case the model name was meant to go everywhere.
- **The live page = HEAD's `static/index.html` plus Cloudflare's injected
  `/cdn-cgi/challenge-platform/…` script** (the only diff). The privacy
  notice already names Cloudflare.
- **G-2's alert limit is per process:** `alerts._sent` lives in memory, so
  an app in a crash loop (restarted every 5–300 s) with a failing
  housekeeping step would alert once per start, not once an hour. Needs
  two faults at once; noted, not reproduced.
