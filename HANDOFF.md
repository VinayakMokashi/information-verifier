# Information Verifier — the whole project in one file

> **Read this first in a new session.** It is written so nothing is lost when
> a conversation ends: what the thing is, how it got here, what it costs, what
> is decided, what is open, and how to run it. Depth lives in
> [PROJECT_PLAN.md](PROJECT_PLAN.md) (§7 is the decisions log, §11 the to-do
> list) and [CLAUDE.md](CLAUDE.md) (the invariants and how we work).
>
> Last updated: **2026-10-15**. Repo: `c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier`,
> pushed to https://github.com/VinayakMokashi/Information_Verifier (private).

---

## 0. Resume point — where the work is RIGHT NOW (updated at every step)

> If a session ended mid-task (usage limit, network drop), start here.
> Verify first (CLAUDE.md, "Interruptions"), then continue from **Next**.

**Task in hand (2026-10-15):** §11 A–C — lay out the public-launch choices,
ask Vinayak to decide, then build; tell him early what WhatsApp needs.

**Done, all pushed:** e4a9822 (no key in any `Settings` repr, §11 17) ·
63f8049 (the bot token never reaches a log line) · 9a737bd (an over-20 MB
Telegram file gets the real reason) · ee49622 (docs; translated Hindi lookups
measured, 3/12 → 7/12) · ca76538 (Facebook reel and share links resolve in the
app — they never did) · ad79c00 (the research so far, persisted in
[docs/research/2026-10-15/](docs/research/2026-10-15/README.md)).

**In flight — each writes its own file as it goes:**
- WhatsApp research → `docs/research/2026-10-15/whatsapp.md`
- verifiers → `docs/research/2026-10-15/{cloud-hosting,home-tunnel,limits-budget,policy-legal}.verification.md`
- in the session's workflow (its results reach only a session journal, so
  they are copied into the topic files when it finishes): verifiers for
  `ytdlp-cloud-ips.md` and `audit-ops.md`, then a critic.

A research file whose top says **"status: in progress"** means its agent died:
re-run that one task, seeded from the file.

**DECIDED (Vinayak, 2026-10-15, PROJECT_PLAN §7):** this PC now behind a
Cloudflare named tunnel, a VM later · a $1/day dollar budget with per-person
limits · the bot open to anyone, 5 a day each · a .com via Cloudflare. The
research is complete and verified (except `whatsapp.md`, complete but
unverified), and the brief is corrected:
[docs/research/2026-10-15/decision-brief.md](docs/research/2026-10-15/decision-brief.md).

**Done 2026-10-15/16, all pushed** (PROJECT_PLAN §7 has the why and every
measurement): the brief's §6 steps 1 and 2 — the five reproduced
pre-public blockers (50dcf3b, 1080d2d, 020e26f); per-person limits
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

**NEXT — the brief's §6 step 3: restarts, the ledger, monitoring**
([audit-ops.md](docs/research/2026-10-15/audit-ops.md)): OPS-06 run_check's
final save is unguarded (a stuck job, a lost paid answer); OPS-04 a check
killed mid-flight loses its spend from the ledger; OPS-07 the bot forgets
in-flight checks on restart (+ §11 26); OPS-05 a second copy on the same
database; OPS-18 /health is a constant (+ §11 19); OPS-19 no monitoring or
alerting; OPS-20 print() is block-buffered on a host; OPS-11 logs keep IPs
and job ids; OPS-10 no database backup; OPS-24 unpinned dependencies;
OPS-25 no yt-dlp update path. Then (4) running 24/7 here — the domain,
cloudflared as a service, auto-start; (5) privacy notice, terms, the app
manifest; then WhatsApp. Each step: failing test first, commit + push,
update this section.

**Going live needs, in .env:** `PUBLIC_HOSTS=<the .com>` — without it every
visitor is refused (the server prints each refused name once) — and
`TURNSTILE_SITE_KEY` + `TURNSTILE_SECRET_KEY` from a free Turnstile widget
for the .com in the Cloudflare dashboard (without them startup warns, and
visitors are not challenged).

**Owner actions waiting on Vinayak** (free; the brief has details): set
Sarvam's data retention to 0 days; a separate Anthropic workspace with a
monthly spend limit for the public key; buy the .com (if Cloudflare declines
the card, any registrar + Cloudflare nameservers); once the .com exists, a
free Turnstile widget for it (Cloudflare dashboard → Turnstile: two keys
for .env); for WhatsApp, a new SIM and a free Udyam registration. Pre-public **blockers**
already established ([audit-security.md](docs/research/2026-10-15/audit-security.md)):
one stranger can use up the day's cap; a 25 MB text post freezes the server
for 10–19 s; the bot answers anyone, even with no public URL; any website can
make its visitors submit paid image/voice checks (cross-site); concurrent
refunded link resolves lock everyone out, free and untraceably.

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
   2026-10-11, 2026-10-10 and 2026-09-29 entries), §8 MEASURED costs,
   §11 THE TODO LIST (A: website, B: WhatsApp, C: the rest).
Your memory also has entries for this project.

Verify the state first (free, ~2 min) — and read pytest's OWN exit code:
  .\.venv\Scripts\python.exe -m pytest tests -q     # expect 1074 passing

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

**Surfaces:** a chat web page (on this PC only, for now), a **Telegram bot**
(@Information_Verifier_bot, live since 2026-09-29, usable from any device
while this PC runs it), a local-only spending dashboard, and console scripts.
**Next: a public website/app, then a WhatsApp bot** (§6).

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
| **Oct 15** | Before going public: no credential reaches any printed line (§11 17, and the bot token's leak through error text); an over-20 MB Telegram file gets the real reason; translated Hindi lookups double Google fact-check matches (3/12 → 7/12). Public-launch options researched (§11 A). |
| **Oct 11** | **Three cost cuts, measured:** the Google fact-check shortcut (**$0.0084, 6.7 s** for a covered hoax, was ~$0.05 and 28–51 s); pass 1 says "not covered" in one sentence (318 tokens, was an essay); "hi"/"ok"/"thanks" cost nothing. A second test leak (late claims landing in other tests' databases) fixed — after a wrong first fix was reverted. |

---

## 4. Where it stands right now

- `main` is clean and pushed. **1074 tests pass**, all free (every paid seam is
  faked, and a test proves demo mode cannot reach a paid provider).
- Proven on the real model: the web page, links/reels, the caches, the
  Telegram bot, the summary, the language chooser, and (2026-10-11) the
  Google fact-check shortcut and the one-sentence pass 1.
- **Spent to date: $1.7437** — the spend ledger's own total, 17 rows (the
  ledger, not anyone's sum, is the truth: it once caught a $0.26 check the
  docs had missed). Watch it at `http://127.0.0.1:8000/dashboard`.
- **Open problems found on real runs** (PROJECT_PLAN §11):
  the open-web pass is now the expensive and slow part — one took **295 s**,
  longer than the bot waits (items 21, 23); Google's lookup misses Hindi and
  Hinglish forwards entirely (20); source narrowing is per *domain*, so a big
  site brings unrelated pages (15); there is no eval set, so quality
  trade-offs can't yet be tested safely (22); the bot answers anyone (18).
  (17, keys in a `Settings` repr, was fixed 2026-10-15 — with the bot
  token's own leak through error text.)

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

**Safety settings in force:** a $1-a-day dollar budget deployment-wide
(each check reserves its kind's worst case and settles at its real cost;
cheaper as the day drains; 40 checks a day at most as a backstop; persisted
in SQLite, India's day, shared by page and bot, fails closed); per person,
one check at a time and 5 a day (Telegram, WhatsApp; 20 per IPv4 address);
messages deleted after 30 days with costs kept content-free; the dashboard
is refused to anything that is not this machine.

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

## 6. The next steps (agreed 2026-10-11)

Vinayak: *"We need to make this into an app/website which anyone can access
and also a whatsapp bot. And also work on the remaining todo's."*
PROJECT_PLAN §11 A–C has the detail.

- **A. A website/app anyone can use.** Decide first: where it runs 24/7 (a
  small cloud host with a disk, or this PC behind a named Cloudflare Tunnel),
  the daily budget and per-person limits for strangers (the 5/day cap is
  deployment-wide and would run out in minutes), and a bot shield. §11 17
  is fixed (2026-10-15); decide §11 18 before any public URL. A
  web-app manifest makes the page installable on phones — the cheap "app".
- **B. The WhatsApp bot**, once A gives it a public webhook: Meta Cloud API,
  business verification (slow — start early), a WhatsApp formatter, the
  Telegram bot's per-chat logic reused.
- **C. The remaining to-dos**, value order: the eval set (22) — it gates
  every quality-for-cost trade-off — then the basic-search-tool A/B (21),
  Hindi queries for the Google lookup (20), and the rest of §11.

---

## 7. How to run and test it

Always the venv Python: `.\.venv\Scripts\python.exe …`

**Free (spends nothing):**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q            # 1074 tests, ~1 min
.\.venv\Scripts\python.exe scripts\serve_demo.py         # the real page, simulated engine
.\.venv\Scripts\python.exe scripts\demo_offline.py       # engine + cache, in the console
.\.venv\Scripts\python.exe scripts\link_probe.py "<reel url>"   # does a link resolve?
.\.venv\Scripts\python.exe scripts\telegram_bot.py --check-token
```

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

The REST contract is deliberately surface-agnostic: submit → `{job_id}` →
poll `/reports/{job_id}`, with an optional `/stream/{job_id}` for live text.
Every surface — page, Telegram, and the WhatsApp bot to come — uses the same
two calls.
