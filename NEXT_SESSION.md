# Next session — paste the prompt below

> **This file is committed and pushed after every step**, so if a session hits
> its limit mid-work, nothing is lost: `git log` shows exactly where it stopped
> and the "IN PROGRESS" section below says what was next.

---

## 1. The startup prompt (copy from here)

```
Continuing my "Information Verifier" project — a multi-modal fact-checking app
to fight misinformation in India, at
c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier
(git repo, pushed to https://github.com/VinayakMokashi/Information_Verifier, private).

FIRST, read these in order:
1. NEXT_SESSION.md  — where the last session stopped, and what was next.
2. CLAUDE.md        — how we work here: money rules, invariants, conventions.
3. PROJECT_PLAN.md  — the source of truth. §0 status, §0a the reel-link feature
   (it was lost from the plan once — never let that happen again), §7 decisions
   log (skim before changing anything), §11 "THE TODO LIST" = open items.
Your memory also has entries for this project.

Verify the state first (free, ~35s):
  .\.venv\Scripts\python.exe -m pytest tests -q

I'm cost-conscious — DON'T run paid tests without asking. Measured: ~$0.12–0.26
per claim; $0.279 for a whole 6-claim Instagram reel. Free paths for nearly
everything are in CLAUDE.md's table (pytest, serve_demo, demo_offline,
link_probe, factcheck_probe).

Work the way we have been: systematic layered commits PUSHED AFTER EACH ONE
(so a session break never loses work), adversarial review of the diff INCLUDING
of the fixes themselves (that has caught real bugs every single round),
measure rather than assume, and keep PROJECT_PLAN.md + NEXT_SESSION.md current.
When editing docs by script, assert every replace matched — a silent no-op
replace left §11 stale once.

What I want to work on next: <PICK ONE, or tell me your own>
  (a) GO LIVE with the Telegram bot. The token is already in .env and
      validated (@Information_Verifier_bot); the bot has just never been
      started. I'll be at the keyboard — walk me through it and we fix
      whatever the first real messages break.
  (b) §11 item 17: a transcript cache for links, so the same reel forwarded
      by many people is bought once, not once per person.
  (c) Burn down the rest of the §11 backlog (items 7–22).
  (d) Verify the cheap pending items (translation prompt fixes ~$0.04;
      I'll paste a real Facebook reel link for the free probe).
  (e) Prepare for real public sharing: my cap decisions + observability
      + data pruning, then a supervised share_demo.ps1 session.
```

---

## 2. Where the last session stopped

**Session of 2026-07-28 (late).** Vinayak asked for an end-to-end review before
sleeping. A 10-angle review of everything built since `0389647` ran; findings
are being fixed in layered commits.

**STATUS: see the bottom of this file — updated after every commit.**

---

## 3. What the project can do today

Text · screenshot · voice note/video · **pasted links** (Instagram Reels,
YouTube/Shorts, Facebook videos, fb.watch) · **Telegram bot** (built, not yet
live — needs a token). Verdicts cite only whitelisted sources, abstain honestly,
come back in the reader's own language with English underneath, and every report
carries its own measured bill (`report.usage`).

Measured economics: ~$0.12–0.26/claim · $0.279 for a whole 6-claim reel ·
~$0.03 for a repeat of a cached rumour · $0 for the entire demo/test surface.

---

## 4. THE TODO LIST

The authoritative copy lives in **PROJECT_PLAN.md §11**. Summary:

**Needs Vinayak, not code:**
1. AFP Fact Check whitelist — add `factcheck.afp.com` or not?
2. Spend caps before going public (~$99/day ceiling today).
3. Judge the live Hindi translation quality (two real reports exist).
4. ~~Create the @BotFather token~~ **DONE** — validated, see §5 below.

**Cheap verifications pending:**
- **First live Telegram message** (needs you present; the bot is ready).
- Translation prompt fixes unverified (~$0.04 — the claims are cached).
- Facebook `/reel/<id>` URL form unprobed (free, needs one real link).

**Defect backlog:** PROJECT_PLAN §11 items 7–22 (17–22 were deferred by the
end-to-end review; item 17, a transcript cache for repeat links, is the
highest-value one).

---

## 5. WHERE THE LAST SESSION ENDED

**The end-to-end review is COMPLETE and every fix is committed and pushed.**
`main` is clean, 350 tests pass, working tree empty. Nothing is half-done.

The review ran 10 angles over everything since `0389647` (4 died to a session
limit; 6 reported). It found **11 defects, every one of them silent** — each
produced output that looked entirely plausible. All were fixed in seven
layered commits, each with tests, each pushed:

| Commit | What |
|---|---|
| `3477f0c` | 4 engine defects (POSIX language tags disabled translation; persisted reports kept a stale whitelist; the meter could double every bill; one translation per tag *spelling*) |
| `8f41dab` | 6 ways the bot could take money and give silence |
| `9220bf2` | Telegram flakiness + free token validation |
| `1a1f4c1` | one definition of "which platforms work", not four |
| `86198da` | page dead-ends; concurrent ASR chunks |
| `675961b`, this one | docs |

**The single most important thing for you to know:** your `TELEGRAM_BOT_TOKEN`
was found in `.env` and **validates as `@Information_Verifier_bot`**. I did
**not** start the bot — anyone messaging it spends real money and nobody was
awake to supervise. Re-check for $0 any time:

```powershell
.\.venv\Scripts\python.exe scripts\telegram_bot.py --check-token
```

To go live (this is the whole remaining step for Phase 3):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app     # terminal 1
.\.venv\Scripts\python.exe scripts\telegram_bot.py     # terminal 2
```
…then message the bot. Watch it: Telegram was measured timing out twice in
three calls from this network, so the retry logic gets its first real test.

**Deferred deliberately** (recorded as §11 items 17–22, best value first):
no transcript cache for repeat links (re-buys ASR on every forward of the
same reel), three-way duplication that has drifted once already, two SSRF
host parsers, ASR metering at the wrong seam, a shared thread pool, and the
bot handling messages one at a time.
