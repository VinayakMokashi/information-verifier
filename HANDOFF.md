# Information Verifier — the whole project in one file

> **Read this first in a new session.** It is written so nothing is lost when
> a conversation ends: what the thing is, how it got here, what it costs, what
> is decided, what is open, and how to run it. Depth lives in
> [PROJECT_PLAN.md](PROJECT_PLAN.md) (§7 is the decisions log) and
> [CLAUDE.md](CLAUDE.md) (the invariants and how we work).
>
> Last updated: **2026-09-29**. Repo: `c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier`,
> pushed to https://github.com/VinayakMokashi/Information_Verifier (private).

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
2. CLAUDE.md       — how we work here: money rules, the 10 invariants, conventions.
3. PROJECT_PLAN.md — depth. §0 status, §7 decisions log (newest first: read the
   2026-09-23 and 2026-09-22 entries), §8 MEASURED costs, §11 THE TODO LIST.
Your memory also has entries for this project.

Verify the state first (free, ~2 min) — and read pytest's OWN exit code:
  .\.venv\Scripts\python.exe -m pytest tests -q     # expect 781 passing

Money: I'm cost-conscious. MEASURED per check: ~$0.05-0.06 when a fact-checker
covered the claim, ~$0.15 when it searches the wider web, ~$0.08 + ₹0.58 for a
reel, $0 for a repeat. The whole app is capped at 2 CHECKS A DAY (my decision,
"just to be safe"). DON'T run paid tests without asking me — CLAUDE.md has a
table of free paths that cover nearly everything.

Work the way we have been: systematic layered commits PUSHED AFTER EACH ONE,
adversarial review of the diff INCLUDING of the fixes themselves (on 2026-09-22
a third of the defects came from the fixes for earlier defects), measure rather
than assume, and keep PROJECT_PLAN.md + HANDOFF.md current. Process rules we
learned the hard way are in CLAUDE.md: check pytest's own exit code; write
anything containing a backslash with the Edit/Write tools, never a shell
heredoc; look at a UI in headless Chrome before calling it done; concurrency
tests need fakes that suspend; a test that HANGS on the bug is not a test that
fails.

What I want to do today:
  (a) The Telegram bot is LIVE (2026-09-29). Start the app and the bot for me
      (HANDOFF §7) and keep watching the logs while I use it.
  (b) Record search error codes in each answer (§11 item 16) — free — BEFORE
      any more paid Indian-politics checks; then decide the cap, and a few real
      checks across health / science / Indian politics to judge quality (§11).
```

---

## 2. What it is, in plain words

Someone forwards you a claim. You paste it here — as text, a screenshot, a
voice note, or a link to an Instagram Reel / YouTube Short / Facebook video —
and get back **one plain-prose answer, the way Claude would answer if you
pasted the thing into a chat**: in the language the message arrived in (or one
you pick), streamed word by word, with a confidence %, a highlighted two-line
summary you can skim, and clickable sources underneath.

It checks a **vetted whitelist first** (Alt News, BOOM, Factly, PIB, The
Quint, WHO, NASA, Snopes, Full Fact… 57 trusted domains, 43 of them
searchable) and only then the **open web**, which it labels clearly as such.
It is allowed to say "nobody reliable has covered this" — that is a real
answer here, not a failure.

**Surfaces:** a chat web page (the main one), a Telegram bot (live since
2026-09-29), a local-only spending dashboard, and a set of console scripts.
A WhatsApp bot is on hold.

---

## 3. How it got here (the short history)

| When | What happened |
|---|---|
| Jul 2026 | Built as a 6-stage pipeline producing a rigid "Truth Report" (rating enum, per-claim verdicts). Worked; read like a form. |
| Jul 28 | Reel/Shorts link ingestion built and paid-verified ($0.279 for a 6-claim reel). |
| **Sep 10–11** | **The pivot** (§7): one streaming Claude **Sonnet 5** call, two at most, producing prose. Truth Report, rating enum and the semantic cache deleted — with them went sqlite-vec, sentence-transformers and a 1.2 GB model. |
| Sep 22 (day) | **First paid runs of the new engine.** Costs measured (2–3× cheaper than modelled). Found and fixed: English answered in Hinglish, a self-contradicting trust label, a server that could not start on the real database, two whitelisted domains that block the crawler. Built: the 2-a-day cap, retention, the transcript cache, the spending dashboard, a concurrent Telegram bot, plain-language errors. Sonnet 5 beat Opus 5 on the same reel at a quarter of the cost. |
| Sep 22 (eve) | **Two adversarial reviews** of that day's work: 13 defects, all reproduced, all fixed. Then **two reviews of those fixes**: 15 more, five of them introduced by the fixes themselves. |
| **Sep 23** | The reader's two controls: a **skimmable summary** and a **reply-language chooser**. |
| **Sep 29** | **The Telegram bot goes live** from Vinayak's phone. The summary and the language chooser both work against the real model. Fixed: the bot's startup health check checked nothing. Found: a ₹2000 answer showed an RBI ₹20-note page as a receipt, and an unrecorded Sep 23 politics reel paid for 5 searches that returned nothing. |

---

## 4. Where it stands right now

- `main` is clean and pushed. **781 tests pass**, all free (every paid seam is
  faked, and a test proves demo mode cannot reach a paid provider).
- The engine has run for real; the web page, the link path, the caches, **the
  Telegram bot, the summary and the language chooser** are all proven.
- **Spent to date: $1.2364** — the spend ledger's own total, 13 rows: five
  checks on the page or bot ($0.37), a $0.26 politics reel on 2026-09-23 that
  the docs had missed, and $0.61 of operator scripts (the Sonnet-vs-Opus A/B
  and the language diagnostics). Watch it at `http://127.0.0.1:8000/dashboard`.
- **Open problems found on real runs:** source narrowing is per *domain*,
  so big sites bring unrelated pages; a fresh rumour gets two full answers
  (pass 1 does not stop short); and search errors are not recorded anywhere
  that survives the console (PROJECT_PLAN §11 items 4, 15, 16).

**Measured costs** (Sonnet 5, 2026-09-22):

| Check | Cost | Time |
|---|---|---|
| A claim a fact-checker has covered (one pass) | **$0.048–0.061** | 28–51 s |
| A fresh rumour (whitelist, then open web) | **$0.150** | 57 s |
| A real reel | **$0.082** + ₹0.58 ASR, once per video | 34 s |
| The same thing sent again (cache) | **$0** | instant |
| A long political reel, both passes, searches all failed (Sep 23) | **$0.256** | — |

**Safety settings in force:** 2 checks a day deployment-wide (persisted in
SQLite, India's day, shared by page and bot, fails closed); messages deleted
after 30 days with costs kept content-free; the dashboard is refused to
anything that is not this machine.

---

## 5. The decisions that constrain everything (don't undo these by accident)

The ten invariants are in [CLAUDE.md](CLAUDE.md); these are the ones that bite:

1. **The label is evidence, never assertion.** "Fact-checkers" requires a
   trusted URL the API itself returned. The model can LOWER the label, never
   raise it — and **only the whitelist pass can earn it**, because the
   open-web pass is *told* to say no vetted source covered the claim.
2. **"Could not verify" is a real answer.** Never manufacture a decisive one.
3. **Prose is never a receipt.** Links, confidence and the summary come from
   structured fields; the model's markdown renders as text everywhere.
4. **Machine-read text is shown back** (ASR/OCR), so a mis-hear can't silently
   become a confident answer about different words.
5. **Every paid call is bounded before it is made**, and the daily cap is
   taken atomically in SQLite, failing closed.
6. **Caches degrade to doing the work, and expire.**
7. **The verdict tag is never visible and never forgeable.**
8. **Streaming never forks the truth** — the persisted answer is canonical.
9. **Every paid seam has a fake, and the fake is pinned.**
10. **Messages are forgotten; costs are not.**

---

## 6. The next steps (updated 2026-09-29)

1. ~~**Switch the Telegram bot on.**~~ **Done 2026-09-29.**
1a. **Record search error codes in the answer** (§11 item 16), free, before
   more paid politics checks: the one politics reel so far paid for 5
   searches that returned nothing, and nobody can say why.
2. **Decide the cap.** Raising it from 2 is one number in `app/config.py`
   plus the test that pins it.
3. **A few more real checks** across health, science and Indian politics, to
   judge answer quality on fresh rumours (only one two-pass run so far).
4. **WhatsApp stays on hold** — Meta's approval is slow. When it happens it
   reuses the bot's `format_reply` unchanged.

Everything else open — smaller code items, residuals from the reviews — is in
**PROJECT_PLAN §11**, which is the authoritative to-do list.

---

## 7. How to run and test it

Always the venv Python: `.\.venv\Scripts\python.exe …`

**Free (spends nothing):**

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q            # 781 tests, ~2 min
.\.venv\Scripts\python.exe scripts\serve_demo.py         # the real page, simulated engine
.\.venv\Scripts\python.exe scripts\demo_offline.py       # engine + cache, in the console
.\.venv\Scripts\python.exe scripts\link_probe.py "<reel url>"   # does a link resolve?
.\.venv\Scripts\python.exe scripts\telegram_bot.py --check-token
```

**Real (spends money — ask first; 2 checks a day):**

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app       # one worker only
# then http://127.0.0.1:8000  (the page)  and  /dashboard  (what it has spent)
.\.venv\Scripts\python.exe scripts\telegram_bot.py       # terminal 2, for the bot
```

`scripts\smoke_test.py "claim"` and `scripts\link_smoke.py <url>` run one real
check from the console and print the bill.

---

## 8. Where the code lives

`app/api/` routes (text / image / media / link) → `app/engine/job.py`
(`run_check`: cache → engine → persist → spend ledger) → `app/engine/chat.py`
(pass 1 whitelist, pass 2 open web) → `app/store/` persists.
`app/engine/marker.py` is the streaming filter that pulls the verdict tag and
the summary out of the model's words. `app/providers/` wraps every external
service. `app/api/stream.py` is the live SSE preview, `app/api/dashboard.py`
the local-only spending page, `app/hosts.py` the ONE place a URL's host is
read. `static/index.html` is the whole web page; `scripts/telegram_bot.py` the
bot; `scripts/fake_stages.py` the fakes that make everything above free to test.

The REST contract is deliberately surface-agnostic: submit → `{job_id}` →
poll `/reports/{job_id}`, with an optional `/stream/{job_id}` for live text.
Every surface uses the same two calls.
