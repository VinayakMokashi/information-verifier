# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-07-28** (end-to-end review — see §7).

---

## 0. Where we are right now (read this first)

**Everything below is built, tested, committed and pushed.** `main` is clean;
**350 tests pass** (`.venv\Scripts\python.exe -m pytest tests -q`, free — every
paid API is faked).

Working end-to-end, verified against live APIs:
- **Text, image, voice/video AND pasted Reel/Shorts links** through one
  pipeline, with a mobile web page at `/` and a REST API underneath.
- **Bounded trust**: verdicts can only cite a curated whitelist; Google Fact Check
  results are filtered to it too.
- **Two-tier claim cache**: exact match, then semantic nomination confirmed by a
  cheap LLM check.
- **The answer comes back in the language the message arrived in** (2026-07-27),
  with the adjudicated English kept canonical and one tap away, plus its own
  content-addressed translation cache so cost stays per-rumour.
- **Spend guards**: per-visitor and per-deployment rate limits, input/claim caps,
  upload size and duration caps — all enforced before any paid call.

**To see it right now (free, $0):**
```powershell
.\.venv\Scripts\python.exe scripts\serve_demo.py     # then open http://127.0.0.1:8000
```

**Phase 3 delivery is BUILT**: a Telegram bot (`scripts/telegram_bot.py`,
long polling, no tunnel) that takes text, links, voice notes and photos and
replies in the sender's language. **It has not touched live Telegram yet** —
it needs `TELEGRAM_BOT_TOKEN` in `.env` (2 minutes with @BotFather), then:
app in one terminal, bot in the other. Every report now carries its own
measured bill (`report.usage`), and the six audit blockers for a public link
are closed (see §7 and §11).

**Waiting on Vinayak** — see §11 "Open decisions": AFP whitelist, public
spend caps, the translation-quality judgment, and the BotFather token.

---

## 0a. Paste a reel / Shorts link — ✅ BUILT (2026-07-28)

**History matters here:** Vinayak asked for this early on, it was never
captured in this file, and so it was never built until he pointed out the gap
— a search of all 35 commits and every doc found zero mention. It is part of
the definition of done. It now exists:

> **Paste a public Instagram Reel or YouTube (Shorts) URL into the same box
> as everything else** — the page routes it to `POST /api/v1/verify/link`,
> which pulls the claim out of the post (caption + subtitles, or capped
> audio download → Sarvam ASR) and runs the normal pipeline. Same
> submit → job_id → poll contract as every other surface.

**Live-verified free ($0), 2026-07-28:** the real provider resolved a Hindi
YouTube video and pulled 1,294 chars of `hi-orig` subtitles (the spoken claim
for ₹0 of ASR), and resolved + downloaded a real Reel (0.42 MB audio),
ffprobe'd 70.1 s against the 300 s cap, and stopped before the ₹0.58 ASR
purchase. **Facebook added 2026-07-28** after its own free probe: three public
government /videos/ URLs (PIB, I&B, Defence ministry pages) all resolved
anonymously, WITH duration advertised (so over-cap FB videos are rejected
free, unlike Instagram), and FB's auto captions are named `<lang>_FB` — one
track, the recognized speech, accepted as an ASR substitute. fb.watch short
links included. FB Reels URL-form (`/reel/<id>`) is allowlisted but untested
against a live reel — worth one probe when a real one comes along.

**Paid tail verified 2026-07-28** (`scripts/link_smoke.py`, Vinayak-approved):
a real Reel went link → download → Sarvam → 6 claims → verdicts → Hindi
back-translation, end to end, for **$0.279 measured** (the project's first
measured cost figure — see §8).

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
| Language detect + translation + retrieval + cache confirm | Claude **Haiku 4.5** (`claude-haiku-4-5`) |
| Retrieval | Native `web_search_20260209` (allowed_domains) + Google Fact Check API |
| Link ingestion | **yt-dlp** (Instagram/YouTube/Facebook extractors only, generic disabled) |
| OCR | Opus 4.8 vision (no Tesseract) |
| ASR | **Sarvam Saaras v3** (`saaras:v3`) — live, wired to `/verify/media` + `/verify/link` |
| Audio/video handling | ffmpeg (normalize to 16 kHz mono WAV, chunk, probe) |
| Embeddings | **EmbeddingGemma-300m** local on CPU, 256-dim ($0/lookup) |
| Storage | **SQLite + sqlite-vec** (Postgres + pgvector deferred to deployment) |
| Async | FastAPI BackgroundTasks (ARQ/Redis still deferred) |
| Frontend | **Self-contained `static/index.html`** served by FastAPI — no Node, no build |
| Public sharing | cloudflared quick tunnel (`scripts/share_demo.ps1`) |

**Every LLM boundary returns a validated Pydantic object** via `messages.parse`.

## 4. Pipeline

```
INPUT
  /verify/text   raw text
  /verify/image  → OCR (Opus vision)            ─┐  machine-read text is kept in
  /verify/media  → ffmpeg → Sarvam ASR (chunked) ┘  report.source_text and shown back
  /verify/link   → yt-dlp resolve (inline, free) → background:
                   caption + (subtitles | capped download → ffmpeg → ASR)

normalize (Haiku: detect language + English pivot)
  → extract claims (Opus)   → capped at max_claims_per_report
  → per claim, concurrently:
        1. exact cache hit?                        → serve, free
        2. semantic nomination (sqlite-vec KNN)     → candidate only, never served
           └ Haiku equivalence confirm (~$0.0005)   → serve + learn alias (unindexed)
        3. otherwise: retrieve (Haiku: web_search whitelist + Google Fact Check,
           trust-filtered) → adjudicate (Opus, adaptive thinking)
  → aggregate
  → back-translate (Haiku, one call per claim, concurrent) — skipped for English
       └ ADDITIVE: lands in report.localized, never over the English
  → persist
OUTPUT  Truth Report: rating + confidence + reasoning + correction + citations,
        plus the same prose in the reader's language
```

## 5. Directory map

```
app/
  main.py            FastAPI app + lifespan (init_db) + static mount at "/"
  config.py          settings + model IDs + cache/media knobs
  trusted_sources.py SEARCH_DOMAINS (crawlable) + FACTCHECK_ONLY_DOMAINS + trust matching
  api/               routes (text/image/media/link/reports) + wire DTOs
  models/            Pydantic contracts: Claim, Verdict, Evidence, TruthReport
  engine/            normalize, extract, retrieve, adjudicate, equivalence,
                     aggregate, translate (back-translation), pipeline, prompts
  providers/         llm (Anthropic), vision (OCR), factcheck (Google),
                     asr (Sarvam Saaras v3), embeddings (EmbeddingGemma),
                     media (ffmpeg helpers), links (yt-dlp: Reels/Shorts)
  store/             SQLite + sqlite-vec db, repository (reports + 2-tier claim
                     cache + content-addressed translation cache)
static/
  index.html         self-contained mobile demo page (text/image/voice, no build step)
scripts/
  demo_offline.py    FREE full-pipeline demo with simulated LLM stages
  serve_demo.py      FREE demo web server (real UI, simulated stages)
  share_demo.ps1     uvicorn + cloudflared quick tunnel (public share link)
  smoke_test.py      REAL one-claim end-to-end test (costs a few cents)
  factcheck_probe.py FREE Google-API-only probe: shows KEEP/DROP per publisher
  link_probe.py      FREE yt-dlp probe: does a Reel/Shorts URL resolve, captions?
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
- [x] **Hindi audio tested end-to-end (2026-07-27, ~₹0.11 authorized spend).**
      Sarvam TTS (`bulbul:v2`, hi-IN) synthesized a Hindi claim, re-encoded to a
      WhatsApp-style OGG/Opus voice note, and POSTed to the real `/verify/media`.
      Route, ffmpeg, ASR and Devanagari handling all worked — **but the
      transcription was not exact**:
      spoken `डब्ल्यूएचओ ने कहा कि 5जी से कोरोना फैलता है।`
      heard  `डब्ल्यूएचओ ने कहा कि जिसे कोरोना फैलता है।`
      The entity `डब्ल्यूएचओ` (WHO) survived; the alphanumeric **`5जी` (5G) — the
      subject of the claim — was lost**. A second call with an explicit
      `language_code=hi-IN` hint produced the identical output, so it is not our
      parameter. Unresolved whether the fault is Sarvam's ASR or the synthetic
      voice's pronunciation; a human-recorded note would settle it.
      **Consequence, now mitigated:** a mangled key term means confidently
      fact-checking a DIFFERENT claim. Reports carry `source_text` (the ASR
      transcript / OCR text) and the page shows it back — "We read this from
      your file — if it's wrong, retype it above" — so a mis-hear is visible
      instead of silent. See Decisions log.
- [x] **`/verify/link` — BUILT & live-verified free (2026-07-28), see §0a and §7.**
      The measurement trail that shaped it: The
      back half already exists: `/verify/media` does ffmpeg → chunk → Sarvam →
      transcript → pipeline, with caps. What is missing is *fetching* the media
      from a URL. Plan, cheapest step first:
      1. ✅ **Free probe built and run** (`scripts/link_probe.py`, yt-dlp
         2026.07.04, metadata only, $0). **Measured 2026-07-28 on three real
         Reel URLs Vinayak supplied, plus YouTube:**
         - **Instagram Reels resolve ANONYMOUSLY — no cookies needed.** All
           three (narendramodi, bharatjodo, peektv_in) returned metadata.
           ⚠️ **An earlier probe run said the opposite and was wrong**: it used
           an invented Reel ID, and Instagram's "empty media response … use
           cookies" error is indistinguishable from "no such post". The run was
           correctly labelled unsettled at the time; the lesson is that a
           fabricated test input can produce a confident wrong conclusion about
           a whole platform.
         - **YouTube works on all three URL forms**: `/shorts/<id>`,
           `/watch?v=<id>`, `youtu.be/<id>`.
      1b. ⚠️ **Instagram reports NO duration and NO filesize** (`duration:
         None`, every format `filesize: None`). Both pre-spend caps
         (`max_media_seconds`, `max_media_bytes`) are therefore unenforceable
         from metadata for Reels. **Invariant 5 still holds, but only if the
         order is right**: cap the download as bytes stream (free —
         bandwidth), then `ffprobe` duration and reject, and only then call
         Sarvam. `normalize_to_wav` already probes duration before decoding,
         so the existing media path is the correct shape to reuse.
         *(The probe itself had this bug and it is fixed: it printed an unknown
         duration as "0s, within the cap" — announcing that a spend guard had
         passed when it was never applied.)*
      2. **Two free text sources, and neither is sufficient alone:**
         - **Post caption** (`description`) is present and substantial on both
           platforms — 599 chars on the PEEK TV reel, carrying a full quoted
           assertion that is checkable with **no download and no ASR**. But the
           PIB Short's 492 chars were pure promo ("Join our official
           channel…"). So captions are a cheap *supplement*, not a replacement;
           the `checkworthy` filter already discards the promotional ones.
         - **Subtitles**: YouTube Hindi videos carry auto-captions in `hi` and
           `hi-orig` (plus mr/ta/bn/te/kn/ml/gu/pa/or/as/ur) → the spoken claim
           for **₹0 of ASR**. **Instagram has none at all**, and the 14 s PIB
           Short had none either. Sarvam fallback is not optional. A 250 s
           video would cost ~₹2.08 to transcribe.
      3. **Consider frame OCR.** A lot of Indian reel misinformation is burned
         into the image, not spoken; we already have Opus vision. Adds cost per
         frame, so make it opt-in or heuristic.
      4. **SSRF is a real risk here.** §7 records deliberately hardening ffmpeg
         so a crafted upload could not make the server fetch remote URLs — this
         endpoint reopens that door on purpose. Needs a host allowlist plus
         private-IP/redirect blocking, and the existing size/duration caps.
      5. Note: downloading from these platforms is against their ToS. Vinayak's
         call; recorded here so the decision is explicit rather than implied.
- [ ] ARQ/Redis queue replacing BackgroundTasks — needs Redis (Docker or Memurai);
      lowest priority while traffic is one user at a time
- [x] **Back-translated Truth Reports — LIVE (2026-07-27):** the summary, each
      claim, its reasoning and its correction come back in the language the
      message arrived in. Additive (`report.localized`), never in place — see
      the Decisions log for the three properties that are enforced by the shape
      of the code rather than by prompt rules. Own content-addressed
      translation cache, so a repeat forward in the same language is free.
      Not yet exercised against the live API (needs a paid run to confirm
      translation quality on real Indic output — the plumbing is pinned by
      tests, the prose is not).
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
- [x] **Telegram bot — BUILT (2026-07-28), not yet live.** Long polling, no
      tunnel; consumes the same two REST calls as the page; localized-first
      replies with English-receipt citations; handles text/link/voice/photo.
      Needs `TELEGRAM_BOT_TOKEN` from @BotFather to go live. WhatsApp stays
      deferred: Meta business verification + webhook tunnel + 5-recipient
      test cap; when it happens it reuses `format_reply` unchanged.
- [ ] Lightweight PWA (Next.js) — only if the static page outgrows itself
      (needs Node.js)
- [ ] Localization UI (Hindi, Marathi, Tamil, Bengali…)

## 7. Decisions & findings log

*Newest first. This is the "why", and the most useful section to skim before
changing anything — several entries record measurements that overturned an
obvious-looking design.*

- **2026-07-28 (late) — End-to-end review before handoff: 11 more defects,
  every one of them SILENT.** A 10-angle review of everything since `0389647`
  (4 angles lost to a session limit; 6 reported). What it found had a theme —
  each failure produced output that looked entirely plausible:
  **(1) POSIX language tags disabled translation.** `target_language` stripped
  underscores for the English check but then matched the RAW tag against a
  regex with no underscore, so `hi_IN`/`mr_IN`/`ta_IN`/`bn_BD` silently
  returned an English-only report — the mission failure the stage exists to
  prevent, unlogged because None legitimately means "nothing to do".
  **(2) Persisted reports kept a stale whitelist.** The trust filter ran when a
  verdict was BUILT; a report saved last week carried last week's
  TRUSTED_DOMAINS, and the URL-hash resume re-serves stored reports on every
  reload. Now filtered on the way out of the store too.
  **(3) The meter could have doubled every bill** if a future SDK routed
  `parse` through `create` (the installed one calls `_post` — checked).
  Re-entrancy guard added.
  **(4) One translation per tag SPELLING**, not per language — `hi` and
  `hi-IN` bought separate copies of identical prose (backlog item 12, closed).
  **(5–10) The Telegram bot could take money and give silence** six ways:
  `send()` discarded Telegram's response entirely; `quote=False` inside
  `href="…"` broke the HTML on a citation URL with a quote in it; `source_text`
  was cut at 500 chars with no marker (invariant 4); the final 4096-slice
  could cut mid-tag; the getUpdates offset was confirmed AFTER minutes of paid
  work, so a crash re-billed the whole check on restart; and a slow check told
  the user to resend, buying it twice. In-flight jobs are remembered per chat
  now and resumed instead.
  **(11) The platform list had drifted the first time it was extended** —
  Facebook was in the hosts, extractors and page regex, but all three
  user-facing messages still said "Instagram and YouTube", and the agreement
  test that should have caught it iterated four hand-picked non-Facebook URLs.
  One definition now; the test walks every allowlisted host.
  Also measured while validating the token Vinayak added: **Telegram timed out
  twice before answering**, so every Telegram call retries. And the page no
  longer dead-ends on a stale `#job=` link or swallow a file pick while busy.
- **2026-07-28 — The public-link blockers are closed, and reports now carry
  their own bill.** One working session, six commits, each mutation-style
  tested: **(1)** invariant 1 finally holds on OUTPUT — `_enforce_trust()`
  filters every verdict's citations against the whitelist on every serve path
  including cached ones, so removing a domain from TRUSTED_DOMAINS is now a
  real curation act; a decisive rating that loses its last receipt is
  withdrawn to UNVERIFIED ("every verdict carries receipts" outranks it).
  **(2)** Evidence text — the last unsanitized prompt path, quoting pages
  strangers wrote — reaches the adjudicator delimited as data; URLs stay
  verbatim because the output filter now guards them. **(3)** The per-claim
  search budget survives pause_turn: each response's measured search count
  shrinks the next request's max_uses, so "4 per claim" is the code's cap
  regardless of server resume semantics. **(4)** CORS wildcard removed
  entirely — same-origin page, server-side bots, and an open ACAO let any
  website spend the budget from its visitors' browsers. **(5)** /verify/media
  ASR moved behind the 202 like links (proxies cut ~100 s inline requests
  while the server kept spending); outages are FAILED reports in words, and
  the image-OCR refund guard stays. **(6)** A long check is never orphaned:
  the job id lives in the page's URL hash and a reload resumes the same job.
  Plus: **per-report spend metering** (`report.usage` — tokens from the API's
  own usage fields, searches, ASR seconds, and a list-price dollar estimate;
  contextvar-ambient so the concurrent fan-out bills the right job; FAILED
  reports keep their bill), **Facebook links** (probed first: three public
  government videos resolve anonymously WITH duration; `<lang>_FB` auto
  captions accepted as the recognized speech), and the **Telegram bot** (§6).
- **2026-07-28 — First paid link run: $0.279 measured, and four §11 questions
  moved.** `scripts/link_smoke.py` wraps the shared Anthropic client and the
  ffmpeg boundary so every run reports measured spend — the audit's top gap.
  The PEEK TV reel (70.1 s, Hinglish speech): Haiku 14 calls (98k in / 3k
  out — retrieval reading pages dominates), Opus 7 calls (1 extract + 6
  adjudicate), 5 web searches, ₹0.58 ASR ⇒ **$0.279 total**, under the $0.39
  modelled for 3 claims despite carrying 6 — UNVERIFIED claims are cheap.
  What the run proved: **(a)** bounded trust found the ONE whitelisted source
  covering a niche story (BOOM's report on the same protester, incl. that the
  viral spread was partly AI fakes) and rated that claim MOSTLY_TRUE 58%,
  while abstaining honestly on the 5 claims no trusted source addressed —
  exactly the designed behaviour on fresh, local news. **(b)** Sarvam on REAL
  Hindi speech preserved every alphanumeric — ₹140, "27th", "5 तारीख", एफआईआर
  — so the 5जी loss from the synthetic-TTS test (§11 open decision 3) was the
  robot voice, not Sarvam. Effectively settled. **(c)** Live back-translation
  read well; residual rough edges recorded: terminology still drifts between
  claims (वक्ता vs स्पीकर, भरोसेमंद vs विश्वसनीय — one call per claim is the
  cause and the alignment guarantee is worth the price), the summary
  translates the rating word ("सत्यापित नहीं") while the badge stays English
  (already backlog item 19), UNVERIFIED confidence renders inconsistently (0
  for "no context", 95 for "sources don't address it"), and extraction left
  "the speaker" unresolved even though the caption names her — social-post
  extraction could hint that the caption may name the first-person speaker.
  Also fixed: the console renderer never printed `source_text` — invariant 4
  had a hole on that surface, found the moment a real transcript existed.
- **2026-07-28 — /verify/link: resolve inline, spend in the background, caps
  by ordering.** The §0a requirement is built. Design decisions worth keeping:
  (1) **Resolve runs inline, fetch+ASR in the background.** A bad link (typo,
  private, deleted) is the common failure and gets an immediate readable 4xx
  with the quota refunded — nothing was spent, since resolve is metadata-only.
  The download and transcription then run behind a 202, because the audit
  showed proxies cutting long inline requests while the server kept spending.
  Consequence, documented in the route: a slot accepted at 202 stays consumed
  even if the background half fails — refunds cannot be issued from a
  background task, and over-counting is the error the wallet survives.
  (2) **Instagram forces the caps to move.** It advertises neither duration
  nor filesize (measured), so invariant 5 holds by ORDER: byte- and
  wall-clock-capped download as the stream arrives (free — bandwidth), then
  ffprobe against `max_media_seconds` (the existing normalize_to_wav path),
  and only then Sarvam. YouTube DOES advertise duration, so an over-cap video
  is 413'd before a single byte.
  (3) **Subtitles replace ASR when honest.** Manual tracks in any language
  win; auto tracks only with the `-orig` suffix — non-orig auto tracks are
  machine TRANSLATIONS, and feeding one to normalize() would pivot a
  translation of a translation. json3 preferred over YouTube's rolling VTT
  (which repeats most lines; the fallback parser collapses them).
  (4) **Three independent SSRF fences**, because this endpoint deliberately
  reopens the door §7 closed for uploads: exact-host https-only allowlist with
  trusted_sources-grade parsing; yt-dlp pinned to the Instagram/YouTube
  extractors so its generic extractor (which fetches ANY url) cannot run; and
  the download function re-checks the allowlist rather than trusting callers.
  (5) The post caption rides along capped at 2000 chars — measured carrying a
  full quoted claim on one real reel and pure promo on another; the
  checkworthy filter sorts that out downstream.
  **Live-verified free:** 1,294 chars of `hi-orig` subtitles from a Hindi
  YouTube video (₹0 of ASR), and a real Reel resolved → 0.42 MB audio
  downloaded under cap → 70.1 s ffprobe'd → stopped before the ₹0.58 ASR
  spend. ToS note: fetching from these platforms is against their terms;
  Vinayak decided to proceed for personal/testing use.
- **2026-07-28 — First live Devanagari run, and an audit that found a critical
  spend hole.** A real `smoke_test.py` run on a Hindi ₹2000-note rumour went
  end to end: 3 claims extracted from one compound sentence, rated separately
  (MOSTLY_TRUE/FALSE/FALSE), citing only pib.gov.in and factly.in — bounded
  trust held. Numbers, dates and percentages carried across translation
  exactly, and the MOSTLY_TRUE hedge survived instead of hardening into FALSE.
  Two translation defects showed up only by reading the Hindi: terminology
  drifted across claims (प्रचलन / संचलन / परिसंचरण for "circulation" in one
  report — the measured price of translating each claim in its own call) and
  English was left sitting inside Hindi sentences ("अभी भी exchange या जमा").
  Both are prompt fixes, **not yet verified against the live API**.
  **Cost note:** the run was quoted at ~$0.06–0.13 on the assumption of one
  claim. The sentence became three, so it cost roughly 3× that. The per-claim
  figure in §8 also looks low against the actual call structure — see the
  revised model there. **We do not log token usage, so no exact figure exists
  for any run.** Fixing that is the single highest-value next task.
  A six-way adversarial audit then raised 37 findings, 23 surviving an agent
  told to refute them. The critical one: `_quota` refunded the rate-limit slot
  on ANY HTTPException, including the 422/502 that `/verify/media` and
  `/verify/image` raise *after* Sarvam and Opus vision have been billed — so a
  loop of silent audio could burn credit indefinitely with the daily counter
  reading zero. Fixed; the routes now mark the spend boundary explicitly.
  Also found: `pytest` could reach the real Sarvam API (conftest faked every
  seam but `get_asr_provider`), the per-claim translation isolation did not
  actually exist (`parsed_output` dereferenced outside its guard, into a
  `gather` with no `return_exceptions`), and last commit's `dir="auto"` fix was
  inert on the two blocks that carry RTL text. The remaining 19 are listed in
  §11 as a backlog rather than silently carried.
- **2026-07-27 — Reviewing the back-translation diff found 5 more defects, all
  reproduced before fixing and re-measured after.**
  (1) **The language tag could carry instructions.** `input_language` is Haiku
  output derived from a stranger's text and is interpolated straight into the
  translation prompt. The tag check allowed spaces, and `english now reply only
  with OK` was measured passing it. Now one token, no spaces — `hi`, `hi-IN`,
  `Hindi`, `zh-Hant` pass, every crafted probe fails closed. Cost: a two-word
  language name answers in English.
  (2) **A long verdict was silently shortened.** A 2734-char reasoning cleared
  the report-wide cap, was cut to 2000 on the way into the prompt, and came back
  translated with its concluding sentence gone — a fact-check missing its
  conclusion, presented as complete. Over the cap we now decline the claim and
  show English, which the page labels out loud.
  (3) **One bad cache row disabled a claim's translation forever.** A cached
  translation rejected by today's rules returned early and the row stayed put,
  so every future reader of that rumour silently got English. It now
  re-translates and overwrites — one call, once, and the cache heals itself.
  (4) **The console renumbered claims** — it enumerated `localized.claims`
  instead of indexing by claim position, so a short list relabelled claim 3's
  answer as claim 2's. Same harm class as serving a cached verdict for a
  different claim.
  (5) **The page's language lookup read inherited properties**: `constructor`
  passes the server's tag check, and `LANG_NAMES[tag]` would have rendered
  Object's constructor as the button label.
  Also: `dir="auto"` on every reader-language element — Urdu and Sindhi are
  right-to-left and their punctuation lands on the wrong end in this LTR page
  without it; and an empty summary no longer buys a translation call.
- **2026-07-27 — Back-translation: additive, prose-only, structurally aligned.**
  The mission is "the real answer, in their own language", but the pipeline
  pivots to English and the report came back in English — a Hindi reader could
  see a red FALSE badge and not read *why*, which is the half that changes a
  mind. Three properties are enforced by the shape of the code, not by prompt
  rules, because a prompt rule is a request:
  **Additive.** The translation lands in `report.localized` and `localize()`
  returns a block rather than writing one; the adjudicated English stays
  canonical. The trap avoided is the claim cache — translate a `Verdict` in
  place before caching it and the first Hindi reader poisons that rumour for
  every Tamil reader behind them. Pinned by a test that reads the cache back.
  **Prose only.** `LocalizedClaim` has no field for rating, confidence or
  citations, so they cannot be translated by accident. A rating is a structured
  enum; a citation's title and publisher are the strings a reader searches for
  on the source page, and translated the receipt stops being findable.
  **Structural alignment.** One Haiku call per claim, so the pairing is held in
  Python rather than asserted by a model returning a list. A failed claim leaves
  `None` at its own index and can never shift the next claim's answer up a slot.
  ~9 concurrent calls on a full report (~$0.01, under 2% of the check it rides
  on) instead of one, and per-claim failure isolation comes free with it.
  The translator also may not become an author: an invented correction on a
  TRUE/UNVERIFIED claim is discarded, and a dropped field falls back to English
  wholesale rather than serving half a verdict. A translator being down costs
  the reader a translation, never a verdict.
- **2026-07-27 — Translation needs its own cache, or the claim cache's
  economics invert.** The claim cache exists so one viral forward is one paid
  check however many people send it. Back-translation quietly undid that: every
  reader then paid ~$0.01 to re-translate the same cached verdict — a thousand
  readers meant one $0.05 check and $10 of translation, i.e. per-USER pricing
  wearing a cache's clothes. Fixed with a content-addressed cache keyed by
  (digest of the exact English source, language). Content-addressing means
  there is no invalidation logic to get wrong — re-adjudicate a claim, its prose
  changes, the key changes, the stale translation is never looked up again. The
  digest is over a JSON dump, not a concatenation, so `("ab","c")` and
  `("a","bc")` cannot hash into one another's translation.
- **2026-07-27 — Devanagari broke the console renderer, measured.** On Windows a
  redirected stdout falls back to the ANSI code page (cp1252 here) and Indic
  text raises `UnicodeEncodeError` there while the same command on a console
  succeeds — so `demo_offline.py > out.txt` died the moment a report carried a
  localized block. `scripts/render.py` grew `print_report()`, which forces UTF-8
  and degrades to printing anyway for any stdout that refuses. This machine has
  `PYTHONIOENCODING=utf-8` set inside the agent harness but *not* in a plain
  PowerShell session, so it looked fine until the variable was cleared — worth
  remembering before trusting any "it printed fine for me".
- **2026-07-27 — Independent re-verification found 5 more live defects, 3 of them
  introduced by the previous round of fixes.** A second adversarial workflow
  re-ran every unverified finding against the fixed code and swept the fixes
  themselves for regressions. Confirmed fixed: the decode amplification and the
  sqlite-vec gating. Still live, now fixed and re-measured:
  (1) **The "free demo" never protected Anthropic.** `providers/llm.py` builds
  one client at import, so blanking `settings.anthropic_api_key` left the LIVE
  client holding the real key — the backstop looked right and protected nothing,
  for the most expensive provider. Now the client's key and the env var are
  overwritten; the test asserts on `auth_headers`, i.e. the wire value.
  (2) **The 413 middleware was bypassable by omitting Content-Length** — a
  chunked upload skipped it entirely (629 MB spooled against a 1 MB cap). It is
  now raw ASGI counting bytes as they stream; a `@app.middleware("http")`
  function structurally cannot do this, since Starlette rebuilds the downstream
  receive channel.
  (3) **The rate limiter was defeated by plain concurrency.** Splitting
  check-from-count left awaits in between, so 30 simultaneous uploads all saw an
  empty counter and passed a 2/day cap. Reserving is now atomic, with a refund
  for submissions rejected before any paid work.
  (4) One embedding blip burned the whole 3-failure budget, because a report's
  claims embed concurrently. Failures are now counted per event, and a paused
  tier retries after 5 minutes instead of staying off until restart.
  (5) Report reads/writes ran on the event loop, so the 30 s busy timeout could
  freeze the entire server for 30 s; they now run in threads.
  Also: equivalence-prompt delimiters are escapable (`</claim_a>` in claim text)
  → angle brackets neutralized and claims truncated to 1000 chars; `_SAFE_SUFFIX`
  used `$`, which matches before a trailing newline, so `note.ogg\n` reached
  `open()` and 500'd → `\Z` + `fullmatch`; the web page dispatched its request
  before the double-submit guard ran → it now takes a request factory.
- **2026-07-27 — Machine-read text is now shown back to the user.** The Hindi
  audio test lost `5जी` from a claim about 5G (see Phase 2 checklist). Speech and
  image text are *guesses*, and a wrong guess means the engine confidently checks
  a claim the person never made — which is precisely the harm this project
  exists to reduce. So `TruthReport.source_text` carries whatever a machine read
  (ASR transcript or OCR text) and the page displays it above the verdict, with
  an invitation to retype. Text submissions leave it unset — nothing was guessed.
  Open question for Phase 3: whether to ask for confirmation *before* spending on
  a check when the input came from audio.
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
- **2026-07-26 — Semantic cache: embeddings NOMINATE, Haiku CONFIRMS.** Local
  calibration on the real model produced a decisive finding: genuine paraphrases
  score 0.926–0.982 cosine similarity, but claims differing by ONE token score up
  to **0.971** ("pandemic in March 2020" vs "March 2019") — i.e. a wrong-verdict
  pair can embed CLOSER than a correct-hit pair. **No pure distance threshold is
  safe.** Design: KNN nominates within distance 0.20, then a Haiku structured
  yes/no equivalence check (~$0.0005, ~100× cheaper than a full check) gates the
  hit; confirmed phrasings are written back as exact-cache aliases so repeats are
  free. When the embedding model or dim changes, `init_db()` wipes vectors
  (verdicts survive; vectors re-learn on the next put). **Any new embedding model
  needs its own calibration — never copy this threshold.**
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

## 8. Cost model (approximate)

- Opus 4.8: $5 / $25 per million tokens (in / out). Haiku 4.5: $1 / $5.
- Web search: ~$0.01 per search (separate fee); capped at `max_search_uses` (4) per claim.
- Semantic-cache confirm: ~**$0.0005** per candidate (Haiku, structured bool) —
  roughly 100× cheaper than the full check it can replace.
- Back-translation: ~**$0.001 per claim** (Haiku; one call per claim plus one for
  the summary, run concurrently), so ~$0.01 on a full 8-claim report — under 2%
  of the check it rides on. **$0 for English input** (the stage is skipped
  before any call) and **$0 on a translation-cache hit**, which is the common
  case for a forward that has been seen before in the same language.
- Sarvam ASR: **₹30/hour**, billed per second (~₹0.50/min).
- A **link check** adds: $0 when the post has subtitles or the claim is in
  the caption (YouTube Hindi auto-captions measured present) — otherwise the
  reel's audio duration × ASR rate (a 70 s reel ≈ ₹0.58) on top of the
  normal per-claim cost. Resolve/download are bandwidth, not API spend. Sarvam TTS (only used
  for testing): bulbul:v2 ₹15 / 10K chars.
- **Per real single-claim check: ~$0.12–0.26 modelled.** First MEASURED
  anchor (2026-07-28, `scripts/link_smoke.py`): a 6-claim reel report cost
  **$0.279 all-in** ($0.22 LLM + $0.05 search + ₹0.58 ASR) — cheaper per
  claim than the model because UNVERIFIED claims skip heavy adjudication.
  Metering now lives IN THE APP: every report carries `report.usage`
  (tokens per model from the API's own usage fields, searches, ASR seconds,
  estimated USD), so future figures come from reports, not scripts.
- A submission is priced per CLAIM, not per message, and one ordinary compound
  sentence becomes several claims — a single Hindi sentence about ₹2000 notes
  extracted into **three**. Budget per sentence, not per submission.
- **Fixed per report** (regardless of claim count): ~$0.03 for normalize +
  extract.

| Submission | Typical | Worst case at current caps |
|---|---|---|
| 1 claim | ~$0.15 | ~$0.29 |
| 3 claims | ~$0.39 | ~$0.81 |
| 8 claims (`max_claims_per_report`) | ~$0.99 | ~$2.11 |
| repeat of a cached rumour, same language | ~$0.03 | (both caches hit) |

⚠️ **At the current caps a public link's daily ceiling is ~$99 typical /
~$211 worst case** (`max_checks_per_day` 100 × `max_claims_per_report` 8).
That is what open decision 2 is really asking about.

**What bounds the spend** (all in `app/config.py`):

| Setting | Default | Bounds |
|---|---|---|
| `max_checks_per_hour` | 10 | submissions per visitor IP |
| `max_checks_per_day` | 100 | submissions across the whole deployment |
| `max_input_chars` | 5000 | text per submission |
| `max_claims_per_report` | 8 | paid claim checks per submission |
| `max_media_bytes` | 25 MB | upload size (enforced as bytes stream in) |
| `max_media_seconds` | 300 | audio duration (probed before decoding) |
| `max_search_uses` | 4 | billed web searches per claim |
| `max_translate_chars` | 12000 | source prose per report sent to translation |
| `translate_reports` | true | set false to answer in English only, at $0 |

⚠️ Before sharing the public link widely, consider lowering `max_checks_per_day`
and/or `max_claims_per_report` — 100 × 8 claims is a large worst case.

**Always-free**: the whole test suite, `demo_offline.py`, `serve_demo.py`,
`share_demo.ps1 -DemoMode`, and `factcheck_probe.py`.

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

## 11. Open items

### THE TODO LIST (updated 2026-07-28, end of session — the authoritative one)

**Needs Vinayak, not code:**
1. **AFP Fact Check** (`factcheck.afp.com`, IFCN-certified) is the only publisher
   still being dropped by the trust filter on live queries. Add it to
   `FACTCHECK_ONLY_DOMAINS` or leave it out? Curating the whitelist is a trust
   decision, deliberately not an automatic one.
2. **Spend caps before going public** — see §8: the current ceiling is ~$99/day
   typical, ~$211 worst case. Lower `max_checks_per_day` (100) and/or
   `max_claims_per_report` (8)?
3. **Judge the live Hindi translation quality.** Two real reports exist now
   (the ₹2000-note check and the PEEK TV reel). The prose read well to the AI;
   whether it reads *naturally* is Vinayak's call. Known rough edges are
   recorded in §7 (terminology drift between claims, the summary translating
   the rating word while the badge stays English).
4. ~~Create the Telegram bot token~~ **DONE by Vinayak 2026-07-28.** The
   token is in `.env` and validates as `@Information_Verifier_bot`. Re-check
   any time for $0:
   `.venv\Scripts\python.exe scripts\telegram_bot.py --check-token`.
   **The first live message is now the only step left**, and it was
   deliberately NOT taken while Vinayak slept — anyone messaging the bot
   spends real money and nobody was awake to supervise. To go live:
   `uvicorn app.main:app` in one terminal, `scripts\telegram_bot.py` in the
   other, then message the bot.

**Settled this session (kept for the record):**
- ~~Hindi ASR accuracy~~ → settled 2026-07-28: real Hinglish speech from a reel
  preserved every alphanumeric (₹140, "27th", एफआईआर) — the synthetic TTS voice
  caused the old 5जी loss, not Sarvam.
- ~~/verify/link paid tail~~ → verified 2026-07-28: $0.279 measured, one
  MOSTLY_TRUE with a live BOOM citation + five honest abstentions.
- ~~Back-translation never read live~~ → two real Hindi reports now exist
  (item 3 above is what remains of this).

**Cheap verifications pending (code is ready, needs a paid run or a URL):**
- **Translation prompt fixes are unverified.** The 2026-07-28 fixes for
  terminology drift and English-left-inside-Hindi are prompt changes; no paid
  run has read their output. Cheap: the ₹2000 claims are cached, so a re-run
  of `smoke_test.py` on that claim pays only normalize + extract + 4 Haiku
  translations (~$0.04).
- **Facebook `/reel/<id>` URL form is unprobed.** `/videos/` URLs are measured
  working; when a real FB reel link comes along, one free
  `scripts\link_probe.py` run settles the reel form.
- **Telegram bot has never touched live Telegram.** Token validated ($0,
  getMe only); 24 bot tests are offline. The first live message is the real
  test — and worth watching, because Telegram was measured timing out twice
  in three calls from this network (every call retries now).
- **WhatsApp bot: deferred, deliberately.** Meta business verification +
  webhook tunnel + 5-recipient test cap. When it happens it reuses the
  Telegram bot's `format_reply` unchanged.

### Known-defect backlog (from the 2026-07-28 adversarial audit)

Six independent read-only sweeps raised 37 findings; each was then handed to a
separate agent instructed to *refute* it. 23 survived. Four are fixed (see the
Decisions log); these are the rest, in the order I would take them. None is
known to be actively causing harm today — the app is not publicly exposed.

**Before sharing a public link — ALL SIX CLOSED 2026-07-28** (see §7):
1. ~~Verdict citations unchecked~~ → `_enforce_trust()` on every serve path.
2. ~~search cap per-request~~ → budget enforced across continuations in code.
3. ~~evidence undelimited~~ → `as_prompt_data` in `adjudicate._render`.
4. ~~CORS wildcard~~ → removed; no ACAO issued, pinned by test.
5. ~~inline media ASR~~ → behind the 202, FAILED reports in words.
6. ~~orphaned paid reports~~ → job id in the URL hash; reload resumes.

**Correctness / trust:**
7. `aggregate.py` has no test file and every fake verdict in the suite is FALSE,
   so the worst-first roll-up precedence is vacuously verified.
8. The "a failed claim surfaces as UNVERIFIED, never vanishes" branch in
   `pipeline.py` is never exercised by a test.
9. Raw exception strings are stored in `report.error` and rendered to the user.
10. A claim adjudicated while the semantic tier is paused is stored with no
    vector and never re-indexed.

**i18n:**
11. The verdict word itself is never localized — per-claim badges show the raw
    English enum, and `RATING_LABELS` is romanized *Hindi* shown to Tamil and
    Bengali readers too. Now in TWO places (the page and the bot's
    `_RATING_BADGE`): fix once in the API payload, not per surface.
12. ~~translation cache keyed on the raw tag~~ **CLOSED 2026-07-28** — the key
    folds case and region. A language NAME ("Hindi") still keys separately.

**Ops / hygiene:**
13. Nothing is ever pruned: `created_at` is written and never read, so every
    stranger's message is retained indefinitely.
14. All `asyncio.to_thread` work shares one default executor — an embedder cold
    start can freeze report polling for everyone.
15. `/health` is a constant; there is no way to see spend, queue depth, or which
    subsystems are degraded.
16. Two weak tests: `test_devanagari.py:97` asserts a property of a constant, not
    of the page; the embedding failure-budget tests neutralize `_FAILURE_WINDOW_S`
    and so hide whether the budget ever exhausts under production timing.

**Deferred by the 2026-07-28 end-to-end review — real, but not worth the churn
that night. Roughly in value order:**
17. **No transcript cache for links.** One viral reel forwarded by many people
    re-downloads and re-buys the whole ASR every time (~₹0.58 for a 70 s clip)
    — the same "per-user pricing wearing a cache's clothes" inversion the
    translation cache was built to fix, still open on the most expensive
    input. `resolve_link` already returns a stable `(platform, video_id)` for
    free, before any spend, so the key is already in hand. **Best value here.**
18. **Duplication that has already drifted once.** The FAILED-report
    finalization exists three times (media `fail()`, link `except`,
    `run_pipeline`'s `finally`) — forgetting `report.usage` in one is exactly
    how failed reports used to lose their bill; the fake-seam list is
    hand-synced across three files; the localized-merge logic is
    re-implemented in three renderers (and HAD diverged — fixed in the bot).
19. **Two SSRF host parsers.** `links.allowed_link_host` re-implements
    `trusted_sources.trusted_domain_of`'s fail-closed parsing and they already
    disagree on the hostname charset — two security boundaries to patch when
    the next parser-differential bypass appears.
20. **ASR metering sits at the ffmpeg boundary**, not the ASR provider seam,
    so a future path reaching `transcribe` without `normalize_to_wav` (Sarvam's
    batch API for >30 s clips) would be silently unmetered — while the bill
    still LOOKS complete.
21. **Long downloads share asyncio's default thread pool** with every report
    poll, so a few concurrent link jobs can make finished reports look stuck.
22. **The bot handles messages sequentially**, so one user's 4-minute check
    blocks every other chat, including `/help`.

### Prerequisites already in place

- `.env` holds `ANTHROPIC_API_KEY`, `GOOGLE_FACTCHECK_API_KEY`, `SARVAM_API_KEY`,
  `HF_TOKEN`, `DB_PATH`. Never commit it; `.env.example` stays blank.
- Installed: Python 3.12, git, gh, winget, ffmpeg (Gyan 8.1.2),
  cloudflared 2026.7.3 (at `C:\Program Files (x86)\cloudflared\`),
  `sqlite-vec==0.1.9`, `sentence-transformers`, EmbeddingGemma-300m
  (~1.2 GB cached in `~\.cache\huggingface`).
- NOT installed and not needed by the current stack: Node.js, Docker, psql, Redis.

### To share the demo with people

`.\scripts\share_demo.ps1` prints a `https://….trycloudflare.com` link that works
on any phone. REAL mode spends money per check, so share it privately and Ctrl+C
when done (the link dies with the process). `-DemoMode` gives the same UI for $0
with simulated verdicts.

### Next build step: WhatsApp (or Telegram) bot

Researched 2026-07-25; re-check pricing before relying on it:
- **WhatsApp Cloud API** — a free **test number** allows exactly **5 verified
  recipients** (each confirms a code in the Meta dashboard), and user-initiated
  service replies are free. Needs: Meta developer account → app with the WhatsApp
  product → webhook pointed at the cloudflared URL (re-pasted on every restart).
  A real number additionally needs Meta Business verification (2–7 days).
- **Telegram** — free, and long polling needs **no tunnel at all**, so it is the
  lowest-friction chat demo. User chose to skip it on 2026-07-26 ("maybe later").
- The engine is already surface-agnostic: a bot only needs to call
  `POST /api/v1/verify/text` (or `/media` for voice notes) and poll
  `GET /api/v1/reports/{job_id}` — the exact contract the web page uses.
