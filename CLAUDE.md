# Working on Information Verifier

A multi-modal fact-checking engine for misinformation in India. Read
**[PROJECT_PLAN.md](PROJECT_PLAN.md)** first — §0 is the current status, §7 is the
decisions log (the "why"), §11 is what's open. This file is how to work here.

## Money rules (the user is cost-conscious — this matters most)

- **Never run a paid test without asking.** MEASURED: ~$0.12–0.26 per claim,
  and $0.279 for a whole 6-claim reel. A report can hold 8 claims. Sarvam ASR
  is ~₹0.50/min. Every report carries its own bill in `report.usage`.
- **Prefer the free path, and there is almost always a free path:**

  | Command | Cost | Proves |
  |---|---|---|
  | `.venv\Scripts\python.exe -m pytest tests -q` | $0 | everything; every paid seam is faked |
  | `.venv\Scripts\python.exe scripts\demo_offline.py` | $0 | pipeline + cache, console |
  | `.venv\Scripts\python.exe scripts\serve_demo.py` | $0 | the real web UI, simulated verdicts |
  | `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"` | $0 | which publishers we keep/drop |
  | `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg` | ~paise | one real transcription |
  | `.venv\Scripts\python.exe scripts\smoke_test.py "claim"` | ~cents | one real fact-check |

- When adding a paid provider, add it to `scripts/fake_stages.py`
  (`apply_fake_stages`) **and** neutralize its credential where it is actually
  read. Blanking `settings` is not enough for clients built at import time — see
  the Anthropic case in §7. `tests/test_demo_is_free.py` pins this.

## Environment

Windows, PowerShell. Always use the venv Python explicitly:
`.\.venv\Scripts\python.exe …` — a bare `python` will not have the deps.

Installed: Python 3.12, git, gh, winget, ffmpeg, cloudflared, sqlite-vec,
sentence-transformers, EmbeddingGemma (cached).
**Not** installed and not needed: Node.js, Docker, psql, Redis.

Secrets live only in `.env` (git-ignored): `ANTHROPIC_API_KEY`,
`GOOGLE_FACTCHECK_API_KEY`, `SARVAM_API_KEY`, `HF_TOKEN`, `DB_PATH`.

## Invariants — do not break these without a decision recorded in §7

1. **Bounded trust.** A verdict may only cite `TRUSTED_DOMAINS`. Both retrieval
   paths (web search *and* Google Fact Check) are filtered. `trusted_domain_of()`
   fails closed on anything a browser might parse differently than Python.
2. **The engine may abstain.** `UNVERIFIED` is a real answer. Never force a
   true/false call to look decisive.
3. **A cached verdict is never served on embedding distance alone.** Claims
   differing by one token can embed *closer* than genuine paraphrases (measured).
   The vector index nominates; a Haiku check confirms; aliases are stored
   unindexed so hits cannot chain away from the adjudicated claim.
4. **Machine-read text is shown back to the user.** ASR/OCR output goes in
   `report.source_text` and is displayed — a mis-hear must never silently become
   a confident verdict on a different claim.
5. **Caps are enforced before spending**, not after. Size/duration/claim-count
   checks come before any paid call, and the rate limiter reserves atomically.
6. **A cache failure degrades to doing the real work.** It must never discard a
   verdict already paid for, or surface as "no claims found".
7. **Back-translation is additive.** The adjudicated English is canonical and
   lives on; the reader's language goes in `report.localized`, index-aligned
   with `claim_verdicts` (`None` = show the English for that one, never shift).
   Ratings and citations have no translated form and must not grow one. Never
   translate a `Verdict` before caching it — the first Hindi reader would
   poison that rumour for every Tamil reader behind them.

## How we work

- **Verify, don't assume.** Several "obviously correct" fixes here were wrong and
  only measurement caught it (§7 has three rounds of this). Reproduce a problem
  with a script, fix it, then re-measure to prove the fix. Fixes deserve the same
  adversarial review as features.
- **Layered commits**: one concern per commit, each with tests passing. Commit
  messages explain *why*, including what was measured. Push after each meaningful
  change so the next session sees the latest state.
- **Keep PROJECT_PLAN.md current** — it is the handoff. Add a §7 entry for any
  non-obvious decision or surprising measurement.
- Tests are free and fast; add one for every fix. Prefer a test that would have
  caught the bug over a test that describes the fix.
- Comments explain constraints and hard-won facts, not what the line does.

## Shape of the code

`app/api/` routes (text / image / media / **link** — a pasted Reel or Shorts
URL) → `app/engine/pipeline.py` orchestrates →
`normalize → extract → (cache | retrieve → adjudicate) → aggregate → translate` →
`app/store/` persists. Providers (`app/providers/`) wrap every external service.
The REST contract is deliberately surface-agnostic: submit → `{job_id}` → poll
`/reports/{job_id}`. The web page, and any future WhatsApp/Telegram bot, use the
exact same two calls.
