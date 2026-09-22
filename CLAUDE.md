# Working on Information Verifier

A general-purpose claim verifier: paste a message, a screenshot, a voice note
or a reel link, and get back one prose answer — the way Claude would answer if
you pasted the thing into a chat — with a confidence % and clickable sources.
Read **[PROJECT_PLAN.md](PROJECT_PLAN.md)** first — §0 is the current status,
§7 is the decisions log (the "why", including the pivot), §11 is what's open.
This file is how to work here.

## Money rules (the user is cost-conscious — this matters most)

- **Never run a paid test without asking.** MODELLED: ~$0.16 for a single pass,
  ~$0.26 when the open-web pass also runs. The one time this project modelled a
  cost and then measured it, the model was 40% high — so the model is a
  starting point, not a fact. Sarvam ASR is ~₹0.50/min. Every answer carries
  its own bill in `answer.usage`.
- **Prefer the free path, and there is almost always a free path:**

  | Command | Cost | Proves |
  |---|---|---|
  | `.venv\Scripts\python.exe -m pytest tests -q` | $0 | everything; every paid seam is faked |
  | `.venv\Scripts\python.exe scripts\serve_demo.py` | $0 | the real chat UI + real SSE, simulated Claude |
  | `.venv\Scripts\python.exe scripts\demo_offline.py` | $0 | engine plumbing + cache, in the console |
  | `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"` | $0 | which publishers we keep/drop |
  | `.venv\Scripts\python.exe scripts\link_probe.py <url>` | $0 | does a reel resolve; has it captions |
  | `.venv\Scripts\python.exe scripts\telegram_bot.py --check-token` | $0 | the bot token still works |
  | `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg` | ~paise | one real transcription |
  | `.venv\Scripts\python.exe scripts\smoke_test.py "claim"` | ~cents | one real check, with its bill |
  | `.venv\Scripts\python.exe scripts\link_smoke.py <url>` | ~cents | a real reel, end to end, with its bill |

- When adding a paid provider, add it to `scripts/fake_stages.py`
  (`apply_fake_stages`) **and** neutralize its credential where it is actually
  read. Blanking `settings` is not enough for clients built at import time — see
  the Anthropic case in §7. `tests/test_demo_is_free.py` pins this.

## Environment

Windows, PowerShell. Always use the venv Python explicitly:
`.\.venv\Scripts\python.exe …` — a bare `python` will not have the deps.

Installed: Python 3.12, git, gh, winget, ffmpeg, cloudflared.
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
   stored answer over prose that says no fact-checker covered it.
2. **The engine may say it could not verify.** Tier `none` is a real answer.
   Never force a decisive-looking call out of nothing.
3. **Prose is never a receipt.** The model can write a convincing fake URL.
   Links and confidence come only from structured fields; its markdown renders
   as text on every surface — no links, no images, no HTML. (A markdown image
   would leak the reader's forwarded message to a third party on render.)
   Telegram is the special case: it auto-links bare URLs in message text, so
   URLs are stripped from the prose there specifically. The console renderer
   (`scripts/render.py`) deliberately prints the prose verbatim — it is a
   developer surface, and hiding what the model actually wrote would defeat
   the point of running a paid check to inspect it.
4. **Machine-read text is shown back to the user.** ASR/OCR output goes in
   `answer.source_text` and is displayed — a mis-hear must never silently
   become a confident answer about a different claim.
5. **Every paid call is bounded before it is made.** Size/duration/input caps
   and the search budget come before any spend, and the rate limiter reserves
   atomically. The budget is enforced across `pause_turn` continuations, not
   per request.
6. **The cache degrades to doing the work, and its entries expire.** A cache
   failure must never discard an answer already paid for, or surface as an
   empty result. The cache is exact-match only now, so the TTL is not optional
   — "no fact-checker has covered this" is wrong the day BOOM publishes.
7. **The sentinel is never user-visible and never user-plantable.** It trails
   the answer (a header cannot survive streaming — §4); `MarkerFilter` holds
   back a trailing `<` and strips it; `as_prompt_data()` turns every `<`/`>` in
   user input into `‹`/`›` so it cannot be forged.
8. **Streaming never forks the truth.** The persisted `Answer` is canonical;
   every surface re-renders from it when the stream ends. A reload after the
   job finished must behave exactly like watching it live.
9. **Every paid seam has a fake, and the fake is pinned.** A seam without one
   is a seam that will spend money in "free" mode.

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

## Shape of the code

`app/api/` routes (text / image / media / **link** — a pasted Reel, Shorts or
Facebook URL) → `app/engine/job.py` (`run_check`: cache → engine → persist) →
`app/engine/chat.py` (pass 1 whitelist, pass 2 open web if nothing vetted
covered it) → `app/store/` persists. Providers (`app/providers/`) wrap every
external service. `app/api/stream.py` carries the live SSE preview.

The REST contract is deliberately surface-agnostic: submit → `{job_id}` →
poll `/reports/{job_id}`, with an optional `/stream/{job_id}` for live text.
The web page, the Telegram bot, and any future WhatsApp bot use the same calls.
