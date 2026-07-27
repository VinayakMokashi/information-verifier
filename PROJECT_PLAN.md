# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-07-26**.

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
  main.py            FastAPI app + lifespan (init_db) + static mount at "/"
  config.py          settings + model IDs + cache/media knobs
  trusted_sources.py SEARCH_DOMAINS (crawlable) + FACTCHECK_ONLY_DOMAINS + trust matching
  api/               routes (text/image/media/reports) + wire DTOs
  models/            Pydantic contracts: Claim, Verdict, Evidence, TruthReport
  engine/            normalize, extract, retrieve, adjudicate, equivalence,
                     aggregate, pipeline, prompts
  providers/         llm (Anthropic), vision (OCR), factcheck (Google),
                     asr (Sarvam Saaras v3), embeddings (EmbeddingGemma),
                     media (ffmpeg helpers)
  store/             SQLite + sqlite-vec db, repository (reports + 2-tier claim cache)
static/
  index.html         self-contained mobile demo page (text/image/voice, no build step)
scripts/
  demo_offline.py    FREE full-pipeline demo with simulated LLM stages
  serve_demo.py      FREE demo web server (real UI, simulated stages)
  share_demo.ps1     uvicorn + cloudflared quick tunnel (public share link)
  smoke_test.py      REAL one-claim end-to-end test (costs a few cents)
  factcheck_probe.py FREE Google-API-only probe: shows KEEP/DROP per publisher
  asr_probe.py       Sarvam-only transcription probe (fractions of a rupee)
  fake_stages.py     the shared simulated LLM stages (demos + tests)
  render.py          console Truth Report formatter
tests/               pytest suite — always free, every paid seam faked
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

### Phase 2 — Production hardening + media
- [x] **Semantic claim cache — LIVE (2026-07-26):** `sqlite-vec` 0.1.9 + local
      EmbeddingGemma-300m (256-dim, STS prompt, CPU, $0/lookup). Design is
      **nominate-then-confirm**: the vector index only NOMINATES the nearest
      cached claim (distance ≤ 0.20); a ~$0.0005 Haiku equivalence check must
      CONFIRM before the cached verdict is served, and a confirmed phrasing is
      learned as an exact-cache alias. See Decisions log for why a pure
      distance threshold is provably unsafe. Vectors auto-wipe when the
      embedding model/dim changes (signature check in init_db).
- [ ] Postgres + pgvector **deferred to deployment**: Neon free tier (pgvector
      included, auto-wakes from scale-to-zero) beats Supabase (7-day hard pause)
      and native Windows install (Visual Studio source compile). Keep the cache
      behind the repository interface so the swap is SQL-only.
- [x] **Audio/video `/verify/media` — LIVE (2026-07-26):** any audio/video →
      ffmpeg-normalized to 16 kHz mono WAV → Sarvam Saaras v3 (chunked at 29 s
      for the sync API) → transcript → existing text pipeline. Caps: 25 MB
      upload, 300 s duration (protects credits), checked BEFORE any spend.
      WhatsApp OGG/Opus accepted. **Verified live:** a Windows-TTS spoken
      sentence transcribed verbatim (en-IN) for ₹0.04 of free credits.
- [ ] **Hindi audio still unproven end-to-end.** Everything on OUR side is
      verified free: WhatsApp PTT opus / m4a / mp3 / webm / amr all normalize, a
      90 s note chunks correctly, the exact Sarvam request (endpoint, auth
      header, `saaras:v3`, multipart fields) is pinned by a mock-transport test,
      and Devanagari/Tamil/Bengali round-trip through SQLite → JSON → page
      unchanged. What is NOT proven is Sarvam's transcription *accuracy* on real
      Hindi speech — no Hindi TTS voice exists on this machine (only en-US
      David/Zira), so it needs either a real recorded voice note
      (`scripts\asr_probe.py clip.ogg`, a fraction of a rupee) or a paid Sarvam
      TTS call to synthesize one. **Awaiting the user's choice.**
- [ ] ARQ/Redis queue replacing BackgroundTasks — needs Redis (Docker or Memurai);
      lowest priority while traffic is one user at a time
- [ ] Back-translate the Truth Report summary into the user's input language
- [x] Widen sources: Reuters/PTI/The Hindu/India Today/Vishvas (+ Quint, Fact
      Crescendo, Full Fact, Snopes) reach the engine via the trust-filtered
      Google Fact Check path (2026-07-25)

### Phase 3 — Delivery (the actual goal)
- [x] **Mobile web demo — BUILT (2026-07-26):** self-contained `static/index.html`
      (text + image + voice/video, Hinglish labels, dark mode, XSS-escaped
      rendering) served by FastAPI at `/`. Free full-UI demo:
      `scripts\serve_demo.py` (all LLM stages simulated, $0). Share a real
      public link: `.\scripts\share_demo.ps1` (cloudflared quick tunnel;
      `-DemoMode` for the free variant). ngrok avoided deliberately.
- [ ] WhatsApp Cloud API: free **test number** covers exactly 5 verified
      recipients; user-initiated service replies are free (per-message billing
      since 2025-07). A real number needs Meta Business verification (2–7 days).
- [ ] Telegram bot alternative: free, and long polling needs **no tunnel at
      all** — lowest-friction chat demo; friends may need to install Telegram.
- [ ] Lightweight PWA (Next.js) — only if the static page outgrows itself
      (needs Node.js)
- [ ] Localization UI (Hindi, Marathi, Tamil, Bengali…)

## 7. Decisions & findings log

- **2026-07-26 — Semantic cache: embeddings NOMINATE, Haiku CONFIRMS.** Local
  calibration on the real model produced a decisive finding: genuine paraphrases
  score 0.926–0.982 cosine similarity, but claims differing by ONE token score up
  to **0.971** ("pandemic in March 2020" vs "March 2019") — i.e. a wrong-verdict
  pair can embed CLOSER than a correct-hit pair. **No pure distance threshold is
  safe.** Design: KNN nominates within distance 0.20, then a Haiku structured
  yes/no equivalence check (~$0.0005, ~100× cheaper than a full check) gates the
  hit; confirmed phrasings are written back as exact-cache aliases so repeats are
  free. When the embedding model or dim changes, `init_db()` wipes vectors
  (verdicts survive; vectors re-learn on the next put).
- **2026-07-27 — Re-checking the review's UNVERIFIED findings found 3 more real
  holes.** The first review run lost 10 verification agents to a session limit;
  those findings were fixed on judgment alone, and that judgment was wrong in
  three places — a reminder that "looks obviously right" is not verification.
  (1) **Decode amplification:** a 3.26 MB Opus upload (an hour at 6 kbps) passed
  the 25 MB byte cap and expanded to 110 MB of PCM in RAM — **34×**, measured —
  before the duration cap rejected it; ~0.8 GB per request at the cap, on a
  publicly shared link. Now the source duration is probed before decoding and
  ffmpeg is capped with `-t`: rejected in 0.08 s holding no PCM.
  (2) **Unbounded fan-out:** rate limits count *requests*, but one request could
  carry any number of claims, each a paid retrieval + adjudication. Input is now
  capped (5000 chars) and claims per report capped (8), with the count of
  unchecked claims disclosed in the report rather than dropped silently.
  (3) **sqlite-vec loaded on every connection, ungated and unguarded:** since
  `get_conn` is the only door to the DB, a Python built without extension support
  would have 500'd *every* request including report reads. Now gated on the
  setting and degrades only the cache.
  Also: the limiter no longer charges a visitor for a submission rejected before
  any paid work, and its visitor table is hard-bounded against an IP flood.
- **2026-07-26 — Adversarial review of the Phase 2/3 build found 7 real defects;
  all fixed.** Most important: **"free demo mode" could spend real money** — the
  fake stages never patched the ASR seam, so the Voice button on a public
  `-DemoMode` link made live Sarvam calls. Fixed by patching every paid seam AND
  swapping the API keys for dummies, so a missed seam now fails auth instead of
  billing. Others: cache exceptions could silently discard a fully-paid verdict
  and report "no claims found" (all cache calls are now guarded and the DB uses
  WAL + a 30 s busy timeout); confirmed aliases were indexed, letting a chain of
  hops drift arbitrarily far from the claim actually adjudicated (aliases are now
  stored unindexed — only adjudicated claims are nomination anchors); a huge
  upload was buffered to disk and RAM before the size cap applied (now rejected
  by middleware before the body is parsed); ASR outages returned a bare 500 (now
  502 with a readable message); one transient embedding error disabled the
  semantic tier permanently (now a 3-failure budget that a success resets).
  Hardening added alongside: ffmpeg/ffprobe run with timeouts, a sanitized temp
  filename, and a protocol whitelist so a crafted "voice note" cannot make the
  server fetch remote URLs; the equivalence prompt delimits claim text as data.
- **2026-07-26 — Spending guard for the public link.** `share_demo.ps1` exposes
  the app to anyone with the URL, so `app/api/limits.py` caps checks per visitor
  (10/hour) and per deployment (100/day), returning a friendly 429. Reading a
  report is never limited. Off by default in tests; tune in `config.py`.
- **2026-07-26 — Media = transcribe-then-pipeline, caps before spend.** Sarvam
  `mode=transcribe` (not translate) keeps the existing normalize stage as the
  single language-detection point. Transcription happens inline in the route
  (like OCR) so failures surface as clear HTTP errors, with duration/size caps
  enforced BEFORE the first paid second. Verified live: TTS clip → verbatim
  transcript, `en-IN`, ₹0.04. Sarvam dashboard shows the user's actual balance.
- **2026-07-26 — ffmpeg was already installed** (Gyan 8.1.2 via winget) — the
  plan previously said otherwise; environment notes corrected.
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
- Free demo (console): `.venv\Scripts\python.exe scripts\demo_offline.py`
- Free demo (web UI): `.venv\Scripts\python.exe scripts\serve_demo.py` → http://127.0.0.1:8000
- Free tests: `.venv\Scripts\python.exe -m pytest tests -q`
- Free source probe: `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"`
- ASR probe (~paise): `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg`
- Real check: `.venv\Scripts\python.exe scripts\smoke_test.py "your claim"`
- Real server + UI: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload` → http://127.0.0.1:8000
- Share publicly: `.\scripts\share_demo.ps1` (add `-DemoMode` for the free variant)

## 11. Phase 2/3 prep — your action checklist (researched 2026-07-25)

Everything below was verified on the live web on 2026-07-25 (key sources:
sqlite-vec GitHub/PyPI, neon.com/docs, docs.voyageai.com, ai.google.dev,
developers.googleblog.com (EmbeddingGemma), docs.sarvam.ai, developers.facebook.com,
developers.cloudflare.com, core.telegram.org). Prices/tiers drift — re-check before
relying on a number months from now.

**Semantic cache (option b) — DONE 2026-07-26:**
- [x] `sqlite-vec==0.1.9` + `sentence-transformers` installed (in requirements.txt)
- [x] HF account + Gemma license accepted; `HF_TOKEN` in `.env`; model downloaded
      (~1.2 GB, cached in `~\.cache\huggingface`) and verified (256-dim)

**Audio/video (option c) — DONE 2026-07-26:**
- [x] Sarvam key in `.env`; live transcription verified (₹0.04)

**Demo to friends (option d) — page BUILT; sharing is one command away:**
- [x] cloudflared 2026.7.3 installed (found at `C:\Program Files (x86)\cloudflared\`)
- [ ] To actually share: `.\scripts\share_demo.ps1` and send the printed
      trycloudflare.com link (REAL mode spends money per check — share privately)
- [ ] Telegram route: SKIPPED for now (user decision 2026-07-26 — maybe later)
- [ ] WhatsApp test-number route (when wanted): Meta developer account → app with
      WhatsApp product → add up to 5 friends' numbers (each confirms a code) →
      webhook = the cloudflared URL (re-paste it on every tunnel restart)
