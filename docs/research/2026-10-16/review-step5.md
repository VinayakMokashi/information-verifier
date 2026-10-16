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
  `app/api/privacy.html:86-89` ("notes your chat number until your answer
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
  wait gave up stays until it writes again). The promise: privacy.html:85-89
  ("kept in the server's memory to count today's checks"), :137-139 ("cleared
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
- Where: `app/api/privacy.html:109-111`; HANDOFF.md at 69e7d6d, "Going live
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

### S5-5. "Hi" (or a sticker, or a too-big file) sent together with a claim still leaves the claim unchecked — the /id fix covered the commands, not the rule

- Severity: medium
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:987` (`counted = ... not in _INSTANT`);
  `:697` `_NEVER_CHECKED = ("unsupported", "smalltalk", "too_big")` are
  never submitted either, but are still counted as work in flight;
  `:883-887` then tells the claim it arrived mid-check.
- Evidence: `repro_bot_never_checked.py` (scratch), Part 1, one batch of two
  messages from one chat — at 69e7d6d:

      '/id' (fixed by bb623ae)  kind=id          -> claim CHECKED
      'Hi' (small talk)         kind=smalltalk   -> claim NOT CHECKED; told: ℹ️ Yeh naya message check nahi hua, kyunki pichla check chal raha tha....
      a sticker (unsupported)   kind=unsupported -> claim NOT CHECKED; told: (same)
      a 21 MB voice note        kind=too_big     -> claim NOT CHECKED; told: (same)

  At 4b56628 (snapshot `snap-before`) all four were NOT CHECKED: bb623ae fixed
  the commands its finding named; its own rule — a message that is never
  submitted must not make the next one look mid-check — still fails for
  the other three never-submitted kinds. "Hi" then a forward is the most
  ordinary first exchange there is; both land in one batch whenever the
  bot was down or Telegram was slow (this machine measured getMe timing out
  twice), and the reply's reason ("the previous check was running") is false.
- Suggested fix: count only kinds that can submit (`text`, `link`, `media`,
  `image`); keep the never-submitted kinds going through the lock and the
  pending branch (so "ok" still collects a report) without counting them.
  Test the rule over every kind classify_message can return.

### S5-6. A bare unknown command is no longer a poke: after "send me any message", "/status" gets the help text and the answer stays undelivered

- Severity: low
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:179-183` (a bare unknown command becomes
  "help"), `:828-830` ("help" returns before the pending branch); the promise
  is `_STILL_RUNNING` (`:703-705`, "Mujhe koi bhi message bhejiye aur main
  wahi report dikha dunga").
- Evidence: `repro_bot_never_checked.py`, Part 2 (pending job, chat in
  `prompted`):

      69e7d6d : '/status' kind=help -> help text; pending after: {7: 'job1'}
      4b56628 : '/status' kind=text -> the ANSWER; pending after: {}

  "/status" or "/result" is what a person used to bots types when told to
  send anything. No money is lost (the next message still collects it), but
  the bot breaks its own sentence; /privacy and /delete now do the same.
- Suggested fix: let a bare unknown command (and /privacy, /delete) deliver a
  pending answer first — e.g. route "help"-by-default through the pending
  peek when the chat has one — or say "any message except a /command".

### S5-7. A reel-link check cannot be found from "the message and the day" — the link is not stored — and forget.py then tells the owner it is probably gone already

- Severity: medium
- Status: CONFIRMED
- Where: `app/engine/job.py:120-121` (run_check overwrites `input_text` with
  the gathered caption + transcript; `app/api/routes.py:764` had created
  the row with the URL); `app/store/repository.py:474-495` (`find` searches
  only `input_text`/`source_text`); `scripts/forget.py:59-61` (the
  no-match message); the instructions it serves: privacy.html:159-161 ("or
  with the message and the day you sent it"), the bot's `/delete` ("message
  aur din bata dijiye").
- Evidence: `repro_forget_paths.py` (scratch), a link check stored exactly as
  `/verify/link` → `_link_job` → `run_check` store it:

      stored input_text starts: 'Sarkar har ghar ko 5000 rupaye de rahi h'
      No check matches (deleted already, or older than 30 days and so gone anyway?).
      forget --text <the link> --day today -> 1 (1 = nothing matched)
      ...
      still in transcript_cache after --yes: [('v2:instagram:DAbCdEfGhIj', 'Sarkar har ghar ko 5000 rupaye de rahi h')]

  For a reel, the link IS the message a person sent; they never typed the
  words a machine heard. The tool's reply invites the owner to answer "it is
  already gone" while the check stays for 30 days. A `--job` deletion (the
  other path) leaves the post's words in `transcript_cache` for
  `transcript_cache_ttl_days` (30), which the tool's docstring does not
  mention (the notice does list that cache, as public-post content).
- Suggested fix: keep the submitted URL in its own field (e.g.
  `Answer.submitted_url`, or leave `input_text` as sent and put the gathered
  text in `source_text` only) and search it; make the no-match message say
  "a link, voice note or screenshot is found by the words read from it, or
  by its #job= address"; have `forget()` also drop the transcript row whose
  text matches, or say why it stays.

### S5-8. A repeat served from the cache saves its COMPLETE row twice; a deletion between the two saves is undone

- Severity: low
- Status: CONFIRMED (deterministic interleaving; the real window is the
  milliseconds between the two saves)
- Where: `app/engine/job.py:140-154` (the cache branch saves COMPLETE and
  `return`s) and `:195-200` (the `finally` saves the same COMPLETE answer
  again, INSERT OR REPLACE); `scripts/forget.py:68-77` trusts COMPLETE to
  mean "no more writes" ("a running check saves itself again when it ends").
- Evidence: `repro_forget_paths.py`, part 2 — `repo.forget()` called right
  after the repeat's first COMPLETE save, as forget.py in another process
  would:

      COMPLETE saves of the row: 2 | forget deleted (rows, cached copies): (1, 1)
      row after the job ended: PRESENT again (input_text='Garam paani peene se corona ma'...)

  The cached copy stays deleted; the person's message is back in `answers`
  for the full 30 days, and the owner was told it was deleted.
- Suggested fix: make the cache branch's save the only one (skip the
  `finally` save when it already succeeded), or have the final save be an
  UPDATE that cannot recreate a deleted row.

### S5-9. The bot is public already, but the missing-contact warning is keyed to the web's PUBLIC_HOSTS: live bot users are told a contact comes "before the service goes public"

- Severity: medium
- Status: CONFIRMED
- Where: `app/main.py:359-378` (`_going_live_warnings` returns nothing unless
  PUBLIC_HOSTS is set); `scripts/telegram_bot.py:133-148` (`delete_text`),
  `:1115-1157` (the bot's startup checks the token and /ready, never the
  contact); HANDOFF at 69e7d6d lists "the bot answers anyone, even with no
  public URL" among the pre-public facts, and start.cmd runs the bot today.
- Evidence: `repro_bot_contact.py` (scratch), PUBLIC_HOSTS and CONTACT_EMAIL
  both empty — the state the conftest pins and HANDOFF says .env is in until
  Vinayak decides:

      app startup warnings      : []
      bot /delete says          : Jaldi delete karwane ka email pata service public hone se pehle privacy notice mein diya jaayega.
      bot /privacy links notice : False
      bot main() mentions contact_email: False

  Anyone on Telegram can use the bot now, so "before the service goes
  public" is already untrue, the deletion promise has no channel, and
  nothing tells the owner. The warning added in dfb16b7 guards the surface
  the finding named (the web pages), not the rule (a public surface needs a
  contact).
- Suggested fix: the bot prints the same warning at startup when
  CONTACT_EMAIL is empty (it is public by construction); `/delete` without a
  contact should say how to reach the owner now (or the bot should refuse
  new users until one is set), not promise a future notice.

### S5-10. Three full copies of the real database sit in session scratch folders, outside every deletion the notice promises

- Severity: medium
- Status: CONFIRMED (by listing name, size and date only — not opened, per
  this review's rules)
- Where: `%TEMP%\claude\c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier\`
  - `09bde991-…\scratchpad\realcopy.db` — 1,273,856 bytes, 29 Sep
  - `4b88200f-…\scratchpad\forget-real-copy-1\copy.db` — 1,273,856 bytes
    (made 16 Oct 22:17 for 4806194's "measured on a file COPY of the real
    database")
  - `4b88200f-…\scratchpad\real-backup-80894b81\data\verifier.db` —
    1,273,856 bytes
  (the real `data\verifier.db` is 1,273,856 bytes too).
- Evidence: `find … -iname "*verifier*.db" -o -iname "*copy*.db" …` over the
  project's temp folders. Nothing prunes these: housekeeping deletes rows in
  DB_PATH only, forget.py opens DB_PATH only, and Windows never empties
  %TEMP% by itself. The 29 Sep copy already holds whatever the real table
  held then, so it passes the notice's 30 days on 29 Oct at the latest, and
  a deletion request honoured with forget.py leaves all three copies holding
  the message. The privacy notice is a promise about every copy, not only
  the live file.
- Suggested fix: delete the three copies now; make "a copy of the real
  database is people's messages: delete it when the measurement ends, and
  say so in the commit" a CLAUDE.md rule; prefer measuring against a
  synthetic database (the tests already build one) or a ledger-only backup.

### S5-11. "Deleted" leaves the message's bytes in the database file: SQLite's secure_delete is off

- Severity: low
- Status: CONFIRMED
- Where: `app/store/db.py:118-126` (`get_conn` sets WAL and busy_timeout,
  never `secure_delete`); `app/store/repository.py:439-454` (prune) and
  `:497-520` (forget) are plain DELETEs.
- Evidence: `repro_sqlite_remanence.py` (scratch) — save a check and its cached
  copy through the app's own connection, `forget()` it, checkpoint:

      secure_delete pragma: 0
      forget() -> (1, 1)
      row still readable through the app: False
      remanence.db         69632 bytes, the deleted message appears 2 time(s)

  The app can no longer read it, but the file still holds the message (row
  and cached copy) until SQLite happens to reuse those pages — on a
  low-traffic database, for a long time. Every file-level copy (S5-10; a
  cloud host's disk snapshot later) carries "deleted" messages with it.
- Suggested fix: `PRAGMA secure_delete = ON` in `get_conn` (or `FAST`, which
  zeroes deleted content in pages that are written anyway), and a test that
  greps the file after a prune and after `forget()`.

### S5-12. The "content-free" cost record and its daily backups hold every job id — each one opens that person's message for 30 days

- Severity: low
- Status: CONFIRMED
- Where: `app/store/repository.py:243-249` (`job_id` is the ledger's key);
  `app/store/backup.py:52-58` (`SELECT * FROM` each of `_TABLES`, the ledger first, into every daily
  copy, kept 14 days, in BACKUP_DIR — which HANDOFF asks Vinayak to point
  at OneDrive); `app/api/routes.py:801-806` (`/reports/{job_id}` is public);
  the notice's lines: privacy.html:134-136 ("never what was sent and never
  who sent it") and :126-128 ("anyone who has the address ... can open it").
- Evidence: `repro_ledger_keys.py` (scratch; TestClient, fake engine, a
  scratch DB and backup folder):

      job ids in the content-free ledger backup: ['8792c671417b4ad693c0c2245ce2e1e6']
        /reports/<that id> -> 'Mera beta Rohan Class 7B mein hai, uske school mein bomb ki afwah sach hai?'

  The dashboard already leaves job ids out for exactly this reason
  (`SpendLedger.recent`, "A job id opens /reports/{id}, the full message, to
  anyone holding it"); the backup that leaves the machine keeps them all.
  Whoever can read the synced folder can read every message of the last 30
  days through the public site — and that cloud drive is not among the
  notice's recipients.
- Suggested fix: drop `job_id` from the backup copy (a NULL-able or hashed
  column there; `restore_ledger` would then match on the hash), or key the
  ledger itself by a one-way hash of the job id (the backfill's LEFT JOIN
  would compare hashes in Python).

### S5-13. "/privacy?" is still a paid check: the unknown-command rule matches only an exact bare token, and the old prefix test still eats "/startup …" claims

- Severity: medium
- Status: CONFIRMED
- Where: `scripts/telegram_bot.py:169-183` (`_COMMAND.fullmatch(first)` and
  `first == text`: one trailing mark or word and it is no longer "bare");
  `:166-167` (`text.startswith(("/start", "/help"))`, kept above the new
  parser, is a PREFIX test).
- Evidence: `repro_bot_command_variants.py` (scratch, `handle_message` with a
  stub app):

      '/privacy'                                   kind=privacy -> privacy text
      '/privacy?'                                  kind=text    -> PAID CHECK submitted
      '/privacy.'                                  kind=text    -> PAID CHECK submitted
      '/delete?'                                   kind=text    -> PAID CHECK submitted
      '/stop.' / '/stop!' / '/settings?'           kind=text    -> PAID CHECK submitted
      '/cancel please'                             kind=text    -> PAID CHECK submitted
      '/startup India scheme har yuva ko Rs 10 lakh' kind=help  -> help text
      '/helpline 1930 ab band ho gayi hai'           kind=help  -> help text

  bb623ae's measured bug was "/privacy" bought as a paid check; its rule is
  "a bare unknown command is never a paid check". "/privacy?" — a person
  asking — still buys one (and spends one of their 5 a day). Telegram itself
  marks "/stop" in "/stop." as a bot_command entity. Meanwhile the old
  prefix test (pre-existing, left beside the new parser) turns real claims
  that begin "/startup…" or "/helpline…" into the help text, unchecked.
- Suggested fix: decide "command" from Telegram's own `entities` (a
  `bot_command` at offset 0) or strip trailing punctuation before the
  fullmatch; send /start and /help through the same parser (exact token, not
  prefix); treat a command followed only by punctuation/emoji as bare.

### S5-14. Two sentences of the notice say more than the code does: the daily counts ARE on disk, and the "In short" box's "deleted after 30 days" is not true at the recipients

- Severity: low
- Status: CONFIRMED (code trace)
- Where: `app/api/privacy.html:137-139` ("The counts behind the daily limits:
  only in the server's memory, cleared after the day they count (and
  whenever the server restarts)") against `app/store/db.py:43-61`
  (`daily_checks`, `daily_budget`: "Persisted, not in memory", never pruned)
  and `app/store/backup.py:30` (both copied into every daily backup);
  `privacy.html:62-63` ("What you send goes to the services listed below
  ... and it is deleted after 30 days") against :103-107 (Anthropic may keep
  flagged content up to 2 years), S5-4 (Sarvam: indefinite until set), and
  Telegram keeping the chat.
- Evidence: the schema comments say of both tables "Persisted ... survives
  restarts" — the opposite of the sentence. They hold no personal data, so
  the harm is only that the notice's literal claim is false; the per-person
  counts are what the sentence means. The summary box is what most readers
  read, and it promises deletion everywhere.
- Suggested fix: "The per-person counts behind the daily limits"; and "...
  and we delete our copy after 30 days (the services keep theirs as
  described below)".
