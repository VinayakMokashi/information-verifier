# Working on Information Verifier

A general-purpose claim verifier: paste a message, a screenshot, a voice note
or a reel link, and get back one prose answer — the way Claude would answer if
you pasted the thing into a chat — with a confidence % and clickable sources.
Read **[HANDOFF.md](HANDOFF.md)** first — the whole project in one file,
with the startup prompt and where the last session stopped. Then
**[PROJECT_PLAN.md](PROJECT_PLAN.md)** for depth: §0 status, §7 the
decisions log (the "why", including the pivot), §11 what's open. This file
is how to work here.

## Money rules (the user is cost-conscious — this matters most)

- **Never run a paid test without asking.** MEASURED 2026-09-22 (Sonnet 5):
  **$0.05–0.06** for a single pass, **$0.15** when the open-web pass also runs,
  **$0.08** for a real 70 s reel (+ ₹0.58 ASR, now paid once per video). The
  models said 2–3× more. Every answer carries its own bill in `answer.usage`,
  and **`http://127.0.0.1:8000/dashboard`** (this machine only) shows the total.
- **The deployment is capped at 5 checks a day** (Vinayak, 2026-09-22: 2 a
  day "just to be safe … we can increase it later"; raised to 5 on
  2026-09-29 for quality testing). Persisted in SQLite, India's day,
  shared by the web page and the Telegram bot; a test pins the default.
  Operator scripts (`smoke_test.py`, `ab_models.py`) do not go through it —
  they are still paid, so still ask.
- **Prefer the free path, and there is almost always a free path:**

  | Command | Cost | Proves |
  |---|---|---|
  | `.venv\Scripts\python.exe -m pytest tests -q` | $0 | everything; every paid seam is faked |
  | `.venv\Scripts\python.exe scripts\serve_demo.py` | $0 | the real chat UI + real SSE, simulated Claude |
  | `.venv\Scripts\python.exe scripts\demo_offline.py` | $0 | engine plumbing + cache, in the console |
  | `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"` | $0 | which publishers we keep/drop |
  | `.venv\Scripts\python.exe scripts\link_probe.py <url>` | $0 | does a reel resolve; has it captions |
  | `.venv\Scripts\python.exe scripts\telegram_bot.py --check-token` | $0 | the bot token still works |
  | `.venv\Scripts\python.exe scripts\crawl_probe.py` | $0–0.002 | the API accepts every search domain (run after editing the whitelist) |
  | `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg` | ~paise | one real transcription |
  | `.venv\Scripts\python.exe scripts\smoke_test.py "claim"` | ~cents | one real check, with its bill |
  | `.venv\Scripts\python.exe scripts\link_smoke.py <url>` | ~cents | a real reel, end to end, with its bill |
  | `.venv\Scripts\python.exe scripts\ab_models.py <url or claim>` | ~$0.40 | two models on one input, each billed |

- When adding a paid provider, add it to `scripts/fake_stages.py`
  (`apply_fake_stages`) **and** neutralize its credential where it is actually
  read. Blanking `settings` is not enough for clients built at import time — see
  the Anthropic case in §7. `tests/test_demo_is_free.py` pins this.

## Environment

Windows, PowerShell. Always use the venv Python explicitly:
`.\.venv\Scripts\python.exe …` — a bare `python` will not have the deps.

Installed: Python 3.12, git, gh, winget, ffmpeg, cloudflared, Chrome and Edge
(headless screenshots — see "How we work").
**Not** installed and not needed: Node.js, Docker, psql, Redis.
No longer used (the pivot removed them): sqlite-vec, sentence-transformers,
EmbeddingGemma. Startup no longer imports torch.

Secrets live only in `.env` (git-ignored): `ANTHROPIC_API_KEY`,
`GOOGLE_FACTCHECK_API_KEY`, `SARVAM_API_KEY`, `HF_TOKEN`, `DB_PATH`,
`TELEGRAM_BOT_TOKEN`.

Run the real server with **one worker**: the stream registry and the rate
limiter are both in-memory.

## Invariants — do not break these without a decision recorded in §7

1. **Tier is evidence, not assertion — the model can lower it, never raise
   it.** A "fact-checked" label needs a trusted URL the API itself returned
   (`trusted_domain_of()`, fail-closed on anything a browser might parse
   differently). The model's `trusted="no"` DOES lower it — measured: BOOM pages
   about a *different* hoax labelled a Nagpur answer "fact-checkers" under a
   heading saying none had covered it. Its `used=` list narrows the sources to
   what the answer rests on and can never add one. After the fact a label only
   goes down: relabelling on serve re-tiers each source, but never promotes a
   stored answer over prose that says no fact-checker covered it. **Only the
   whitelist pass can earn the label.** Pass 2 is *told* to say that no vetted
   source covered the claim, so nothing it finds may relabel the answer — a
   trusted page it turns up is shown as trusted, and the answer stays "general
   web" under its 75 cap. Measured twice: an unrelated who.int result labelled
   a Times of India answer at 90%, and then — after that fix — a BOOM page
   pass 1 had explicitly disowned did the same.
2. **The engine may say it could not verify.** Tier `none` is a real answer.
   Never force a decisive-looking call out of nothing.
3. **Prose is never a receipt.** The model can write a convincing fake URL.
   Links, confidence and the skimmable summary come only from structured
   fields: the summary is pulled OUT of the prose by the filter, never
   scraped back out of it, so it is shown once and in a box of its own. The
   model's markdown renders as text on every surface — no links, no images,
   no HTML. (A markdown image would leak the reader's forwarded message to a
   third party on render.)
   Telegram is the special case: it auto-links bare URLs in message text, so
   URLs are stripped from the prose there specifically. The console renderer
   (`scripts/render.py`) deliberately prints the prose verbatim — it is a
   developer surface, and hiding what the model actually wrote would defeat
   the point of running a paid check to inspect it.
4. **Machine-read text is shown back to the user.** ASR/OCR output goes in
   `answer.source_text` and is displayed — a mis-hear must never silently
   become a confident answer about a different claim.
5. **Every paid call is bounded before it is made.** Size/duration/input caps
   and the search budget come before any spend. The daily cap is taken by one
   conditional UPSERT in SQLite (the database refuses the slot past the cap),
   survives restarts, and FAILS CLOSED if it cannot be recorded. The search
   budget is enforced across `pause_turn` continuations, not per request.
   Concurrency never gets to bypass this: the bot's per-chat lock covers the
   decide-and-submit step, so one chat cannot pay twice.
6. **The caches degrade to doing the work, and their entries expire.** A
   cache failure must never discard an answer already paid for, or surface as
   an empty result. The answer cache is exact-match only, so its TTL is not
   optional — "no fact-checker has covered this" is wrong the day BOOM
   publishes. The transcript cache (by platform video id) never stores a
   failed transcription, or one that heard nothing beyond the caption.
7. **The sentinel is never user-visible and never user-plantable.** It trails
   the answer (a header cannot survive streaming — §4). `MarkerFilter` removes
   EVERY `<verdict…>` tag whether or not it parses (any case, any attribute
   order, any length), holds back a possible opener, and drops a tag cut off
   mid-stream; the page, the bot and the console strip any tag shape again.
   `as_prompt_data()` turns every `<`/`>` in user input into `‹`/`›` so it
   cannot be forged.
8. **Streaming never forks the truth.** The persisted `Answer` is canonical;
   every surface re-renders from it when the stream ends. A reload after the
   job finished must behave exactly like watching it live.
9. **Every paid seam has a fake, and the fake is pinned.** A seam without one
   is a seam that will spend money in "free" mode.
10. **Messages are forgotten; costs are not.** Answers are deleted after
   `answer_retention_days` (30). The spend ledger keeps what each check cost
   and NEVER what anyone sent — pinned against the table's schema.

## How we work

- **Verify, don't assume.** Several "obviously correct" fixes here were wrong and
  only measurement caught it (§7 has four rounds of this). Reproduce a problem
  with a script, fix it, then re-measure to prove the fix. Fixes deserve the same
  adversarial review as features.
- **A green suite is not a working product.** Measured twice: the Telegram bot
  was broken for a whole commit while its tests passed on hand-built dicts, and
  four scripts could not even import while nothing tested that they could.
  Prefer a test that would have caught the bug over one that describes the fix,
  and check it *does* fail against the broken version.
- **Layered commits**: one concern per commit, each with tests passing. Commit
  messages explain *why*, including what was measured. Push after each meaningful
  change so the next session sees the latest state.
- **Keep PROJECT_PLAN.md current** — it is the handoff. Add a §7 entry for any
  non-obvious decision or surprising measurement.
- Tests are free and fast; add one for every fix.
- Comments explain constraints and hard-won facts, not what the line does.
- Scripted doc edits must assert their markers. A `.replace()` that silently
  matched nothing left §11 stale for a whole session.
- **Check pytest's own exit code before committing** — never a piped `| tail`
  (it exits 0 whatever pytest did; a commit went in with a failing test).
- **Shell heredocs collapse doubled backslashes.** Write anything containing
  `\` (regexes, Windows paths, `\n` in source) with the Edit/Write tools. A test
  now fails any file with an invalid escape.
- **A UI is done when it has been looked at.** Headless Chrome renders it
  (`chrome --headless=new --screenshot=...`); phone width needs a 390 px
  iframe, because desktop Chrome will not size a window below ~500 px. The
  dashboard's four real defects were found only this way.
- **Concurrency tests need fakes that suspend** (`await asyncio.sleep(0)`), or
  a race cannot happen and the test passes with the guard removed — measured.
  And wait on conditions, not durations: asyncio's clock here steps 15–16 ms.
- **A test that hangs on the bug is not a test that fails.** Make the broken
  version FAIL: stubs that finish work submitted late, and a thread with a
  join timeout around anything that could spin synchronously (measured:
  `Dispatcher.drain()` spun where no asyncio timeout could fire).
- **Review the fix, not just the bug.** On 2026-09-22 a third of the defects
  came from the fixes for earlier defects, and two more were found only by
  running a reviewer's randomized interleaving search against the FIXED bot
  (`scratchpad/fixrev_money/bot_explorer_real*.py`, 2,000 seeds each). A fix
  that addresses the mechanism a finding named, rather than the rule behind
  it, leaves the hole open.
- **Some things only reality shows.** The server could not start on the one
  real database; two whitelisted sites blocked the crawler; the search tool
  made English claims come back in Hinglish. Free probes (`crawl_probe.py`,
  `link_probe.py`) and one cheap real run find what fakes cannot.

## Shape of the code

`app/api/` routes (text / image / media / **link** — a pasted Reel, Shorts or
Facebook URL) → `app/engine/job.py` (`run_check`: cache → engine → persist →
spend ledger) → `app/engine/chat.py` (pass 1 whitelist, pass 2 open web if
nothing vetted covered it) → `app/store/` persists. Providers
(`app/providers/`) wrap every external service. `app/api/stream.py` carries
the live SSE preview; `app/api/dashboard.py` the local-only spending page;
`app/hosts.py` is the ONE place a URL's host is read (both the trust label and
the link fetcher depend on it).

The REST contract is deliberately surface-agnostic: submit → `{job_id}` →
poll `/reports/{job_id}`, with an optional `/stream/{job_id}` for live text.
The web page, the Telegram bot, and any future WhatsApp bot use the same calls.
