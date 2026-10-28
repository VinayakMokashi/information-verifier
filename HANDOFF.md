# Information Verifier — the whole project in one file

> **Read this first in a new session.** It is written so nothing is lost when
> a conversation ends: what the thing is, how it got here, what it costs, what
> is decided, what is open, and how to run it. Depth lives in
> [PROJECT_PLAN.md](PROJECT_PLAN.md) (§7 is the decisions log, §11 the to-do
> list) and [CLAUDE.md](CLAUDE.md) (the invariants and how we work).
>
> Last updated: **2026-10-18** (in session). Repo: `c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier`,
> pushed to https://github.com/VinayakMokashi/Information_Verifier (private).

---

## 0. Resume point — where the work is RIGHT NOW (updated at every step)

> If a session ended mid-task (usage limit, network drop), start here.
> Verify first (CLAUDE.md, "Interruptions"), then continue from **Next**.
> A research file whose top says **"status: in progress"** means its agent
> died: re-run that one task, seeded from the file.

**⚠ RAISED CAPS, TEMPORARY (Vinayak, 2026-10-27), for 7 days, to about
2026-11-03:**
- `DAILY_BUDGET_USD=5`, `MAX_CHECKS_PER_DAY=200`, and
  `PERSON_DAILY_LIMITS={"tg": 10, "tgchat": 10, "wa": 5, "dev": 10, "ip6": 5, "ip": 20}`,
  in `.env`, added by him.
- **He reverts by telling Claude** (his choice, not automatic): remove
  those three lines and restart, back to $1, 40, and 5/3.
- Any session after 2026-11-03 asks him first thing.
- At $5 a day, October's worst case in the capped Anthropic workspace is
  about $26. His monthly limit (about $35) must stay above that.

**The 2026-10-18 session — IN FLIGHT (kept current as it moves):**
- **Resume verified, free:**
  - git clean, `main` = `origin/main` at 97244ee;
  - 1316 passed, pytest exit 0 (6 min 18 s: another project's indexing
    job shared the CPU);
  - nothing of this project running;
  - `data\verifier.db` 1,273,856 bytes, 2026-10-12 05:21:10, the same
    after the suite;
  - both 2026-10-16 review files say complete.
- **Vinayak chose two of §0's three offers:** the fresh reviewer and one
  real local check. Not the fresh-venv suite.
- **The fresh review of the third-round fixes (1ae3cc3..09dc74d) is
  COMPLETE:**
  [docs/research/2026-10-18/review-fixes-round3.md](docs/research/2026-10-18/review-fixes-round3.md).
  - **First start: safe.** Measured on a synthetic database built by the
    2026-10-11 code, in the real file's state. Two of its claims were
    re-checked here: uvicorn 0.51 runs the lifespan before it binds, and
    the bot never opens the database.
    Expect after the start: the rewrite line once; answers from before
    2026-09-18 pruned (the 30 days); the ledger still **$1.7437**.
  - **go-live.md §5: correct**, except that the fallback account is not
    granted BACKUP_DIR (G-2).
  - **8 findings, all low** (G-1 … G-8). None of them blocks the first
    start. **ALL 8 FIXED**, each failing-first, with mutants, and pushed
    alone. The commits: G-8 82b0708, G-2 6eb2e57, G-4 4838389, G-5
    aaf5398, G-1 f9fd678, G-3 486a795, G-7 7f35db8, G-6 ea2e82c (the
    table at the end of the review file). **1333 tests** (1334 after 5455a6e, 2026-10-24).
  - **What it means for go-live:** go-live.md's fallback block now
    grants BACKUP_DIR, and its check proves a backup landed. A failing
    housekeeping step (the backup, the 30-day prune) now alerts your
    phone.
- **find_db_copies on %TEMP%** (the real file only stat'ed, never
  opened): it found **284** synthetic and demo databases from earlier
  sessions' reviews, probes and tests:
  - 163 in scratch `4b88200f…` (2026-10-15/17);
  - 93 in `%TEMP%\tmp*`-style folders (July to 2026-10-15);
  - 24 in scratch `2be1a3d1…` (2026-09-22);
  - 2 in scratch `09bde991…`, and 1 at the top of %TEMP%.

  None is the real file's size. The largest is 274 KB, against the
  real file's 1.27 MB.
  - Vinayak said to do what is best: delete them.
  - A dry run re-checked all 283 listed paths, 19.6 MB with their
    sidecars. Each is a SQLite file with this project's tables, inside
    %TEMP%, outside pytest's folders and the project. Six had their
    schema only in a live -wal.
  - The deletion itself was **blocked by Claude Code's permission
    check** (a sweep of other sessions' scratch folders). Not worked
    around. It waits on Vinayak: run it himself, or allow it.
  - The script is the session scratch's `delete_leftovers.py`. If that
    is gone, re-run find_db_copies on %TEMP% and delete what it lists,
    with each file's -wal, -shm and -journal.
- **The real check: after go-live §1 item 2** (the new Anthropic
  workspace key), so it proves that key too. Vinayak sends this to the
  bot from his phone, exactly: "UNESCO declared Jana Gana Mana the best
  national anthem in the world".
  - The free probe on 2026-10-18 found 5 trusted reviews in Google's
    fact-check database, all False (Fact Crescendo, Vishvas News,
    Snopes, Factly, India Today). Expect the ~$0.0084 shortcut.
  - NASA "6 days of darkness" was 2026-10-11's claim, so it is not
    reused.
  - **DONE 2026-10-24 09:09 IST, with his yes.**
    - $0.0089, text, COMPLETE, tier trusted, 0 web searches: the
      shortcut.
    - The dashboard's all-time total went from $1.7437 to **$1.7526**.
      The budget committed $0.0089 after reserving $0.20; the cap
      shows 1 of 40.
    - Next: disable the OLD Anthropic key, unless another project of
      his uses it.
- **Next:** docs/go-live.md with Vinayak, one step at a time. He has
  been given §1 item 1 (Sarvam's retention, then
  `SARVAM_ZERO_RETENTION=true`). The suggested order is 1 → 2 → 4 → 5
  → 6, then 3 (`/id`), because 3 needs the bot and so the first app
  start. Then the `/ready` check, then the real check. Nothing he has
  done has been reported yet.

**State at the end of the 2026-10-17 session: nothing in flight.** No
agents running, no half-done edits, no research file "in progress". `main`
is clean and pushed; the session's last commits are its handoff docs, all
after a6c3fe6 (`git log -5`). **1316 tests pass** (pytest exit 0). The app and the bot are NOT running and have not
run since 2026-10-12: `data\verifier.db` is 1,273,856 bytes, last written
2026-10-12 05:21, its `-wal` empty, so the ledger's total is still
**$1.7437**. `scripts\find_db_copies.py` finds no copy of the real
database anywhere.

**The task (Vinayak's startup prompt, §1):** (A) the public website/app,
(B) the WhatsApp bot, (C) the rest of PROJECT_PLAN §11, in value order.

- **A: the code is DONE.** Of the decision brief's §6 build order, steps
  1 (the pre-public blockers), 2 (the dollar budget, per-person limits,
  Turnstile), 3 (restarts, the ledger, monitoring) and 5 (privacy notice,
  terms, the AI line, a deletion tool, an installable app) are built and
  pushed. Each was adversarially reviewed, and so were the fixes: 31
  step-5 findings, all fixed (the record below). **Step 4, running 24/7
  on this PC at its own .com, is ready and waits on Vinayak.**
  [docs/go-live.md](docs/go-live.md) is his runbook, every step with its
  check.
- **B: WhatsApp is not started.** The slow applications are his and can
  start now (owner item 12 below). The build needs A's public address.
- **C: the rest of §11**, in the value order of §6 below.

**Next, for Claude:**
1. **Step 4, with Vinayak, when he is ready.** He does the owner's steps
   in docs/go-live.md; Claude answers, checks, and fixes whatever the
   first real run shows. At the first app start, expect two things:
   - a one-time VACUUM of the real database, logged and lossless (it is
     what makes earlier deletions final);
   - a startup warning for each going-live setting not yet in `.env`.
   One thing no document settled: whether Cloudflare streams the answer
   or buffers it (go-live.md §4).
2. **Offer these; don't do them unasked:**
   - **One real check before the public one** (~$0.01–0.17, only with his
     yes). Nothing has spent real money since 2026-10-11. So the dollar
     budget's reserve-and-settle, the per-person counts, the ledger's new
     reference and the owner alerts have met only fakes. Note that
     go-live.md §4's phone check is itself a paid check.
   - **A fresh reviewer for the third round of fixes** (1ae3cc3 … 09dc74d,
     free). They were proven by failing-first tests, mutants and 6,000
     explorer seeds, but no reviewer has read them. Twice now, a review of
     fixes found new defects in the fixes themselves.
   - **The suite in a fresh venv built from requirements.lock, on today's
     HEAD** (free). It last ran at a66cf5e: 1131 passed, exit 0. The lock
     has not changed since.
3. **B, WhatsApp.** The owner's applications come first (item 12 below).
   Then the build:
   - a webhook route and a WhatsApp formatter;
   - media through the Graph API into the existing image and voice paths;
   - the Telegram bot's per-chat logic;
   - the provider in `fake_stages.py`, with its credential neutralised
     (invariant 9);
   - a human escalation path, which Meta's Business Policy requires.
4. **C:** §11 in the order of §6 below. Each item gets a failing test
   first and its own commit, pushed, and then this section is updated.

**Owner actions waiting on Vinayak**, in [docs/go-live.md](docs/go-live.md)'s
order; each one's check is there. All are free except the domain (~$10.46
the first year).
1. **Sarvam:** set data retention to 0 days (Settings → Workspace → Data
   retention). THEN put `SARVAM_ZERO_RETENTION=true` in `.env`. Only then
   does the privacy notice say Sarvam keeps none of it (review S5-4).
   Until then it says Sarvam may keep it, and startup warns.
   **2026-10-23: BLOCKED on Sarvam.**
   - His workspace page is "Data policy" and lists only Voice Agents
     (24 months). It has no Model APIs row, unlike Sarvam's docs and
     their 2026-09-15 changelog.
   - So `SARVAM_ZERO_RETENTION` stays unset, and the notice stays true.
   - He asks Sarvam support. The rest of go-live goes on.
   - Organisation → Policy holds only encryption-key settings.
   - **He emailed Sarvam support on 2026-10-23.** Waiting on their
     answer.
2. **Anthropic:** a separate workspace with a monthly spend limit; its key
   goes in `.env` as `ANTHROPIC_API_KEY`.
   **DONE 2026-10-23.** Verified free: a models list with the new key
   returned HTTP 200 in workspace `wrkspc_01VYAydX915BB2PdCgkXE7Zh`, and
   claude-sonnet-5 is visible.
   - Keep the old key until the first real check passes on the new one,
     then disable it.
     **2026-10-27, Vinayak: the old key STAYS.** His other projects use
     it. Only the new workspace key is in this app's `.env`.
   - **go-live §2 DONE 2026-10-27:**
     - the domain is **informationverifier.com**, at Cloudflare;
     - Bot Fight Mode is OFF (his screenshot);
     - both Turnstile keys are set. The secret was proven genuine for
       free: siteverify with a dummy token said only
       "invalid-input-response".
   - Restarted 01:29 IST the same day: `/ready` is ready, and the page
     says "I'm an AI, and I can be wrong".
   - **The spend then read $2.1071.** After his $0.0089 check, two more
     checks ran on 2026-10-24: a reel at 05:30 UTC ($0.1764, 178 s of
     ASR) and a screenshot at 06:40 UTC ($0.1781, tier none). The day
     came to $0.3634, inside the $1 budget. Who sent them is not
     recorded, by design. **They were a friend's**, whom he had sent the
     bot to.
   - **go-live §3 DONE 2026-10-27:**
     - the tunnel is **verifier**, `b9002f90-83a1-4751-b2fd-8d81816acfa8`;
       its cert.pem and credentials .json are in `%USERPROFILE%\.cloudflared\`
       (names checked, contents never read);
     - DNS is routed: the site answered HTTP 530 / error 1033, a tunnel
       with no connector, as expected before it runs;
     - `config.yml` was written by Claude from go-live.md's template;
       `ingress validate` says OK;
     - by `ingress rule`, /dashboard and /api/v1/admin/spend → #0
       (404), / and /privacy → #1 (the app), www → #2 (404, not set
       up).
   - cloudflared warns that 2026.7.3 is outdated (2026.10.4 is out).
     Updating is his yes or no, before §5's service install.
   - **go-live §4: THE SITE IS LIVE (2026-10-27, connector up 21:04
     UTC, 02:34 IST).**
     - `PUBLIC_HOSTS=informationverifier.com`. The going-live check
       gives exactly one warning, Sarvam's, which is expected.
     - The tunnel runs in his third PowerShell window; one connector,
       4 edges in Mumbai.
     - From outside: / , /privacy, /terms, /manifest and /ready are 200;
       /dashboard and /api/v1/admin/spend are 404 at the edge.
     - It is up only while that window is open, until §5.
     - Still to do: his phone test on mobile data (streaming or
       buffered? install?), the BotFather privacy URL, then §5.
     - He also asked for a more appealing page UI. It is built in a
       worktree with the demo engine and shown to him before it
       replaces the live static/index.html.
       **Built: branch `ui-refresh`, 48e7c10, pushed; NOT on main, so
       not live.** It has a hero, three "how it works" steps, the
       verdict's colour on the answer card, SVG icons, and a gradient
       Check button with dark words in the dark theme. Looked at in
       both themes, desktop and 390 px phone; the 273 page tests pass.
       The pictures were sent to him; deploying waits on his OK (merge
       to main and push: the running app serves static/ from disk).
       **LIVE 2026-10-27, with his yes:** cherry-picked to main as
       7d84246. 1335 tests pass on that commit, and the live site shows
       the new headline.
     - **His phone test, on mobile data: the answer STREAMS word by
       word through Cloudflare.** That was the one thing no document
       had settled.
     - The BotFather privacy-policy URL is set (his word: "Done").
     - cloudflared update: **yes**. It is a winget install (2026.7.3,
       with 2026.10.4 available), done before §5.
     - He typed his Windows password into the chat. It is not written
       anywhere and never used by Claude; he types it into
       Register-ScheduledTask's own prompt in §5. Advised: it must be
       the account password, not a PIN, and he could change it
       afterwards.
   - **go-live §5a and §5b DONE 2026-10-28:**
     - cloudflared is updated to 2026.10.4 (winget).
     - The **Cloudflared service runs the tunnel**, with the ImagePath
       fix.
     - The first start died nine times, because the copied config's
       credentials-file line carried its label twice. That was seen by
       running the service's command by hand; go-live.md now has a
       validate step.
     - After the fix: the service is Running, the site 200,
       /dashboard 404, and exactly one connector, the service's. His
       manual tunnel window is closed.
     - **Next: §5c**, the Task Scheduler task for serve_forever. He
       closes the start.cmd windows first, and types his account
       password into the prompt himself. Then §5d, the reboot test,
       after the update pause ends (2026-10-30).
   - **go-live §5c DONE 2026-10-28:** the task **"Information
     Verifier"**.
     - It runs as VINAYAK45\Vinayak Mokashi, logon Password, run level
       Limited, with a boot trigger, no time limit, and restarts every
       minute.
     - Started 09:23 IST: the supervisor log shows the app and the bot
       started; /ready is ready (database, keys, ffmpeg); the site is
       200 from outside.
     - The bot is polling; today's ledger backup is in OneDrive; there
       is no housekeeping failure.
     - One asyncio `ConnectionResetError [WinError 10054]` in
       `_call_connection_lost` came at startup. It is known Proactor
       noise when a client drops its socket (likely the supervisor's
       /health probe), harmless. Silencing it is a possible small fix.
     - **If he ever changes his Windows password, the task must be
       re-registered with the new one**, or it cannot start at boot.
     - **start.cmd is no longer used**: the task runs everything. To
       stop it in order: `New-Item data\serve_forever.stop`.
     - **Only §5d is left:** restart without signing in, after
       2026-10-30.
3. **`OWNER_CHAT_ID=`** his Telegram chat id (send `/id` to the bot), so
   restarts, the budget and failures reach his phone.
   **DONE 2026-10-24: the first app start since 2026-10-12** (start.cmd,
   04:00 IST, then restarted 04:03 with OWNER_CHAT_ID). Checked free:
   - `/ready`: ready, real, database + keys + ffmpeg;
   - /privacy shows his contact link and his name, and the "Sarvam may
     keep" line;
   - the dashboard's all-time total is **$1.7437**, 10 checks,
     unchanged;
   - verifier.db went from 1,273,856 to **217,088 bytes**: the
     one-time rewrite plus the 30-day prune, with an empty -wal;
   - `ledger-2026-10-23.db` (UTC date) landed in OneDrive;
   - OWNER_CHAT_ID is set (digits); the app and the bot are running.
   - From now on the real database changes all the time, so its size
     is no check. **The ledger total on the dashboard is.**
4. **`BACKUP_DIR=`** a OneDrive (or USB) folder, so the daily copies of
   the spend record leave this laptop. **DONE 2026-10-23:**
   `OneDrive\InformationVerifier-backups` exists, and the setting points
   to it (checked without printing it). The first app start should put
   a `ledger-<date>.db` there.
5. **DONE 2026-10-23** (checked without printing): `CONTACT_EMAIL` is a
   Gmail address, and `OPERATOR_NAME` is set. The first app start shows
   both on /privacy.
   **What the privacy notice publishes:** `CONTACT_EMAIL` (the notice and
   the terms give it as the place to write for deletion, corrections and
   complaints) and, if he wants a name shown, `OPERATOR_NAME`. A role
   address avoids a personal one. It is his decision, never guessed and
   never in the repo; startup warns without it.
6. **This PC:**
   - Device encryption on (Settings → Privacy & security → Device
     encryption). Telegram's bot terms want stored data encrypted at rest.
     If Windows Home doesn't offer it, §11 29 has the other way.
   - Sleep: Never when plugged in. Lid close: Do nothing.
   - Windows Update active hours: 07:00–01:00.

   **DONE 2026-10-23, read back here:**
   - sleep on AC is Never; lid on AC is Do nothing (his screenshot);
   - active hours are 7–1, set manually;
   - Settings says Device encryption is "On". But the shell's code was
     7 (unmapped), so whether protection is truly on (a TPM protector,
     not "waiting for activation") needs `manage-bde -status C:`, run
     as admin.
   - **MEASURED by him, as admin:** "Used Space Only Encrypted, 100%,
     **Protection Off**, Key Protectors: **None Found**".
     - The data is encrypted, but its key sits unsecured on the same
       disk (Microsoft: `-protectors -enable` "removes the unsecured
       encryption key").
     - So it is **NOT protected at rest**, and Telegram §4.4(a) is not
       met yet (§11 29).
     - Plan, his to run as admin: add a recovery-password protector
       first, saved off the PC; then a TPM protector (TPM-only, so
       unattended reboots still unlock); then `manage-bde -protectors
       -enable C:`.
     - On Home, `manage-bde -protectors -add` may fail with 0x8031005a;
       `Add-BitLockerKeyProtector` is the reported workaround.
     - **DECIDED (Vinayak, 2026-10-23): leave it OFF; revisit at the VM
       move.** Telegram §4.4(a) is a known gap until then (PROJECT_PLAN
       §11 29). Do not reopen it unasked.
   - **He signs in with a LOCAL account** (Get-LocalUser:
     PrincipalSource Local). So no recovery key was ever saved to a
     Microsoft account, and he found none there.
     - Offered: `manage-bde -protectors -get C:` (admin), and keep the
       48-digit key off this PC.
     - For §5: the Task Scheduler task needs that local account's
       password. A blank one is refused for a batch logon.
   - Updates are paused until 2026-10-30 02:23 UTC. He has work open
     until month end, so §5's reboot test waits until then.
7. **The .com:**
   - Buy it at Cloudflare Registrar, with a Visa, Mastercard or Amex
     enabled for international payments with 3-D Secure. If the card is
     declined, use any registrar plus Cloudflare's nameservers.
   - Turn Bot Fight Mode OFF.
   - Add a free Turnstile widget and put its keys in `.env` as
     `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY`. Without them startup
     warns, and visitors are not challenged.
8. **The tunnel:**
   - login, create, route dns, then `config.yml` with the `/dashboard`
     fence first;
   - `PUBLIC_HOSTS=<the .com>` in `.env`. Without it every visitor is
     refused, and the server prints each refused name once;
   - the first test from his phone on mobile data.
9. **@BotFather:** set the bot's privacy policy to
   `https://<the .com>/privacy`.
10. **Running unattended:**
    - cloudflared as a service, WITH the registry ImagePath edit. Without
      it the service runs no tunnel (re-check F-5).
    - The Task Scheduler task that runs `scripts\serve_forever.py` at boot.
11. **Two yes-or-no questions:** update yt-dlp (it is 2026.8.19; startup
    says when it is over 30 days old)? Install deno, the JS runtime yt-dlp
    wants for YouTube? Ask before either.
    **yt-dlp: YES, done 2026-10-24.**
    - 2026.8.19 → **2026.10.21**; pip check is clean; the suite passes
      on it (1334).
    - link_probe resolves a real Facebook share reel (14 s, within the
      cap).
    - Instagram and YouTube Shorts are unprobed: no real link to hand.
    - The running app and bot pick it up at their next restart.
    - **deno: still unasked.**
12. **WhatsApp, the slow items** ([decision-brief §4](docs/research/2026-10-15/decision-brief.md),
    [whatsapp.md](docs/research/2026-10-15/whatsapp.md) "Start TODAY"):
    - a new SIM that has never been on WhatsApp, kept recharged;
    - a free Udyam registration, in exactly the name Meta and the site
      will show. Business verification takes ~7 business days after it
      and is optional at first;
    - the Meta developer account, then an app, a business portfolio and a
      WhatsApp Business Account, in **INR**;
    - a card in Billing Hub. Without one, replies stop after the free
      1,000 a month.

    The risk: Meta's terms §4.7 bar AI providers whose primary function is
    AI, at Meta's discretion. The Quint launched an AI fact-check bot on
    WhatsApp in India in May 2026. Asking Meta for a written view before
    the build is optional.
13. **Decisions recorded for him:**
    - §11 24: for a link plus a short question, check the link?
    - §11 28: DPDP Rule 8(3)'s one-year retention against the 30-day
      deletion. Needed before 13 May 2027.

---

### The record, newest first — what was done, with its commits

**2026-10-17: the RE-CHECK of the step-5 fixes and of step 4's runner and
runbook, COMPLETE:**
[docs/research/2026-10-16/review-fixes-step5.md](docs/research/2026-10-16/review-fixes-step5.md),
13 findings (4 medium, 9 low). FIXED: F-12 1ae3cc3 (the bot's notice:
"our copy", Sarvam by the switch); F-4 + F-8 5acbbad (the supervisor in
its own job first; a stop file for an orderly unattended stop); F-1
1f23fc2 (two more real-database copies deleted; scripts/find_db_copies.py
finds copies by what they are); F-2 + F-6 + F-9 c584e1d (bot: chats let
go the moment their day ends; the restart hand-over locked and counted;
one bot at a time; scripts/bot_explorer_restarts.py); F-3 + F-7 + F-11 +
F-13 e039852 (store: scratch folder per database file; a WAL truncate
that never stalls the app and tells the truth; the one-time VACUUM
guarded; the one ledger writer knows restored rows); F-5 + F-10 09dc74d
(go-live.md: the cloudflared ImagePath step without which the service
runs no tunnel; what a fallback service account needs); the docs,
a6c3fe6. **ALL 13 are closed; 1316 tests.** These third-round fixes were
proven by failing-first tests, mutants and 6,000 explorer seeds — not yet
by a fresh reviewer. The review's "notes, not findings" are at the end of
its file and in PROJECT_PLAN §11 32.

**2026-10-16 (late night): the review of step 5, COMPLETE:**
[docs/research/2026-10-16/review-step5.md](docs/research/2026-10-16/review-step5.md),
18 findings (7 medium, 11 low), each reproduced. FIXED: S5-3
2e4562c (midnight), S5-4 ebbe0aa (Sarvam switch), S5-10 300f375 (three
real-database copies deleted + a CLAUDE.md rule), S5-7/S5-8/S5-18 ed88772
(forget.py finds reels, pasted addresses; one save; no wholesale deletion);
the bot's six (S5-1, S5-2, S5-5, S5-6, S5-9, S5-13) in one commit,
df14115, checked by scripts/bot_explorer.py — now in the repo — over
2,000 interleavings; S5-11, S5-12, S5-16, S5-17 in one commit, 344ef13
(deleted is gone from the file: secure_delete + a WAL truncate + a
ONE-TIME VACUUM of the real database at the next app start; backups carry
a one-way reference, never a job id; a deleted check's stream is not
replayed; working files under data/tmp, emptied at startup); S5-14 +
S5-15 (the notice says "we delete OUR copy"; the iOS Install button only
where Add to Home Screen exists). ALL 18 findings are closed (ae85077).

**2026-10-16 (late night): step 4 made ready for the owner:**
[docs/go-live.md](docs/go-live.md) (800d26c, kept current since) — every
owner step in order, each with its check: the settings, the domain, the
tunnel (with the /dashboard fence), the first test from a phone, then
cloudflared as a service and `scripts/serve_forever.py` as a boot task
(8a15b30: runs the app and the bot unattended, restarts either, logs to
logs/, children die with it; since 5acbbad, `New-Item
data\serve_forever.stop` stops it in order, letting running checks
finish).

**2026-10-16 (night): step 5 of the brief's §6, built.** It added:
- a privacy notice and terms pages;
- an "answers are written by AI" line on every surface;
- an 18+ line beside submit;
- the bot's /privacy;
- the installable-app manifest and icons (no service worker).

Each part is its own pushed commit. The operator's published name and
contact stay unset until Vinayak says what to publish. Landed: 60beff7 (the limiter forgets
who asked after the day it counts — found while drafting the notice; it
kept IP addresses in memory for weeks); dfb16b7 (`/privacy`, `/terms`,
served by app/api/legal.py with the periods read from settings; the AI +
18+ line beside Check; "AI-written" on every answer); bb623ae (the bot:
the AI line on every answer and in /start, /privacy, /delete; a bare
unknown /command gets help instead of being a PAID check — measured; "/id"
no longer makes the next message look mid-check); 4806194 (scripts/forget.py — how
the owner honours a deletion request: `--job <id>` from a web address, or
`--text "…" --day YYYY-MM-DD` from a message; lists first, `--yes`
deletes the check and cached copies of its message; the ledger keeps its
content-free row; dry-run on a copy of the real database worked); the
installable app (manifest, icons drawn by scripts/make_icons.py, an
"Install app" button, an iOS "Share → Add to Home Screen" hint, a GET
share target that only FILLS the box; no service worker — headless Chrome
over DevTools: no manifest errors, no installability errors, and a shared
reel link filled the box with no /verify request).
69e7d6d (the pages' markers filled in one pass).

**2026-10-16 (evening): the brief's §6 step 3 — restarts, the ledger,
monitoring — DONE**
([audit-ops.md](docs/research/2026-10-15/audit-ops.md)): OPS-06
b7d4ced (a check always ends — saved, billed, its stream closed — and a
5-minute sweep fails rows stuck mid-flight that nothing here still runs);
OPS-04 2b5a261 (a running check's bill so far is checkpointed onto its row,
so a killed one still reaches the ledger); OPS-05 (one server per
database: an OS lock beside it, taken before the startup sweep — a second
copy now refuses instead of failing the first one's checks; share_demo.ps1
asks for the running app to be closed) 32462f1; OPS-07 + R12 (the bot's
pending checks persist in data/bot_pending.json and a restarted bot
delivers them) 0ba4f62; OPS-18 + §11 19 (`/ready`: a database write+read
on the /reports pool within 3 s, the key, ffmpeg, and real|demo — the bot
refuses the demo) d65638f; OPS-11/08/20 (no access log — it printed visitor
IPs and job ids; platform errors logged without URL or post id; `--workers
1` explicit; output line-buffered and PYTHONUNBUFFERED) 7f97c0e; OPS-10 (a
daily content-free backup of the spend record — never a message — last 14
kept in data/backups or BACKUP_DIR; a tested restore) 2581d1e; OPS-24
a66cf5e (requirements.lock: the 29 exact tested packages — a fresh venv
from it passed the whole suite, 1131 tests; caps on majors; pytest in
requirements-dev.txt); OPS-25 (yt-dlp warnings logged once, scrubbed;
startup says when yt-dlp is >30 days old — it was 58 days on 2026-10-16:
ASK Vinayak before `pip install -U yt-dlp`, and before installing deno,
the JS runtime yt-dlp wants for YouTube) 6c74d76; OPS-19 (owner alerts on
Telegram: paused for money, the budget running low or spent, 3 failures in
a row, a restart or a sweep that failed checks — to OWNER_CHAT_ID, each
kind at most hourly; the bot's /id tells anyone their chat id). Step 3's
remaining audit items are for a cloud host: OPS-09 (pool starvation on 1
vCPU) and OPS-26 (slow memory growth). OPS-21 (config read from the
working directory) is covered: `serve_forever.py` runs its children from
the project folder, and go-live.md's task sets it too.

**2026-10-15/16: the brief's §6 steps 1 and 2, DONE, all pushed**
(PROJECT_PLAN §7 has the why and every measurement). The five reproduced
pre-public blockers
([audit-security.md](docs/research/2026-10-15/audit-security.md)), each
fixed (50dcf3b, 1080d2d, 020e26f):
- one stranger could use up the day's cap;
- a 25 MB text post froze the server for 10–19 s;
- the bot answered anyone, even with no public URL;
- any website could make its visitors submit paid image/voice checks
  (cross-site);
- concurrent refunded link resolves locked everyone out, free and
  untraceably.

Then: per-person limits
(55d3de0); the $1/day DOLLAR budget, cheaper as the day drains, repeats
free (20e882d, 0951150); the review of those fixes, R1–R15, all fixed or
deferred (R10, R12 → §11 25–26; table in
[review-blockers.md](docs/research/2026-10-15/review-blockers.md)) and a
re-check of the fixes that found five more (dc3ebd4 … 56c3990); Anthropic
refusing for MONEY pauses checking at no cost (f545885, dbd5f08); the
dashboard shows the day's money (42d1dd9); Turnstile + the signed device
cookie — 3 checks a day per web device, the bot and this machine never
challenged (b6daec5, f724156, b79bb2a; run end to end in real headless
Chrome with Cloudflare's test keys).

**DECIDED (Vinayak, 2026-10-15, PROJECT_PLAN §7):** this PC now behind a
Cloudflare named tunnel, a VM later · a $1/day dollar budget with per-person
limits · the bot open to anyone, 5 a day each · a .com via Cloudflare. The
research is complete and verified (except `whatsapp.md`, complete but
unverified), and the brief is corrected:
[docs/research/2026-10-15/decision-brief.md](docs/research/2026-10-15/decision-brief.md).

**Done, all pushed (2026-10-15):** e4a9822 (no key in any `Settings` repr, §11 17) ·
63f8049 (the bot token never reaches a log line) · 9a737bd (an over-20 MB
Telegram file gets the real reason) · ee49622 (docs; translated Hindi lookups
measured, 3/12 → 7/12) · ca76538 (Facebook reel and share links resolve in the
app — they never did) · ad79c00 (the research, persisted in
[docs/research/2026-10-15/](docs/research/2026-10-15/README.md)).

---

## 1. The startup prompt — copy everything between the lines

```
Continuing my "Information Verifier" project — a general-purpose claim verifier
(paste text, a screenshot, a voice note, or a Reel/Shorts/Facebook link; get one
Claude-style prose answer, with a skimmable summary, a confidence % and
clickable sources), at
c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier
(git repo, pushed to https://github.com/VinayakMokashi/Information_Verifier, private).

FIRST, read these in order:
1. HANDOFF.md      — the whole project in one file: state, costs, decisions, to-dos.
                     Its §0 is the resume point: if it lists work in flight,
                     a session ended mid-task — verify, then resume there.
2. CLAUDE.md       — how we work here: money rules, the 10 invariants, conventions.
3. PROJECT_PLAN.md — depth. §0 status, §7 decisions log (newest first: read the
   2026-10-17, 2026-10-16 and 2026-10-15 entries), §8 MEASURED costs,
   §11 THE TODO LIST (A: website, B: WhatsApp, C: the rest).
Your memory also has entries for this project.

Verify the state first (free, ~2 min) — and read pytest's OWN exit code:
  .\.venv\Scripts\python.exe -m pytest tests -q     # expect 1334 passing

Money: I'm cost-conscious. MEASURED per check: ~$0.008 when Google's free
fact-check database already covers the claim (about half of English hoaxes),
~$0.05-0.06 when a fact-checker covered it, ~$0.15-0.17 when it searches the
wider web, ~$0.08-0.26 for a reel, $0 for a repeat or for "hi". The whole app
spends at most $1 A DAY (and 5 checks a day per Telegram user). DON'T run
paid tests without asking me —
CLAUDE.md has a table of free paths that cover nearly everything.

To run it: double-click start.cmd (the app + the Telegram bot, two windows).
Restart both windows after pulling new code.

Work the way we have been: systematic layered commits PUSHED AFTER EACH ONE,
adversarial review of the diff INCLUDING of the fixes themselves, measure
rather than assume — and read what a failing run PRINTED before naming a
mechanism (on 2026-10-11 a fix built on a wrong diagnosis had to be
reverted). Keep PROJECT_PLAN.md + HANDOFF.md current. Process rules we learned
the hard way are in CLAUDE.md: check pytest's own exit code; write anything
containing a backslash with the Edit/Write tools, never a shell heredoc; look
at a UI in headless Chrome before calling it done; concurrency tests need
fakes that suspend; a test that HANGS on the bug is not a test that fails;
work that outlives a test must not touch the next one.

What I want to do now (PROJECT_PLAN §11 A-C):
  (A) Make it a website/app anyone can access. Start by laying out the
      choices — where it runs 24/7, the daily budget and limits for
      strangers, what must be fixed before any public URL (§11 17, 18) —
      and ask me to decide before building.
  (B) Then the WhatsApp bot (Meta's Cloud API; business verification is
      slow, so tell me early what I need to start).
  (C) And the remaining to-dos in §11, in value order.
```

**Where (A)–(C) stand on 2026-10-17.** This note sits outside the prompt;
the prompt stays in Vinayak's words. (A) was decided on 2026-10-15 and is
built; step 4 waits on the owner (§0). (B) is next, then (C). A session
started with this prompt takes §0 as its current task, not (A)'s "lay out
the choices".

### 1b. The resume prompt for the session after 2026-10-17

Written by Claude at the end of the 2026-10-17 session, for picking up
exactly where it stopped. The next session updates or replaces it when it
ends.

```
Continuing my "Information Verifier" project at
c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier
(private repo: https://github.com/VinayakMokashi/Information_Verifier).
The last session was 2026-10-18; HANDOFF §0 says what it left. Pick up exactly where it
stopped.

FIRST, read these in order:
1. HANDOFF.md - its §0 is the resume point: the state, what's next for
   you, and my list of owner actions.
2. CLAUDE.md - the money rules, the 10 invariants, and how we work.
3. PROJECT_PLAN.md - §0; §7 newest first (the 2026-10-18 and 2026-10-17
   entries); §11, the to-do list.
4. docs/go-live.md - step 4, my runbook for putting it online.
Your memory has entries for this project too.

THEN verify, all free, and tell me what you find before doing anything else:
- git is clean, and main equals origin/main at the 2026-10-18 handoff
  commit (git log -3).
- .\.venv\Scripts\python.exe -m pytest tests -q gives 1334 passed. Read
  pytest's OWN exit code (0), never through a pipe.
- No stray python, uvicorn or cloudflared processes.
- The app runs now, so data\verifier.db changes all the time (217,088
  bytes after its first start, 2026-10-24). Don't open or copy it. The
  check is the dashboard's all-time total, http://127.0.0.1:8000/dashboard
  ($1.7437 before the first real check), against HANDOFF §0.
- Both files in docs\research\2026-10-16\ say "status: complete".

Where we are:
(A) The public website/app is BUILT. Steps 1-3 and 5 of the build order
    are done and were reviewed twice (31 findings, all fixed). Step 4,
    running 24/7 on this PC at its own .com, waits on MY actions in
    docs/go-live.md.
(B) WhatsApp is not started. Its slow applications (a new SIM, Udyam, the
    Meta account) are mine.
(C) After that, the rest of PROJECT_PLAN §11, in the value order of
    HANDOFF §6.

What I want now:
1. Ask me which of the three offers in HANDOFF §0 ("Offer these; don't do
   them unasked") to do.
2. When I say I'm ready, walk me through docs/go-live.md one step at a
   time, checking each step's result with me.
3. Then (B), then (C).

Money: I'm cost-conscious. Never run anything paid without asking me
first: smoke_test.py, link_smoke.py, ab_models.py, asr_probe.py,
crawl_probe.py, or a real check through the app. CLAUDE.md's table of
free paths covers nearly everything.
Privacy: never read or print .env. What the privacy notice publishes (my
name and contact) is my call, never guessed.

Work the way we have been:
- layered commits, pushed after each one;
- adversarial review, including of the fixes;
- measure, don't assume, and read what a failing run printed before
  naming a cause;
- every new test seen failing first.
Keep HANDOFF §0 and PROJECT_PLAN current at every step. Save every result
to a repo file the moment it exists, so a session limit costs nothing.
```

---

## 2. What it is, in plain words

Someone forwards you a claim. You paste it here — as text, a screenshot, a
voice note, or a link to an Instagram Reel / YouTube Short / Facebook video —
and get back **one plain-prose answer, the way Claude would answer if you
pasted the thing into a chat**: in the language the message arrived in (or one
you pick), streamed word by word, with a confidence %, a highlighted two-line
summary you can skim, and clickable sources underneath.

It first asks **Google's free fact-check database**; when that already has a
vetted fact-check, it answers from it without searching at all. Otherwise it
searches a **vetted whitelist** (Alt News, BOOM, Factly, PIB, The Quint, WHO,
NASA, Snopes, Full Fact… 57 trusted domains, 43 searchable) and only then the
**open web**, which it labels clearly as such. It is allowed to say "nobody
reliable has covered this" — that is a real answer here, not a failure.

**Surfaces:**
- **A chat web page.** It is on this PC only until step 4 puts it at its
  own .com. Everything for the public is built: a Turnstile challenge, the
  privacy notice and terms, an AI line on every answer, and an
  installable-app manifest.
- **A Telegram bot** (@Information_Verifier_bot), live since 2026-09-29. It
  works from any device while this PC runs it, and is open to anyone at 5
  checks a day each.
- A local-only spending dashboard, and console scripts.

**Next: going public (step 4, the owner's), then a WhatsApp bot** (§6).

---

## 3. How it got here (the short history)

| When | What happened |
|---|---|
| Jul 2026 | Built as a 6-stage pipeline producing a rigid "Truth Report" (rating enum, per-claim verdicts). Worked; read like a form. |
| Jul 28 | Reel/Shorts link ingestion built and paid-verified ($0.279 for a 6-claim reel). |
| **Sep 10–11** | **The pivot** (§7): one streaming Claude **Sonnet 5** call, two at most, producing prose. Truth Report, rating enum and the semantic cache deleted — with them went sqlite-vec, sentence-transformers and a 1.2 GB model. |
| Sep 22 (day) | **First paid runs of the new engine.** Costs measured (2–3× cheaper than modelled). Found and fixed: English answered in Hinglish, a self-contradicting trust label, a server that could not start on the real database, two whitelisted domains that block the crawler. Built: the daily cap, retention, the transcript cache, the spending dashboard, a concurrent Telegram bot, plain-language errors. Sonnet 5 beat Opus 5 on the same reel at a quarter of the cost. |
| Sep 22 (eve) | **Two adversarial reviews** of that day's work: 13 defects, all reproduced, all fixed. Then **two reviews of those fixes**: 15 more, five of them introduced by the fixes themselves. |
| **Sep 23** | The reader's two controls: a **skimmable summary** and a **reply-language chooser**. |
| **Sep 29** | **The Telegram bot goes live** from Vinayak's phone; summary and language chooser proven on the real model. Failed searches recorded per check; the cap goes to **5 a day**; the free test suite caught **refilling the real daily cap** (fixed with a canary). |
| **Oct 10** | **One-click launcher** `start.cmd`. Found: the app and bot had kept running unseen for a week after the session that started them. |
| **Oct 11** | **Three cost cuts, measured:** the Google fact-check shortcut (**$0.0084, 6.7 s** for a covered hoax, was ~$0.05 and 28–51 s); pass 1 says "not covered" in one sentence (318 tokens, was an essay); "hi"/"ok"/"thanks" cost nothing. A second test leak (late claims landing in other tests' databases) fixed — after a wrong first fix was reverted. |
| **Oct 15** | Before going public: no credential reaches any printed line (§11 17, and the bot token's leak through error text); an over-20 MB Telegram file gets the real reason; translated Hindi lookups double Google fact-check matches (3/12 → 7/12). Public-launch options researched (§11 A). **Vinayak decides how it goes public:** this PC behind a named Cloudflare tunnel (a VM later), a $1-a-day dollar budget, the bot open to anyone at 5 a day each, a .com. |
| **Oct 15–16** | **The public launch, built** in the brief's order. Step 1: the five pre-public blockers. Step 2: per-person limits, the dollar budget (cheaper as the day drains), Turnstile and a device cookie (3 a day per web device). Step 3: restarts, the ledger, monitoring (owner alerts, daily backups, `/ready`, pinned requirements). Step 5: a privacy notice and terms, an AI line on every answer, the bot's /privacy and /delete, a deletion tool, an installable app. Reviewed: R1–R15 plus 5 more on steps 1–2, then 18 on step 5. All fixed. |
| **Oct 17** | **A re-check of the fixes** found 13 more, all fixed (1316 tests). Step 4's runner and runbook (`serve_forever.py`, `docs/go-live.md`) are ready. Going live now waits on the owner's steps. |

---

## 4. Where it stands right now

- `main` is clean and pushed. **1334 tests pass**, all free (every paid seam is
  faked, and a test proves demo mode cannot reach a paid provider).
- **Ready for the public, waiting on the owner** (§0, `docs/go-live.md`).
  The app and the bot are not running now; nothing has run since
  2026-10-12.
- Proven on the real model: the web page, links/reels, the caches, the
  Telegram bot, the summary, the language chooser, and (2026-10-11) the
  Google fact-check shortcut and the one-sentence pass 1.
- **Met real money on 2026-10-24, in the first real check since
  2026-10-11.** The UNESCO anthem hoax, sent to the bot, cost $0.0089
  through the shortcut (0 searches, tier trusted). It proved:
  - the dollar budget's reserve-and-settle: $0.20 reserved, $0.0089
    committed;
  - the ledger and its new reference;
  - the new workspace key;
  - the bot's delivery (its pending file is empty).
- **Not yet met reality:**
  - the per-person counts (in memory, unseen);
  - Turnstile with real keys, and the device cookie;
  - the owner alerts;
  - the tunnel's streaming;
  - the unattended runner across a real reboot.

  Step 4's later checks cover them.
- **Spent to date: $1.7526** (was $1.7437 before 2026-10-24) — the spend ledger's own total, 18 rows (the
  ledger, not anyone's sum, is the truth: it once caught a $0.26 check the
  docs had missed). Watch it at `http://127.0.0.1:8000/dashboard`.
- **Open problems found on real runs** (PROJECT_PLAN §11):
  the open-web pass is now the expensive and slow part — one took **295 s**,
  longer than the bot waits (items 21, 23); Google's lookup misses Hindi and
  Hinglish forwards entirely (20); source narrowing is per *domain*, so a big
  site brings unrelated pages (15); there is no eval set, so quality
  trade-offs can't yet be tested safely (22). Fixed: 17 (keys in a
  `Settings` repr, 2026-10-15, with the bot token's own leak through error
  text) and 18 (the bot answers anyone — now on purpose, 5 a day each,
  2026-10-15/16).
- **Open from the launch work** (§11 24–32): a question for Vinayak on
  "is this true? <link>" (24); two per-person hardenings to make before
  the setup changes (25, 27); the DPDP one-year-retention decision before
  13 May 2027 (28); encryption at rest (29, an owner check first);
  declining individualised medical, legal and financial advice (30;
  Anthropic's policy from 12 Nov 2026; a prompt change, so one paid check
  — ask); a "report this answer" control only for the Play Store (31);
  the re-check's small notes (32).

**Measured costs** (Sonnet 5):

| Check | Cost | Time |
|---|---|---|
| A hoax Google's fact-check database covers (shortcut, 2026-10-11) | **$0.0084** | 6.7 s |
| A claim a fact-checker covered (searched, one pass) | **$0.048–0.061** | 28–51 s |
| A fresh rumour (whitelist, then open web) | **$0.150–0.172** | 57–295 s |
| A real reel | **$0.082–0.256** + ASR (₹0.58 per 70 s, once per video) | 34 s+ |
| "hi", "ok", "thanks" (2026-10-11) | **$0** — refused before any spend | instant |
| The same thing sent again (cache) | **$0** | instant |

**Every pass carries ~8,000 tokens of fixed setup** — ~2,000 our
instructions, ~5,900 the web-search tool's own. That is why the shortcut,
which sends no tool, is so cheap.

**Safety settings in force** (the numbers are in `app/config.py`, pinned by
tests):
- **Deployment-wide: $1 a day.** Each check reserves its kind's worst case
  and settles at its real cost. It gets cheaper as the day drains: below
  40% left, no open-web pass; below 15%, only Google's published
  fact-checks. 40 checks a day at most, as a backstop. Persisted in
  SQLite, India's day, shared by page and bot, and it fails closed. When
  Anthropic refuses for money, checking pauses at no cost.
- **Per person:**
  - one check at a time (3 at once per IPv4 address, which NAT shares);
  - 10 an hour;
  - per day: 5 per Telegram user and WhatsApp number, 3 per web device
    (the cookie a Turnstile pass earns), and without a cookie 5 per IPv6
    /64 or 20 per IPv4 address.
  Who someone is stays in memory only, cleared after the day it counts.
- **Kept:** messages for 30 days; the answer cache 7 days (1 for
  open-web answers); reel transcripts 30 days; costs forever, with no
  content. Deletions are secure (secure_delete, then a WAL truncate). The
  dashboard and the admin routes refuse anything that is not this
  machine.

---

## 5. The decisions that constrain everything (don't undo these by accident)

The ten invariants are in [CLAUDE.md](CLAUDE.md); these are the ones that bite:

1. **The label is evidence, never assertion.** "Fact-checkers" requires a
   trusted URL an API itself returned (web search, or Google's fact-check
   database). The model can LOWER the label, never raise it — and the
   open-web pass can never earn it, because it is *told* to say no vetted
   source covered the claim.
2. **"Could not verify" is a real answer.** Never manufacture a decisive one.
3. **Prose is never a receipt.** Links, confidence and the summary come from
   structured fields; the model's markdown renders as text everywhere.
4. **Machine-read text is shown back** (ASR/OCR), so a mis-hear can't silently
   become a confident answer about different words.
5. **Every paid call is bounded before it is made**, and the daily cap is
   taken atomically in SQLite, failing closed.
6. **Caches degrade to doing the work, and expire.**
7. **The verdict tag is never visible and never forgeable.**
8. **Streaming never forks the truth** — the persisted answer is canonical
   (why the fact-check shortcut holds its words until it is kept).
9. **Every paid seam has a fake, and the fake is pinned.**
10. **Messages are forgotten; costs are not.**

---

## 6. The next steps (agreed 2026-10-11; where each stands on 2026-10-17)

Vinayak: *"We need to make this into an app/website which anyone can access
and also a whatsapp bot. And also work on the remaining todo's."*
PROJECT_PLAN §11 A–C has the detail.

- **A. A website/app anyone can use: DECIDED 2026-10-15, BUILT by
  2026-10-17.** Only step 4 is left, and it is the owner's
  (`docs/go-live.md`). The original framing, kept for the record: decide
  first where it runs 24/7 (a small cloud host with a disk, or this PC
  behind a named Cloudflare Tunnel), the daily budget and per-person
  limits for strangers (the old 5/day cap was deployment-wide and would
  have run out in minutes), and a bot shield; fix §11 17 and decide §11
  18 before any public URL; a web-app manifest makes the page installable
  on phones — the cheap "app". All done. After launch, see on a real
  Android phone the install prompt and what WhatsApp's share sheet
  offers.
- **B. The WhatsApp bot**, once A gives it a public webhook: Meta Cloud API,
  business verification (slow — start early), a WhatsApp formatter, the
  Telegram bot's per-chat logic reused. What the owner starts first is
  item 12 of §0's owner list. The research
  ([whatsapp.md](docs/research/2026-10-15/whatsapp.md)) is complete but
  was never independently verified, so re-check Meta's pricing and terms
  before building.
- **C. The remaining to-dos, in value order:**
  1. **30, declining individualised advice.** It is time-bound: Anthropic's
     policy takes effect on 12 Nov 2026, and the app may be public by
     then. It is a prompt change, so one paid check — ask first.
  2. **The eval set (22).** It gates every quality-for-cost trade-off.
  3. **The basic-search-tool A/B (21)**, which may also settle 15 and 23.
  4. **Hindi queries for the Google lookup (20).** Measured: 3/12 → 7/12.
  5. **23**, pass 2 outlasting the bot's wait, unless 21 settles it.
  6. **25 and 27**, the per-person hardenings, before the setup they
     guard changes.
  7. Then the rest: 9a, 10, 11, 4–16. The cloud-only items (OPS-09,
     OPS-26) wait for the VM.

  Vinayak's to answer: 24 (a link plus a short question) and 28 (DPDP
  retention, before 13 May 2027). 29 (encryption at rest) starts with his
  Device-encryption check.

---

## 7. How to run and test it

Always the venv Python: `.\.venv\Scripts\python.exe …`

**Free (spends nothing):**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q            # 1334 tests, ~3-10 min
.\.venv\Scripts\python.exe scripts\serve_demo.py         # the real page, simulated engine
.\.venv\Scripts\python.exe scripts\demo_offline.py       # engine + cache, in the console
.\.venv\Scripts\python.exe scripts\link_probe.py "<reel url>"   # does a link resolve?
.\.venv\Scripts\python.exe scripts\telegram_bot.py --check-token
.\.venv\Scripts\python.exe scripts\bot_explorer.py            # 2,000 random bot interleavings
.\.venv\Scripts\python.exe scripts\bot_explorer_restarts.py   # the same, with restarts and expiry
.\.venv\Scripts\python.exe scripts\find_db_copies.py          # any copy of the real database? (slow: scans %TEMP%)
.\.venv\Scripts\python.exe scripts\forget.py --job <id>       # a deletion request: lists first, --yes deletes
```

CLAUDE.md's table has every free path, and what each proves.

**Real (spends money — ask first; the app's $1-a-day budget):**

**One click: double-click `start.cmd`** in the project folder (or run
`.\start.ps1` in a terminal). It opens the app in one window, waits until it
answers, then opens the bot in a second; it starts nothing that is already
running, and refuses if the free demo server holds the port (a bot wired to
it would send fake answers). Stop: Ctrl+C in each window, or close them.
**After pulling new code, close both windows and start again** — a running
app keeps the code it started with. By hand, the same two steps:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app       # one worker only
# then http://127.0.0.1:8000  (the page)  and  /dashboard  (what it has spent)
.\.venv\Scripts\python.exe scripts\telegram_bot.py       # terminal 2, for the bot
```

`scripts\smoke_test.py --raw "claim"` and `scripts\link_smoke.py <url>` run one
real check from the console and print the bill (`--raw`: every API request's
usage, which is how the shortcut's single no-tool call was confirmed).

**Unattended (step 4, once the owner sets it up):** `scripts\serve_forever.py`
runs the app and the bot from a Task Scheduler task at boot. It restarts
either if it stops, logs to `logs\` (14 days kept), and tells the owner's
phone of each restart. `New-Item data\serve_forever.stop` stops it in order:
the bot first, then the app once running checks finish (up to 5 minutes).
Close `start.cmd`'s windows before starting it: only one app and one bot
may run. [docs/go-live.md](docs/go-live.md) has the setup and "if something
goes wrong".

---

## 8. Where the code lives

`app/api/` routes (text / image / media / link) → `app/engine/job.py`
(`run_check`: cache → engine → persist → spend ledger) → `app/engine/chat.py`
(Google fact-check shortcut, then pass 1 whitelist, then pass 2 open web) →
`app/store/` persists. `app/engine/chat_prompts.py` holds every prompt (their
fingerprint keys the answer cache); `app/engine/triage.py` decides what is
not worth checking ("hi"); `app/engine/marker.py` pulls the verdict tag and
the summary out of the model's words. `app/providers/` wraps every external
service. `app/api/stream.py` is the live SSE preview, `app/api/dashboard.py`
the local-only spending page, `app/api/limits.py` the daily cap,
`app/hosts.py` the ONE place a URL's host is read. `static/index.html` is the
whole web page; `scripts/telegram_bot.py` the bot; `start.ps1`/`start.cmd`
the launcher; `scripts/fake_stages.py` the fakes that make it free to test.

Added for the public launch (2026-10-15/17):
- **Limits and identity.** `app/api/limits.py` now also holds the dollar
  budget and the per-person limits. `app/api/local.py` is the one "is this
  request from this machine?" rule. `app/api/device.py` is the signed
  device cookie, and `app/providers/turnstile.py` the challenge that earns
  it.
- **Legal pages.** `app/api/legal.py` serves `/privacy` and `/terms` from
  `privacy.html` and `terms.html`, with their periods read from the
  settings the deleting code uses.
- **Operations.**
  - `app/providers/alerts.py`: the owner's Telegram alerts.
  - `app/store/backup.py`: the daily content-free ledger backup.
  - `app/store/instance.py`: one server per database.
  - `app/store/scratch.py`: working files under `data/tmp`.
  - `scripts/serve_forever.py`: the unattended runner.
- **The app's files.** `static/manifest.webmanifest`, and the icons
  `scripts/make_icons.py` draws.
- **Owner's tools.** `scripts/forget.py` (deletion requests),
  `scripts/find_db_copies.py`, and `scripts/lock_requirements.py` (writes
  `requirements.lock`).
- **The owner's runbook:** `docs/go-live.md`.

The REST contract is deliberately surface-agnostic: submit → `{job_id}` →
poll `/reports/{job_id}`, with an optional `/stream/{job_id}` for live text.
Every surface — page, Telegram, and the WhatsApp bot to come — uses the same
two calls.
