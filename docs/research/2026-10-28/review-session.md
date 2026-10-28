# Review — the 2026-10-18 to 2026-10-28 session's code commits

status: STOPPED at the owner's request (2026-10-28, out of tokens) - an outline only, no findings. Do not resume unasked.

HEAD reviewed: a1728354089e3874f6702c838e2e29d6cd3a7073 (a172835)

## Scope

The code commits of the 2026-10-18 to 2026-10-28 session:

- 82b0708 G-8: app/files.py replace() retry; PendingStore unsaved flag; backup.py
- 6eb2e57 G-2: housekeeping failures alert the owner
- 4838389 G-4: serve_forever consumes the stop file after the stop
- aaf5398 G-5: forget.py --yes with no match finishes the WAL
- f9fd678 G-1: find_db_copies lists every project-schema DB except pytest's folders; orphaned -wal
- 486a795 G-3: scratch working files per process id; clear() keeps live processes' folders
- 7f35db8 G-7: tests that run both main()s
- ea2e82c G-6: app/processes.py; the app contains itself when VERIFIER_SUPERVISED=1
- 5455a6e: disclaimers say "written by AI", no model name
- 7d78981: VERIFIER_ENV_FILE — the test suite reads no .env
- 7d84246: the page redesign (static/index.html)

## Method

- Work only in an extract (`git archive HEAD | tar -x`) in the session scratch
  folder; no `.env`, no `data\`. The live site, its scheduled task, the
  cloudflared service and the real `data\`/`logs\` are not touched.
- For each commit: does it cover the rule or only the named case; did it add a
  defect; would its test fail against the broken version (a mutant in the
  extract).
- Spend nothing: no paid scripts, no API calls; GETs to the public site only.

## Findings

(appended as each is reproduced)

## Checked and sound

## Notes, not findings
