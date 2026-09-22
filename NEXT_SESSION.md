# Next session — paste the prompt below

> **This file is committed and pushed after every step**, so if a session hits
> its limit mid-work, nothing is lost: `git log` shows exactly where it stopped
> and the "WHERE THE LAST SESSION ENDED" section says what was next.

---

## 1. The startup prompt (copy from here)

```
Continuing my "Information Verifier" project — a general-purpose claim verifier
(paste text, a screenshot, a voice note, or a Reel/Shorts/Facebook link; get one
Claude-style prose answer with a confidence % and clickable sources), at
c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier
(git repo, pushed to https://github.com/VinayakMokashi/Information_Verifier, private).

FIRST, read these in order:
1. NEXT_SESSION.md  — where the last session stopped, and what was next.
2. CLAUDE.md        — how we work here: money rules, the 10 invariants, conventions.
3. PROJECT_PLAN.md  — the source of truth. §0 status, §7 decisions log (newest
   first — the 2026-09-22 entry is the one to read), §8 MEASURED costs,
   §11 "THE TODO LIST".
Your memory also has entries for this project.

Verify the state first (free, ~50s) — and read pytest's OWN exit code:
  .\.venv\Scripts\python.exe -m pytest tests -q     # expect 747 passing

The engine has run for real now (2026-09-22): about $0.05 when a fact-checker
covered the claim, $0.15 for a two-pass fresh rumour, $0.08 for a real reel.
Sonnet 5 stays (it beat Opus 5 on the same reel). The app is capped at
2 CHECKS A DAY (my decision, "just to be safe" — persisted, India's day,
shared by the web page and the Telegram bot). What it has spent is at
http://127.0.0.1:8000/dashboard (this machine only).

I'm cost-conscious — DON'T run paid tests without asking. Free paths for nearly
everything are in CLAUDE.md's table.

Work the way we have been: systematic layered commits PUSHED AFTER EACH ONE,
adversarial review of the diff INCLUDING of the fixes themselves, measure
rather than assume, and keep PROJECT_PLAN.md + NEXT_SESSION.md current.
Process rules we learned the hard way (all in CLAUDE.md): check pytest's own
exit code; write anything with a backslash through Edit/Write, not a heredoc;
look at a UI in headless Chrome before calling it done; concurrency tests need
fakes that suspend.

What I want to do today:
  (a) GO LIVE with the Telegram bot, with me watching. Token is in .env and
      validates (@Information_Verifier_bot). Walk me through starting the app
      and the bot, then we message it and fix whatever real messages break.
      Remember the 2-a-day cap applies to it.
  (b) Then maybe: raise the daily cap, or more real checks across health /
      science / Indian politics to judge answer quality (§11 item 4).
```

---

## 2. What the project can do today

Text · screenshot · voice note/video · **pasted links** (Instagram Reels,
YouTube/Shorts, Facebook videos and share-button reel links) · **Telegram bot**
(concurrent; never yet live — the token works).

One prose answer per submission, streamed onto a chat page in the sender's
language (English in, English out — now stated by code, not left to the
model). Confidence % with its basis; sources narrowed to what the answer rests
on; a clearly-labelled "general web" section when no fact-checker covered it.
57 trusted domains, 43 of them searchable — all verified against the live API.

Money: **measured** $0.048–0.061 single pass, $0.150 two-pass, $0.082 + ₹0.58
for a real reel, $0 for a repeat. 2 checks a day. Spending dashboard at
`/dashboard`. Messages deleted after 30 days; costs kept without content.

---

## 3. THE TODO LIST

The authoritative copy lives in **PROJECT_PLAN.md §11**. Summary:

**Next, with Vinayak present:**
1. **First live Telegram message** — "maybe tomorrow". Everything is ready.

**On hold:** WhatsApp ("Meta's approval process is slow").

**Code, when wanted:** raise the cap; more real checks to judge quality;
mixed-language (English caption over Hindi speech) behaviour; `/health`;
ASR metering seam; thread-pool contention; garbled source titles.

---

## 4. WHERE THE LAST SESSION ENDED

**Session of 2026-09-22 — every to-do Vinayak listed is DONE, committed and
pushed.** `main` is clean, **747 tests pass** (pytest exit 0).

**Then two adversarial reviews of the day's work (evening):** 13 defects,
every one reproduced with a free script and fixed with a test that fails
against the old code — a trust label borrowed from a page the answer did not
use, a DNS-rebinding hole in the dashboard, four ways the verdict tag could
reach a reader, the 2-a-day cap leaking at midnight, a bot message that
could vanish, a deleted job freezing its chat. PROJECT_PLAN §7 ("Two
adversarial reviews") has each one.

**Then the FIXES were reviewed the same way — 15 more defects, five of them
introduced by the fixes themselves**, including a trust label that came back
by another route (an open-web pass can no longer relabel an answer at all),
four more shapes of the verdict tag, and a poke the bot still paid for. Two
were found only by running a reviewer's 2,000-interleaving search against
the already-fixed bot. All fixed, all with failing-first tests. A third
review round was NOT run: the rate of new findings had dropped to corner
cases the §11 list now records.

What he asked, and what happened:

| He asked | Done |
|---|---|
| The first paid run | ✅ Engine works. Measured costs in §8; it found and fixed a Hinglish-for-English bug and a self-contradicting trust label on the way. |
| AFP: "you can decide" | ✅ Kept trusted. Its site blocks the search crawler, so it's reached via Google Fact Check. |
| 2 checks a day, recorded | ✅ Persisted (a restart can't refill it), fails closed, India's day; in config.py with his words, pinned by a test, and in §7. |
| Transcript cache | ✅ A reel is transcribed once, not once per forward. |
| Sonnet vs Opus A/B | ✅ Sonnet stays: right, 4× cheaper, 2.6× faster; Opus reasoned from stale memory. |
| Delete old messages | ✅ 30 days; costs kept in a content-free ledger. |
| Bot one-person-at-a-time | ✅ Concurrent, with a per-chat lock so one chat can't pay twice. |
| Technical error text | ✅ Eight found and rewritten in plain words; details go to the log. |
| Spending dashboard | ✅ `/dashboard`, this machine only; checked visually, light/dark, phone/desktop. |
| Facebook Reels | ✅ Share-button links work; some reels are login-only and now say so. |
| Tidy duplicates | ✅ One host parser (it had a hole: `evil..altnews.in` counted as Alt News), one sentinel stripper, one console stream; the link probe asks the app. |
| Telegram tomorrow; WhatsApp on hold | Recorded in §11. |

**Found only by reality, not by any test** (all in §7): two whitelisted sites
blocked the crawler, so the general-purpose search had never actually run;
the server could not start on the real database; the search tool made
English claims come back in Hinglish; the first "phone" screenshots were
really desktop ones.

**Spent this session:** $0.87 on the dashboard (three checks $0.26, the A/B
$0.41, language diagnostics $0.20) + a fraction of a cent for the crawl probe.
