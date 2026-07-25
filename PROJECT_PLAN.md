# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-07-25**.

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
  factcheck_probe.py FREE Google-API-only probe: shows KEEP/DROP per publisher
  render.py          console Truth Report formatter
tests/               pytest unit tests (pure functions only — always free)
```

## 6. Roadmap & status

### Phase 1 — Core engine (text + image)  ✅ DONE & verified live
- [x] FastAPI skeleton, SQLite store, repository, claim cache (exact-match)
- [x] Pydantic contracts for every stage
- [x] normalize / extract / retrieve / adjudicate / aggregate / pipeline
- [x] Native web search with trusted-domain whitelist
- [x] Google Fact Check API integration — **live & verified** (`GOOGLE_FACTCHECK_API_KEY`
      set; reaches crawler-blocked sources like India Today & Vishvas News via Google)
- [x] Image OCR via Opus vision (`/verify/image`)
- [x] REST API: `/verify/text`, `/verify/image`, `/reports/{id}`, `/health`
- [x] Verified end-to-end: Hindi 5G/COVID → FALSE 95%; Hindi UNESCO-anthem → FALSE 98%
      with web-search + Google Fact Check citations combined
- [x] **Trust-filter Fact Check API results** (2026-07-25): Google returns ClaimReview
      from ANY publisher; results are now filtered to `TRUSTED_DOMAINS` before reaching
      the adjudicator, with dropped hosts logged. Unit tests (`tests/`, free) + free
      curation probe (`scripts/factcheck_probe.py`). Verified live at $0.

### Phase 2 — Production hardening + media  (stack decided 2026-07-25, see §11)
- [ ] **Semantic claim cache — decided stack:** `sqlite-vec` 0.1.9 (pip, prebuilt
      Windows wheel; brute-force KNN is milliseconds at our scale) + **local
      EmbeddingGemma-300m** via sentence-transformers on CPU (100+ languages incl.
      Hindi/Marathi/Tamil/Bengali; truncate to 256 dims). $0 recurring, offline.
      Rule: store embedding model name + dims in the schema; never mix models.
- [ ] Postgres + pgvector **deferred to deployment**: Neon free tier (pgvector
      included, auto-wakes from scale-to-zero) beats Supabase (7-day hard pause)
      and native Windows install (Visual Studio source compile). Keep the cache
      behind the repository interface so the swap is SQL-only.
- [ ] Audio/video `/verify/media`: ffmpeg **already installed** (Gyan 8.1.2 via
      winget — verified). Sarvam **Saaras v3** (`saaras:v3`; Saarika is legacy —
      adapter updated). Sync API ≤30 s/request; chunk longer audio with
      `ffmpeg -f segment`; WhatsApp OGG/Opus accepted directly; `mode=translate`
      can emit English straight into the pipeline. Needs SARVAM_API_KEY
      (₹100 signup credits ≈ 3.3 h of audio at ₹30/hr).
- [ ] ARQ/Redis queue replacing BackgroundTasks — needs Redis (Docker or Memurai);
      lowest priority while traffic is one user at a time
- [ ] Back-translate the Truth Report summary into the user's input language
- [x] Widen sources: Reuters/PTI/The Hindu/India Today/Vishvas (+ Quint, Fact
      Crescendo, Full Fact, Snopes) reach the engine via the trust-filtered
      Google Fact Check path (2026-07-25)

### Phase 3 — Delivery (the actual goal)
- [ ] **Fastest demo path ($0, researched):** mobile-first static page served by
      FastAPI `StaticFiles` (no Node needed — polling fits the existing job API)
      + `cloudflared` quick tunnel (account-free, `winget install -e --id
      Cloudflare.cloudflared`) → sharable https link. Avoid ngrok (account
      required, 1 GB/20k-req monthly cap, interstitial page for browsers).
- [ ] WhatsApp Cloud API: free **test number** covers exactly 5 verified
      recipients; user-initiated service replies are free (per-message billing
      since 2025-07). A real number needs Meta Business verification (2–7 days).
- [ ] Telegram bot alternative: free, and long polling needs **no tunnel at
      all** — lowest-friction chat demo; friends may need to install Telegram.
- [ ] Lightweight PWA (Next.js) — only if the static page outgrows itself
      (needs Node.js)
- [ ] Localization UI (Hindi, Marathi, Tamil, Bengali…)

## 7. Decisions & findings log

- **2026-07-25 — Fact Check API results are now trust-filtered.** Google's Fact Check
  API indexes ClaimReview from any publisher worldwide (live probe saw Full Fact,
  Snopes, Fact Crescendo, The Quint). Bounded trust was only enforced on the web-search
  path; now `trusted_domain_of()` (app/trusted_sources.py) gates the Fact Check path
  too. Matching is exact-host or dot-boundary subdomain — lookalikes like
  `notaltnews.in` or `altnews.in.evil.com` fail. Drops are logged, never silent.
- **2026-07-25 — Trust matching is hardened against parser differentials.** An
  adversarial review found that Python's `urlparse` and browsers' WHATWG parser can
  disagree about where a URL's host ends (`https://evil.example\.altnews.in/` and
  `https://evil.com\@altnews.in/` both read as altnews.in to urlparse but navigate to
  the attacker's host in a browser), and that non-http(s) schemes (`javascript://`,
  `data://`) passed. `trusted_domain_of()` now requires http(s), rejects userinfo,
  and validates the hostname charset — anything a browser could read differently
  fails closed. All bypasses are pinned by unit tests (41 pass, free to run).
- **2026-07-25 — Whitelist widened (user-approved).** Added to FACTCHECK_ONLY_DOMAINS:
  `thequint.com` (their ClaimReview lives on www.thequint.com — the WebQoof section —
  not the factcheck. subdomain used for web search), `factcrescendo.com` (IFCN, India),
  `fullfact.org` (IFCN, UK), `snopes.com` (US). Verified live at $0: the 5G claim went
  from 2 kept / 8 dropped to 9 kept / 1 dropped. All four are crawler-UNTESTED — a paid
  smoke test is needed before promoting any to SEARCH_DOMAINS.
  **Remaining candidate:** `factcheck.afp.com` (AFP Fact Check, IFCN) is now the only
  live drop — awaiting user decision.
- **2026-07-25 — Phase 2/3 stack decided after a live 4-agent web-research sweep**
  (numbers checked against vendor docs; sources in §11). Semantic cache: sqlite-vec +
  local EmbeddingGemma-300m — **Voyage is no longer the embeddings candidate**
  (embedding volume is tiny, local is $0/offline; Gemini `gemini-embedding-001` on the
  existing Google key is the API fallback). Media: Sarvam **Saaras v3** — Saarika is
  legacy/deprecating, `providers/asr.py` updated `saarika:v2` → `saaras:v3` (docs-
  verified, not yet live-tested; needs a key). Demo delivery: FastAPI static page +
  cloudflared quick tunnel (ngrok free tier now capped + interstitial). Known
  uncertainties: Sarvam signup credits ₹100 per official docs (blogs claim ₹1,000 —
  trust the dashboard); Gemini free-tier embedding rate limits unpublished.
- **2026-07-25 — Whitelist-curation loop:** `scripts/factcheck_probe.py` (free, $0)
  shows every publisher Google returns for a query and whether we keep or drop it.
  Recurring DROPs of good IFCN-certified publishers are candidates for the whitelist.
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
- Python 3.12 ✅, git ✅, gh CLI ✅ (authed as VinayakMokashi), winget ✅.
- **ffmpeg ✅ installed** (Gyan.FFmpeg 8.1.2 via winget, on PATH) — the plan
  previously said it wasn't; corrected 2026-07-25 after a local check.
- **Node.js and Docker NOT installed** (also no psql, no redis-server) — but the
  decided Phase 2 stack (sqlite-vec + local embeddings) needs neither.
- Secrets live only in `.env` (git-ignored). `.env.example` stays blank.

## 10. How to run

See [GETTING_STARTED.md](GETTING_STARTED.md). Quick reference:
- Free demo: `.venv\Scripts\python.exe scripts\demo_offline.py`
- Free tests: `.venv\Scripts\python.exe -m pytest tests -q`
- Free source probe: `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"`
- Real check: `.venv\Scripts\python.exe scripts\smoke_test.py "your claim"`
- API server: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` → `/docs`

## 11. Phase 2/3 prep — your action checklist (researched 2026-07-25)

Everything below was verified on the live web on 2026-07-25 (key sources:
sqlite-vec GitHub/PyPI, neon.com/docs, docs.voyageai.com, ai.google.dev,
developers.googleblog.com (EmbeddingGemma), docs.sarvam.ai, developers.facebook.com,
developers.cloudflare.com, core.telegram.org). Prices/tiers drift — re-check before
relying on a number months from now.

**Semantic cache (option b) — nothing to sign up for:**
- [ ] `pip install sqlite-vec sentence-transformers` into the venv (~1.5–2 GB disk
      for CPU torch; pin sqlite-vec — it is pre-v1)
- [ ] Hugging Face account + accept the Gemma license on the
      `google/embeddinggemma-300m` model page (repo is gated), then `hf auth login`
      once — first model load downloads ~1.2 GB

**Audio/video (option c):**
- [ ] Sign up at https://dashboard.sarvam.ai, create an API key, note your real
      free-credit balance, put `SARVAM_API_KEY=` in `.env`
- [ ] Nothing else — ffmpeg is already installed and the adapter is updated

**Demo to friends (option d):**
- [ ] `winget install -e --id Cloudflare.cloudflared` (no account needed)
- [ ] Optional Telegram route: message @BotFather → `/newbot` → token into `.env`
- [ ] WhatsApp test-number route (when wanted): Meta developer account → app with
      WhatsApp product → add up to 5 friends' numbers (each confirms a code) →
      webhook = the cloudflared URL (re-paste it on every tunnel restart)

**Recommended build order:** (d)-lite static page first (pure code, $0, immediately
showable), then (b) semantic cache (pure code after the two installs, $0), then (c)
media (needs the Sarvam key), then WhatsApp/Telegram bots on top.
