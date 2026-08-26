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
  (a) Go live with the Telegram bot — I'll bring the @BotFather token.
  (b) Burn down the §11 defect backlog.
  (c) Verify the pending cheap items (translation prompt fixes ~$0.04;
      I'll paste a real Facebook reel link for the free probe).
  (d) Prepare for real public sharing: my cap decisions + observability
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
4. **Create the @BotFather token** → `TELEGRAM_BOT_TOKEN` in `.env`. This is
   the only thing between the Telegram bot and its first live message.

**Cheap verifications pending:**
- Translation prompt fixes unverified (~$0.04 — the claims are cached).
- Facebook `/reel/<id>` URL form unprobed (free, needs one real link).
- Telegram bot has never touched live Telegram (blocked on #4).

**Defect backlog:** PROJECT_PLAN §11, plus anything left over from the
review below.

---

## 5. IN PROGRESS / NEXT (updated after every commit)

_Initialised before the review fixes began. See `git log --oneline` for the
authoritative record of what actually landed._
