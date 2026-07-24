# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-07-24**.

---

## 1. Mission

Give any Indian with a phone a fast, trustworthy way to check whether a message,
image, or video is true — with the real answer, in their own language, backed by
sources they can click.

The people most exposed to misinformation (rural / semi-urban, reading in Hindi,
Marathi, Tamil, Bengali…) are the least served by existing fact-check sites, which
are English-first and desktop-shaped. We bring the check to where the rumour already
is: mobile, and ultimately WhatsApp.

## 2. Principles (these are enforced in code, not slogans)

- **Bounded trust.** The engine can only cite a curated whitelist of vetted sources.
  It cannot wander the open web. That restraint *is* the product.
- **Willing to abstain.** The `UNVERIFIED` rating exists so we never manufacture a
  confident answer on a novel claim. Absence of evidence ≠ falsehood.
- **Every verdict carries receipts.** No trusted source → no verdict.
- **Cheap at scale.** A claim cache makes cost per-*rumour*, not per-*user*.
- **Not an arbiter of all truth.** We check falsifiable factual claims against trusted
  sources — not opinions, not politics, not the open web.

## 3. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| Reasoning / vision / extraction / adjudication | Claude **Opus 4.8** (`claude-opus-4-8`) |
| Language detect + translation + **retrieval** | Claude **Haiku 4.5** (`claude-haiku-4-5`) |
| Retrieval | Native `web_search_20260209` (allowed_domains) + Google Fact Check API |
| OCR | Opus 4.8 vision (no Tesseract) |
| ASR (Phase 2) | Sarvam AI (Indic languages) — adapter written, not wired |
| Storage | SQLite (Phase 1) → Postgres + pgvector (Phase 2) |
| Async | FastAPI BackgroundTasks (Phase 1) → ARQ/Redis (Phase 2) |
| Frontend (Phase 3) | Next.js PWA + WhatsApp Cloud API |

**Every LLM boundary returns a validated Pydantic object** via `messages.parse`.

## 4. Pipeline

```
normalize (Haiku)  ->  extract claims (Opus)  ->  per claim, in parallel:
    cache gate  ->  retrieve (Haiku: web_search whitelist + Fact Check API)
             ->  adjudicate (Opus, adaptive thinking)
->  aggregate  ->  persist  ->  Truth Report (rating + confidence + correction + citations)
```

## 5. Directory map

```
app/
  main.py            FastAPI app + lifespan (init_db)
  config.py          settings + model IDs + max_search_uses
  trusted_sources.py SEARCH_DOMAINS (crawlable) + FACTCHECK_ONLY_DOMAINS (blocked)
  api/               routes + wire DTOs
  models/            Pydantic contracts: Claim, Verdict, Evidence, TruthReport
  engine/            normalize, extract, retrieve, adjudicate, aggregate, pipeline, prompts
  providers/         llm (Anthropic), vision (OCR), factcheck (Google), asr (Sarvam)
  store/             SQLite db + repository (reports + claim cache)
scripts/
  demo_offline.py    FREE full-pipeline demo with simulated LLM stages
  smoke_test.py      REAL one-claim end-to-end test (costs a few cents)
  render.py          console Truth Report formatter
```

## 6. Roadmap & status

### Phase 1 — Core engine (text + image)  ✅ DONE & verified live
- [x] FastAPI skeleton, SQLite store, repository, claim cache (exact-match)
- [x] Pydantic contracts for every stage
- [x] normalize / extract / retrieve / adjudicate / aggregate / pipeline
- [x] Native web search with trusted-domain whitelist
- [x] Google Fact Check API integration (code done + unit-tested; needs free key to run)
- [x] Image OCR via Opus vision (`/verify/image`)
- [x] REST API: `/verify/text`, `/verify/image`, `/reports/{id}`, `/health`
- [x] Verified end-to-end on a real Hindi 5G/COVID claim → FALSE 95% with 4 citations
- [ ] Set `GOOGLE_FACTCHECK_API_KEY` to activate the Google layer live (user action)

### Phase 2 — Production hardening + media
- [ ] Postgres + pgvector; migrate repository off SQLite
- [ ] **Semantic** claim cache (embed claims → similarity search). Needs an embedding
      model — Anthropic has no embeddings endpoint (candidate: Voyage).
- [ ] ARQ/Redis queue replacing BackgroundTasks
- [ ] Audio/video: wire `providers/asr.py` (Sarvam) into a `/verify/media` route;
      keyframe extraction (needs `ffmpeg`, not installed)
- [ ] Back-translate the Truth Report summary into the user's input language
- [ ] Widen sources: route Reuters/PTI/The Hindu/India Today/Vishvas through the
      Fact Check API (they block the Anthropic crawler — see Decisions log)

### Phase 3 — Delivery (the actual goal)
- [ ] WhatsApp Business Cloud API webhook (forward a message → get a sourced reply)
- [ ] Lightweight mobile-first PWA (Next.js) — needs Node.js installed
- [ ] Localization UI (Hindi, Marathi, Tamil, Bengali…)

## 7. Decisions & findings log

- **2026-07-24 — Retrieval moved Opus → Haiku (cost).** Retrieval reads full page text
  (token-heavy) but is only summarizing evidence; the judgment is in adjudicate() on
  Opus. This is the biggest cost lever. Cut per-check cost ~3–4×.
- **2026-07-24 — web_search on Haiku needs `allowed_callers=["direct"]`.** Haiku 4.5
  doesn't support programmatic tool calling, so web_search 400s without that flag. Added
  it to the tool config so retrieval keeps the cheap model AND web search. Verified: a
  Hindi UNESCO-anthem claim returned FALSE 98% citing both web-search and Google
  Fact Check sources (incl. crawler-blocked India Today & Vishvas News via Google).
- **2026-07-24 — web_search `allowed_domains` is ALL-OR-NOTHING.** If any listed domain
  blocks Anthropic's crawler, the whole request 400s. Reuters, PTI, The Hindu, India
  Today, and Vishvas News block the crawler → moved to FACTCHECK_ONLY_DOMAINS. Only
  altnews.in, boomlive.in, factly.in, factcheck.thequint.com, pib.gov.in are searchable.
- **2026-07-24 — Pipeline no longer swallows claim failures.** A failed claim now
  surfaces as `UNVERIFIED` with the reason instead of vanishing as "no claims found".
- **Rating scale includes UNVERIFIED** so the engine can abstain.
- **Semantic cache deferred to Phase 2** — no embeddings endpoint on Anthropic; Phase 1
  uses exact normalized-text match.

## 8. Cost model (approximate, USD)

- Opus 4.8: $5 / $25 per million tokens (in / out). Haiku 4.5: $1 / $5.
- Web search: ~$0.01 per search (separate fee); capped at `max_search_uses` (4) per claim.
- **Per real single-claim check after the Haiku retrieval fix: ~$0.05–0.12.**
- The offline demo (`scripts/demo_offline.py`) is always free.

## 9. Environment notes (this machine)

- **Repository:** https://github.com/VinayakMokashi/Information_Verifier (private).
  Commit + push after each meaningful change so any session sees the latest state.
- Python 3.12 ✅, git ✅, gh CLI ✅ (authed as VinayakMokashi).
- **Node.js and Docker NOT installed** — needed for the Phase 3 PWA and Phase 2
  Postgres/Redis containers respectively.
- Secrets live only in `.env` (git-ignored). `.env.example` stays blank.

## 10. How to run

See [GETTING_STARTED.md](GETTING_STARTED.md). Quick reference:
- Free demo: `.venv\Scripts\python.exe scripts\demo_offline.py`
- Real check: `.venv\Scripts\python.exe scripts\smoke_test.py "your claim"`
- API server: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` → `/docs`
