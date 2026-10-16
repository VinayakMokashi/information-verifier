# Review of step 5 of the launch (privacy, terms, bot, deletion, app)

status: in progress

Adversarial review of `git diff 4b56628..69e7d6d` (2026-10-16): the privacy
notice and terms, the limiter's forgetting, the bot's /privacy, /delete and
command handling, scripts/forget.py, and the installable app. Findings are
appended below the moment each one is reproduced; a file whose status line
still says "in progress" means the review was interrupted — re-run it,
seeded from what is here.

## Findings

Reproductions run against a `git archive 69e7d6d` snapshot, from the review's
scratch folder (no `.env`; every key `invalid-audit-key`; DB_PATH inside the
scratch folder). The suite there: 1229 pass, 1 fails only because it reads
`app/api/routes.py` relative to the working directory (an artifact of running
from outside the repo, not a defect).

### S5-1. The bot keeps a chat id and its job id on disk for as long as it runs, not "at most a day"

- Severity: medium
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:725-745` (PendingStore: `_TTL_S` is applied
  only in `__init__`, on load), `:931-936` (a wait that gives up leaves the
  entry), `:1034-1037` (same after a restart); the promise is
  `app/api/privacy.html:230-233` ("notes your chat number until your answer
  is delivered (at most a day)").
- Evidence: `repro_bot_memory.py` (scratch) — a check whose 4.5-minute poll
  window runs out (`_STILL_RUNNING`; a two-pass reel check was measured at
  ~295 s before its download and ASR) and whose person never pokes:

      2. a check whose wait gave up ('still running'), nobody pokes:
         pending   : {777: 'job1'}  prompted: {777}
         on disk   : {"777": {"job": "job1", "at": 1792170818.356232}}
      3. three days later, same process, after another chat's write:
         on disk   : {'777': {...}, '888': {...}}
         chat 777's entry is 72 hours old and still on disk

  Every later write rewrites the stale entry. It leaves only when that chat
  sends another message or the bot restarts. On the 24/7 server step 4 is
  building, that is weeks — past the answer's own 30 days — and a job id opens
  the person's message (the class docstring says so: OPS-11). `/delete`'s
  "after the answer is sent I don't remember which message was yours" is true
  only of delivered answers.
- Suggested fix: drop entries older than `_TTL_S` on every write and on a
  timer in the running bot (not only on load), and test it with the process
  kept alive across the day.

### S5-2. The bot keeps every chat id it has ever handled in memory for the life of the process — the rule 60beff7 fixed in the limiter, missed here

- Severity: low
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:844` (`locks.setdefault(chat_id, ...)`, never
  removed), `:968` (`self.locks`), `:969`/`:934` (`self.prompted`: a chat whose
  wait gave up stays until it writes again). The promise: privacy.html:229-233
  ("kept in the server's memory to count today's checks"), :281-283 ("cleared
  after the day they count"); 60beff7's own reasoning ("weeks of visitors'
  addresses in memory, for a record the limits stop using after an hour").
- Evidence: `repro_bot_memory.py` — one ordinary check, delivered:

      1. after the answer was DELIVERED:
         pending   : {}
         in_flight : {}
         locks     : [4242]

  `in_flight` and `pending` are cleaned; `locks` never is. 60beff7 fixed the
  mechanism its finding named (the limiter's `_per_client`), not the rule
  ("who asked is forgotten after the day it counts"), and the bot process is
  the one that sees every Telegram id first.
- Suggested fix: pop a chat's lock when its handler leaves it unlocked with no
  waiters and nothing pending (or sweep idle ones with the pending TTL); drop
  `prompted` entries with the pending entry they belong to.

### S5-3. forget_idle() can change a decision at midnight: a person who used up their day gets one more check charged to that day

- Severity: low
- Status: CONFIRMED
- Where: `app/api/limits.py:679-683` (clears `_person_today`, leaves
  `_person_day[0]` on the old day); `:529-530` / `:553-562` (`fund()` and
  `reserve()` compute `day = today()` BEFORE `_fund` takes `_lock`, with
  `_daily_full(day)` — a SQLite read that can wait out the 30 s busy timeout
  — in between); `:457-461` (the straggler sees its own day label, so it does
  not clear, and finds the count gone).
- Evidence: `repro_forget_idle_midnight.py` (scratch; real threads, the
  database read held open by an Event; midnight passes during the read and
  the housekeeping call lands there):

      without forget_idle: refused 429: You've used your 5 checks for today. ...
      with forget_idle   : GRANTED, charged to day 2026-10-16

  60beff7 and the docstring both say "no decision changes". The window is a
  claim's database read, and the call comes once in 6 hours, so it is rare;
  the day's budget still bounds the money. The same flip-flop already exists
  when the NEXT day's first claim clears the table under a straggler (it
  re-dates back) — forget_idle adds a second trigger rather than closing it.
- Suggested fix: key the per-person counts by (day, subject) and have
  forget_idle drop only days that ended more than the busy timeout ago (or
  record the cleared day and refuse a straggler for it), and say "within a
  few minutes of midnight" honestly if that is the rule.

### S5-4. The notice states "Our Sarvam account is set to keep none of it" — the repo's own HANDOFF says that is not yet true, and nothing guards it

- Severity: medium
- Status: CONFIRMED (by the same commit range's own documents)
- Where: `app/api/privacy.html:253-255`; HANDOFF.md at 69e7d6d, "Going live
  needs": "Sarvam's data retention set to 0 days ... the privacy notice says
  'Our Sarvam account is set to keep none of it', which is true only once
  that is done", and the owner-actions list still has "set Sarvam's data
  retention to 0 days". policy-legal.md F10: Sarvam keeps workspace data
  *indefinitely* until an Owner sets a period, the change is *not
  retroactive*, and its ToS allows training on inputs including audio
  (s.17.5) — a point the verification left unfetched and the notice does not
  mention at all.
- Evidence: the page is served now by `/privacy` (dfb16b7) with the sentence
  unconditional; voice notes go to Sarvam today through the live bot. The
  only owner-dependent facts the code does guard are CONTACT_EMAIL and
  Turnstile (`app/main.py:359-378`, startup warnings). A promise the code
  cannot check needs either the same kind of switch or wording that is true
  until the switch is thrown.
- Suggested fix: a setting (e.g. `SARVAM_ZERO_RETENTION=true`, set by the
  owner after the dashboard change) that picks the sentence, plus a
  going-live warning while it is unset; until then say "Sarvam keeps it
  under its own retention terms". Resolve the training clause before saying
  anything about it.
