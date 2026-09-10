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
2. CLAUDE.md        — how we work here: money rules, the 9 invariants, conventions.
3. PROJECT_PLAN.md  — the source of truth. §0 status, §0a the reel-link feature
   (it was lost from the plan once — never let that happen again), §7 decisions
   log INCLUDING "The pivot" at the end (skim before changing anything),
   §11 "THE TODO LIST" = open items.
Your memory also has entries for this project.

Verify the state first (free, ~35s):
  .\.venv\Scripts\python.exe -m pytest tests -q     # expect 390 passing

BIG CONTEXT: the app was rebuilt in Sept 2026. There is no more Truth Report,
no rating enum, no per-claim verdicts, no semantic cache, no embeddings. One
streaming Claude Sonnet 5 call (two at most: whitelist first, then open web if
nothing vetted covered it) writes one prose answer. If you find code or docs
still talking about TruthReport / claim_verdicts / sqlite-vec as CURRENT state,
that's a bug — outside §6 and §7, which are history and should stay.

I'm cost-conscious — DON'T run paid tests without asking. The new engine has
NEVER had a paid run; §8's numbers for it are modelled (~$0.16 single-pass,
~$0.26 two-pass). The one measured number this project has is $0.279 for a
whole 6-claim reel under the OLD engine. Free paths for nearly everything are
in CLAUDE.md's table (pytest, serve_demo, demo_offline, link_probe,
factcheck_probe, telegram_bot --check-token).

Work the way we have been: systematic layered commits PUSHED AFTER EACH ONE
(so a session break never loses work), adversarial review of the diff INCLUDING
of the fixes themselves (that has caught real bugs every single round),
measure rather than assume, and keep PROJECT_PLAN.md + NEXT_SESSION.md current.
Two hard-won process rules: (a) when editing docs by script, assert every
replace matched — a silent no-op left §11 stale once; (b) a green suite is not
a working product — twice now, tests passed while the thing was broken, so
check a new test actually FAILS against the broken version.

What I want to work on next: <PICK ONE, or tell me your own>
  (a) THE FIRST PAID RUN of the new engine. Everything is built and this is the
      thing that's been waiting. Two checks, under a dollar total: one
      known-debunked claim (should be single-pass) and one fresh rumour (should
      escalate to the open-web pass). Then put the MEASURED numbers into §8 and
      delete the modelled ones.
  (b) GO LIVE with the Telegram bot. Token is in .env and validated
      (@Information_Verifier_bot); it has never been started. I'll be at the
      keyboard — walk me through it and we fix what the first real messages break.
  (c) §11 item 5: a transcript cache for links, so the same reel forwarded by
      many people is bought once, not once per person. Best-value code item.
  (d) A/B Sonnet 5 vs Opus 5 on one real reel (needs (a) first for a baseline).
  (e) Burn down the rest of the §11 backlog (items 7–16).
  (f) Prepare for real public sharing: my cap decisions + observability
      + data pruning, then a supervised share_demo.ps1 session.
```

---

## 2. What the project can do today

Text · screenshot · voice note/video · **pasted links** (Instagram Reels,
YouTube/Shorts, Facebook videos, fb.watch) · **Telegram bot** (built, never yet
live — needs starting, the token works).

One prose answer per submission, streamed word by word onto a chat page, in the
language the message arrived in. Confidence % with its basis. Sources grouped
by tier, and a clearly-labelled "general web" section when no fact-checker has
covered the claim. General-purpose: health, science, history, politics — 58
trusted domains including WHO, CDC, NIH, PubMed, NASA, NOAA, Cochrane, Snopes,
Full Fact, and the Indian fact-checkers it started with.

Economics: **modelled** ~$0.16 single-pass / ~$0.26 two-pass; **$0** for an
exact re-forward inside the cache TTL; **$0** for the entire demo/test surface.
The one measured figure ($0.279 for a 6-claim reel) predates the pivot.

---

## 3. THE TODO LIST

The authoritative copy lives in **PROJECT_PLAN.md §11**. Summary:

**Needs Vinayak, not code:**
1. **The first paid run of the new engine** — the next thing that should happen.
2. AFP Fact Check whitelist — add `factcheck.afp.com` or not?
3. Spend caps before going public (~$26/day modelled now, down from ~$99–211,
   because a submission can no longer fan out into eight paid claims).
4. **First live Telegram message** (needs you present; the bot is ready).

**Best-value code items:** a transcript cache for repeat links (§11 item 5),
then the Sonnet-vs-Opus A/B (item 6), then pruning stored answers (item 7).

---

## 4. WHERE THE LAST SESSION ENDED

**Session of 2026-09-10/11 — the pivot is COMPLETE, committed and pushed.**
`main` is clean, **390 tests pass**, working tree empty. Nothing is half-done.

Vinayak asked for the app to answer "like a simple claude chat" and, mid-build,
to make it general-purpose rather than India-political. Both are done.

| Commit | What |
|---|---|
| `d664e0c` | the app runs on the chat engine; the old pipeline is deleted |
| `2602338` | the page becomes a streaming chat UI |
| `436fa16` | the Telegram bot spoke a shape that no longer existed |
| `10b3652` | four free-path scripts that would have died on line 1 |
| this one | docs: CLAUDE.md invariants, PROJECT_PLAN §0–§5/§7/§8/§11, README, this file |

**Two findings worth carrying forward** (both in §7 "The pivot"):

- **A green suite is not a working product.** The Telegram bot was broken for a
  whole commit while its tests passed — they fed it hand-built Truth Report
  dicts. And four scripts couldn't import at all, because no test imported a
  script. `tests/test_scripts_import.py` now closes the second gap, and it was
  checked against the broken commit to confirm it actually fails there.
- **A confident badge explaining nothing.** A 15,000-character single paragraph
  fit in no Telegram budget, so the whole answer was dropped and the reply
  became "95% confident" plus a link and no explanation. Blocks must be
  droppable, therefore bounded.

**Verified free this session:** the demo server streams live over a real socket
(word-by-word deltas, sequence ids); a late join with `Last-Event-ID: 60`
resumes at 61 instead of restarting; an identical resubmit returns
`cached=True` at $0.0000; image and link routes both show their machine-read
text back; Devanagari, Tamil and Bengali all survive a **cp1252** redirected
stdout (the case that hides from a UTF-8 shell); and the bot token still
validates.

**The one thing that has NOT happened: a paid run of the new engine.** Vinayak
deferred it deliberately — "we will do the paid run once everything is built."
It is built.
