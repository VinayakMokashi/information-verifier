# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-09-11**
> (the pivot to a Claude-style answer — see §7).

---

## 0. Where we are right now (read this first)

**The app was rebuilt around a different answer shape on 2026-09-10/11.** It no
longer produces a Truth Report (rating enum + per-claim verdicts + a localized
block). It produces **one prose answer, the way Claude would answer if you
pasted the thing into a chat** — streamed word by word into a clean web page,
with a confidence % and the evidence tier beneath it. See §7 "The pivot" for
why, and what it cost to find out.

**It is also general-purpose now.** Health, science, history, viral claims from
anywhere — not only Indian politics. The trusted list grew from 5 searchable
domains to 45 (58 trusted in total) to make that real: WHO, CDC, NIH, PubMed,
NHS, Cochrane, FDA, EMA, NASA, NOAA, ESA, USGS, Nature, Science, arXiv,
Snopes, PolitiFact, Full Fact, plus the Indian fact-checkers it started with.

**Everything below is built, tested, committed and pushed.** `main` is clean;
**390 tests pass** (`.venv\Scripts\python.exe -m pytest tests -q`, free — every
paid seam is faked).

Working end to end:
- **Text, image, voice/video and pasted Reel/Shorts/Facebook links** all reach
  the same engine, through the same `submit → {job_id} → poll` REST contract.
- **Whitelist first, then the open web.** Pass 1 searches only vetted sources.
  If nothing vetted has covered the claim, pass 2 searches the wider web and
  the answer says so, in its own labelled section, with its own source group.
- **Tier is computed, never claimed** — from `trusted_domain_of()` over the
  API's own citation objects, on every serve path including cache.
- **Streaming** over SSE with sequence ids, `Last-Event-ID` resume and
  heartbeats; the persisted `Answer` stays canonical and the page re-renders
  from it when the stream ends.
- **Spend guards** unchanged: per-visitor and per-deployment rate limits, input
  caps, upload size and duration caps — all enforced before any paid call.
- Every answer carries its own measured bill in `answer.usage`.

**To see it right now (free, $0):**
```powershell
.\.venv\Scripts\python.exe scripts\serve_demo.py     # then open http://127.0.0.1:8000
```
The canned answer streams word by word over the real SSE endpoint, so what you
see is the genuine transport with a simulated Claude behind it.

**⚠️ The pivot has NOT had a paid run yet.** Every cost figure in §8 for the
new engine is *modelled*, and this project's one measured number (`$0.279`,
2026-07-28) came in against `$0.39` predicted — so treat the model as a
starting point, not a fact. Deferred deliberately by Vinayak: "we will do the
paid run once everything is built". It is now built.

**Waiting on Vinayak** — see §11: the first paid run of the new engine, the
AFP whitelist decision, public spend caps, and the first live Telegram message.

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

Give anyone with a phone a fast, trustworthy way to check whether a message,
image, or video is true — with the real answer, in their own language, backed
by sources they can click.

It started India-first and that is still where the need is sharpest: the people
most exposed to misinformation (rural / semi-urban, reading in Hindi, Marathi,
Tamil, Bengali…) are the least served by existing fact-check sites, which are
English-first and desktop-shaped. We bring the check to where the rumour
already is: mobile, and ultimately WhatsApp.

**Widened 2026-09-11 at Vinayak's request:** it is a general-purpose claim
verifier, not a political one. A health rumour, a science claim, a doctored
historical quote and a WhatsApp forward about a politician all take the same
path; only the sources it reaches for differ.

## 2. Principles (these are enforced in code, not slogans)

- **Evidence, not assertion.** What the model *says* about its own searching
  never sets the label. The tier comes from the host of every URL the API
  actually returned, recomputed on every serve including cache hits.
- **Whitelist first, then the open web — labelled.** Vetted sources get the
  first pass. The wider web is a fallback that arrives in its own section,
  under its own heading, with its own source group and a capped confidence.
  Merging the two is how a reader ends up thinking a blog carried a
  fact-checker's authority.
- **Willing to abstain.** "Nothing reliable has addressed this" is a real
  answer, and one the engine gives. Absence of evidence ≠ falsehood.
- **Prose is never a receipt.** The model can write a convincing fake URL.
  Links and confidence come only from structured fields; its markdown renders
  as text — no links, no images, no HTML, on any surface.
- **Cheap at scale.** An answer cache makes cost per-*rumour*, not per-*user*.
- **Machine-read text is shown back.** ASR and OCR guess. A mis-hear must
  never quietly become a confident answer about words nobody said.

## 3. Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| The whole check | Claude **Sonnet 5** (`claude-sonnet-5`), effort `medium`, streaming |
| Vision (OCR) | Claude **Sonnet 5** |
| Retrieval | Native `web_search_20260209` (`allowed_domains`, then `blocked_domains`) + Google Fact Check API |
| Link ingestion | **yt-dlp** (Instagram/YouTube/Facebook extractors only, generic disabled) |
| ASR | **Sarvam Saaras v3** (`saaras:v3`) — `/verify/media` + `/verify/link` |
| Audio/video handling | ffmpeg (normalize to 16 kHz mono WAV, chunk, probe) |
| Storage | **SQLite** (`answers` + `answer_cache`) — no vector index any more |
| Streaming | SSE, in-memory `JobStream` per job (single worker) |
| Async | FastAPI BackgroundTasks (ARQ/Redis still deferred) |
| Frontend | **Self-contained `static/index.html`** served by FastAPI — no Node, no build |
| Public sharing | cloudflared quick tunnel (`scripts/share_demo.ps1`) |

**Dropped in the pivot:** Opus 4.8, Haiku 4.5, EmbeddingGemma,
sentence-transformers, sqlite-vec, and the six per-stage structured schemas.
Startup no longer imports torch — `import app.main` went from ~11 s to 3.4 s.

## 4. How a check runs

```
INPUT
  /verify/text   raw text
  /verify/image  → OCR (Sonnet vision)           ─┐  machine-read text is kept
  /verify/media  → ffmpeg → Sarvam ASR (chunked)  │  in answer.source_text and
  /verify/link   → yt-dlp resolve (inline, free) →┘  SHOWN BACK before the answer
                   caption + (subtitles | capped download → ffmpeg → ASR)

answer cache lookup (exact, NFKC-normalized; key covers prompt + model +
                     effort + whitelist)          → serve, free, $0
  │ miss
  ▼
PASS 1  Sonnet 5, streaming, system = CHAT_SYSTEM_TRUSTED
        tools: web_search with allowed_domains = the vetted list
               (+ Google Fact Check results rendered into the prompt)
        ends with a trailing sentinel:  <verdict confidence="82" trusted="yes"/>

  escalate iff  web_tier_enabled  AND NOT truncated
                AND (the sentinel said trusted="no"  OR  no trusted source was
                     actually cited)
                AND the sentinel did not say trusted="yes"
  │
  ▼
PASS 2  a FRESH request (allowed_domains and blocked_domains are mutually
        exclusive, and tools render first in the cache prefix — nothing is
        reusable), system = CHAT_SYSTEM_WEB, blocked_domains = social media,
        confidence capped at web_tier_confidence_cap

  → sentinel stripped from the visible text (invariant 7)
  → sources built from the API's citation objects; tier from the URL host
  → sections kept SEPARATE per tier
  → persist, cache with a TTL by tier (trusted 7 d, web/none 24 h)

OUTPUT  Answer: prose + confidence + tier + sources, streamed live and stored.
```

Two things that are load-bearing and non-obvious:

- **The sentinel trails, it does not head.** A header line cannot survive
  streaming: the model narrates before its tool calls, so the first text block
  is often "Let me check the fact-checkers." with no newline and no lookahead
  to tell preamble from answer. A trailer needs only a ~60-char hold-back on a
  trailing `<`. Input cannot forge it because `as_prompt_data()` already turns
  every `<`/`>` into `‹`/`›`.
- **`allowed_domains` is all-or-nothing.** One crawler-blocked domain 400s the
  entire request. So the list is split: `CORE_SEARCH_DOMAINS` (crawler-verified)
  and `GLOBAL_SEARCH_CANDIDATES`. On a 400 the engine retries core-only rather
  than failing the check.

## 5. Directory map

```
app/
  main.py            FastAPI app + lifespan (init_db, sweep orphaned jobs)
  config.py          settings: chat model/effort/caps, tier knobs, cache TTLs
  trusted_sources.py CORE_SEARCH_DOMAINS + GLOBAL_SEARCH_CANDIDATES +
                     FACTCHECK_ONLY_DOMAINS + fail-closed trust matching
  api/               routes (text/image/media/link/reports), stream (SSE), DTOs
  models/            answer.py — Answer, AnswerSection, Source, ReportUsage
  engine/            chat.py (the engine), chat_prompts.py, marker.py
                     (sentinel filter), job.py (run_check + cache key)
  providers/         llm (Anthropic), vision (OCR), factcheck (Google),
                     asr (Sarvam Saaras v3), media (ffmpeg), links (yt-dlp),
                     usage (metering + price table)
  store/             SQLite db + repository (answers + answer_cache with TTL)
static/
  index.html         self-contained chat page — streams over SSE, no build step
scripts/
  demo_offline.py    FREE console demo, streams a simulated answer
  serve_demo.py      FREE demo web server (real UI + real SSE, simulated Claude)
  share_demo.ps1     uvicorn + cloudflared quick tunnel (public share link)
  smoke_test.py      REAL one-claim end-to-end check (costs money)
  link_smoke.py      REAL check of a pasted reel link (costs money)
  factcheck_probe.py FREE Google-API-only probe: shows KEEP/DROP per publisher
  link_probe.py      FREE yt-dlp probe: does a Reel/Shorts URL resolve, captions?
  asr_probe.py       Sarvam-only transcription probe (fractions of a rupee)
  telegram_bot.py    the Telegram delivery surface (--check-token is free)
  fake_stages.py     the shared simulated seams (demos + tests)
  render.py          console Answer formatter (+ force_utf8_stdout)
  usage_report.py    one definition of "what did that cost"
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

### Phase 4 — The pivot to a Claude-style answer  ✅ BUILT (2026-09-10/11)
- [x] **New engine** (`app/engine/chat.py`): one streaming Sonnet 5 call,
      whitelist first, open web as a labelled second pass. Trailing sentinel
      for confidence; tier computed from the API's own citations.
- [x] **New model** (`app/models/answer.py`): `Answer` / `AnswerSection` /
      `Source` replace `TruthReport` / `Verdict` / `Claim` / `Evidence`.
- [x] **Streaming** (`app/api/stream.py`): SSE with sequence ids,
      `Last-Event-ID` resume, heartbeats, and replay from the persisted answer.
- [x] **Answer cache** with a TTL by tier, keyed on prompt + model + effort +
      whitelist; the semantic tier deleted (§7 says why, and what it costs).
- [x] **General-purpose scope** (2026-09-11): 5 searchable domains → 45,
      58 trusted; health, science, space, global fact-checkers, governments.
- [x] **Every surface rewritten** to the new shape: the page (a real chat UI),
      the Telegram bot, the console renderer, all four driver scripts.
- [x] **Old engine deleted**: 8 engine modules, 4 models, embeddings provider,
      the vector store, and ~100 tests. Startup no longer imports torch.
- [ ] **The first paid run.** Deferred by Vinayak until everything was built.
      It is built. See §11 item 1.

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
  **Superseded 2026-09-11** — those five are now `CORE_SEARCH_DOMAINS` and the
  searchable list is 45. The all-or-nothing hazard is unchanged; it is handled
  by retrying core-only on a 400 rather than by keeping the list tiny.
- **2026-07-24 — Pipeline no longer swallows claim failures.** A failed claim now
  surfaces as `UNVERIFIED` with the reason instead of vanishing as "no claims found".
- **Rating scale includes UNVERIFIED** so the engine can abstain.
- **Semantic cache deferred to Phase 2** — no embeddings endpoint on Anthropic; Phase 1
  uses exact normalized-text match.

### The pivot: from Truth Report to a Claude-style answer (2026-09-10/11)

**What changed.** The six-stage pipeline (normalize → extract → retrieve →
adjudicate → aggregate → back-translate) and the structured Truth Report are
gone. One streaming Sonnet 5 call — two at most — now reads the message and
writes a prose answer, the way Claude would if you pasted the thing into a
chat. Vinayak's words: *"I want our application to act like a simple claude
chat (not the chat but the answer should be in that format)."*

**Decisions taken at the start, by Vinayak:** whitelist first then open web;
one answer, chat-styled, with a confidence %; a new engine inside the existing
shell (keep the inputs, the SSRF fences, the caps, the metering, the bot, the
free-demo infrastructure); stream on the web page; **Sonnet 5**, not Opus 5.

**The honest cost finding, surfaced before building.** The pivot is not
automatically cheaper. Whitelist-first means the second pass fires on most
fresh rumours (measured on the one real reel: 5 of 6 claims came back
UNVERIFIED), and each search drags roughly 12k input tokens. Modelled at
effort `medium`, a two-pass check costs ~$0.44 on Opus 5 against a $0.279
measured baseline for a whole 6-claim reel — *more* expensive. Sonnet 5 brings
the same two-pass case to ~$0.26, which is why it was chosen. `chat_effort`,
`chat_max_searches_web` and `web_tier_enabled=false` are the levers if it still
runs hot. **The per-search input-token figure is the dominant unknown and only
a paid run settles it.**

**A trailing sentinel, not a header.** See §4 — a header line cannot survive
streaming, and this was established by reasoning about the event shape before
writing any of it, not discovered afterwards.

**Why the semantic cache tier had to go, and what that costs.** Its 0.20
distance threshold was calibrated on *atomic English claims*, and nothing
produces atomic claims any more — whole multilingual messages are a different
distribution entirely. Keeping it would have been serving a cached verdict on
a similarity score whose calibration no longer applied. Deleting it also drops
sentence-transformers, a 1.2 GB model and sqlite-vec. The consequence is real:
the cache is now exact-match only, so a **TTL became mandatory** — "no
fact-checker has covered this" is wrong the day BOOM publishes. Trusted
answers keep for 7 days, web/none for 24 hours.

**Two live traps found while wiring the metering.** `usage.py` had no price row
for `claude-opus-5` or `claude-sonnet-5`, and unknown models fell back to Opus
4.8 — 2.5× wrong for Sonnet. And `messages.stream()` is **not** wrapped by
`usage.instrument()`, which covers only `parse`/`create`; without an explicit
`note_llm()` per request, every bill for the new engine would have read $0.
Both fixed before the first paid call, which is the only time fixing them is
free.

**A deadlock, caught by a hanging test suite.** `JobStream` first used an
`asyncio.Condition`. `follow()` suspends at its `yield` while still holding the
lock, so `publish()` could never acquire it and the whole stream deadlocked.
The lock was not merely broken, it was unnecessary: publish and follow both run
on one event loop and neither awaits between reading and mutating. Removed
entirely, replaced with a list of futures.

**Green tests, broken product.** After the routes switched to `Answer`, four
scripts (`render.py`, `demo_offline.py`, `smoke_test.py`, `link_smoke.py`) were
still importing `app.models.report`, a module that no longer existed — every one
would have crashed on line 1, and CLAUDE.md's free-path table promised those
commands worked. Separately, the Telegram bot's `format_reply` still read
`overall_rating` / `claim_verdicts` / `localized`, so every real reply would
have been the "no checkable claim" fallback after a paid check. **The suite was
green through all of it**, because the bot's tests fed it hand-built Truth
Report dicts and no test imported a script at all.
`tests/test_scripts_import.py` now walks every script's AST and checks each
`app.*` import still resolves, module and name; run against the previous commit
it fails on exactly the three broken scripts.

**A confident badge explaining nothing.** While testing the Telegram length
budget: `'para ' * 3000` is one unbroken 15,000-character paragraph. It fit in
no budget, so the whole answer was dropped and the reply became a
95%-confident badge with a source link and no answer — worse than sending
nothing. Blocks must be droppable, therefore bounded; `_soften()` now breaks
over-long paragraphs at 700 chars on a word boundary. The test that missed it
only asserted the *receipts* survived. It now asserts the answer does too.

**Telegram auto-links bare URLs.** "Render the model's prose as plain text" is
enough on the web page and in the console; it is not enough in a Telegram
message, where a URL the model invented arrives tappable and
indistinguishable from a vetted one. Markdown links and bare URLs are stripped
from the prose on that surface specifically.

**The whitelist grew from 5 searchable domains to 45** (58 trusted in all) when
Vinayak asked, mid-build, for a general-purpose verifier rather than an
India-political one: WHO, CDC, NIH, PubMed, NHS, Cochrane, FDA, EMA, NASA,
NOAA, ESA, USGS, Nature, Science, arXiv, Snopes, PolitiFact, Full Fact, and
national governments, alongside the Indian fact-checkers it started with. The
all-or-nothing `allowed_domains` hazard is what makes this risky — one
crawler-blocked domain 400s every request — so the list is split into
crawler-VERIFIED core and candidates, and a 400 retries core-only rather than
failing the check. **Wikipedia is deliberately excluded**: it is user-editable,
which makes it part of the attack surface rather than a defence against it.

Widening the scope also changed the tests, and this is worth knowing before
"fixing" one: `test_trusted_sources` used to assert that PolitiFact and Lead
Stories were UNtrusted. That was correct under an India-only scope and became
wrong the moment the scope widened. Those assertions were replaced with domains
that will never be vetted, plus new tests that a health, space, Cochrane,
global-fact-checker or non-Indian-government claim now has somewhere vetted to
go. Every security assertion — lookalikes, parser differentials, schemes,
userinfo — was left untouched.

**What was kept deliberately.** Every SSRF fence, the exact-host allowlist, the
yt-dlp extractor pinning, the rate limiter's atomic reservation, the caps
before spend, the `#job=` hash resume, `GoneError` clearing a dead hash, the
factory-not-promise `submit()` guard, and the escape-then-promote ordering in
every renderer. The pivot changed the answer's shape, not the things that stop
it costing money or lying.

## 8. Cost model

> ⚠️ **Everything in the first table is MODELLED, not measured.** The pivot has
> not had a paid run. The one time this project modelled a cost and then
> measured it, the model said $0.39 and the meter said $0.279 — the model was
> 40% high, in the cheap direction. Do not quote these numbers as facts.

- Sonnet 5: **$2 / $10** per million tokens (in / out). (Opus 5 is $5 / $25 —
  the A/B is still worth running once, on a real reel.)
- Web search: ~$0.01 per search (a separate fee), capped by
  `chat_max_searches_trusted` (3) and `chat_max_searches_web` (2).
- Sarvam ASR: **₹30/hour**, billed per second (~₹0.50/min).

| Scenario | Modelled, Sonnet 5 | Modelled, Opus 5 |
|---|---|---|
| Single pass, vetted sources found | ~$0.16 | ~$0.28 |
| **Two-pass (typical fresh rumour)** | **~$0.26** | **~$0.44** |
| Nothing checkable (no search runs) | ~$0.02 | ~$0.05 |
| Exact re-forward inside the TTL | **$0** | **$0** |

- A **link check** adds: $0 when the post has subtitles or the claim is in the
  caption (YouTube Hindi auto-captions measured present) — otherwise the
  clip's audio duration × the ASR rate (a 70 s reel ≈ ₹0.58). Resolve and
  download are bandwidth, not API spend.
- **Pricing is now per SUBMISSION, not per claim.** That is a real change: the
  old pipeline priced a compound sentence as three claims, and a message could
  reach eight. One message is now one answer, and its ceiling is set by
  `chat_max_tokens` and the search caps rather than by how many assertions the
  sender packed in.

**The measured anchor that still stands** (old engine, 2026-07-28,
`scripts/link_smoke.py`): a 6-claim reel report cost **$0.279 all-in**
($0.22 LLM + $0.05 search + ₹0.58 ASR). That is the number the new engine has
to beat, and the first paid run is what will say whether it does.

Metering lives IN THE APP: every answer carries `answer.usage` — tokens per
model from the API's own usage fields, searches, ASR seconds, estimated USD —
so future figures come from answers, not from scripts.

**What bounds the spend** (all in `app/config.py`):

| Setting | Default | Bounds |
|---|---|---|
| `max_checks_per_hour` | 10 | submissions per visitor IP |
| `max_checks_per_day` | 100 | submissions across the whole deployment |
| `max_input_chars` | 5000 | text per submission |
| `chat_max_tokens` | 12000 | output tokens per pass |
| `chat_effort` | medium | thinking effort — `low` is the first cost lever |
| `chat_max_searches_trusted` | 3 | billed searches in pass 1 |
| `chat_max_searches_web` | 2 | billed searches in pass 2 |
| `web_tier_enabled` | true | **set false to skip pass 2 entirely** |
| `web_tier_confidence_cap` | 75 | ceiling on a web-only answer's confidence |
| `max_media_bytes` | 25 MB | upload size (enforced as bytes stream in) |
| `max_media_seconds` | 300 | audio duration (probed before decoding) |
| `answer_cache_ttl_trusted_h` | 168 | 7 days |
| `answer_cache_ttl_web_h` | 24 | 1 day |

⚠️ At the current caps a public link's ceiling is roughly **$26/day modelled**
(100 checks × ~$0.26) — down from ~$99–211 under the per-claim pricing, because
a submission can no longer fan out into eight paid checks. Open decision 2 in
§11 is now a smaller question than it was, but still Vinayak's to answer.

**Always-free**: the whole test suite, `demo_offline.py`, `serve_demo.py`,
`share_demo.ps1 -DemoMode`, `factcheck_probe.py`, `link_probe.py`, and
`telegram_bot.py --check-token`.

## 9. Environment notes (this machine)

- **Repository:** https://github.com/VinayakMokashi/Information_Verifier (private).
  Commit + push after each meaningful change so any session sees the latest state.
- Python 3.12 ✅, git ✅, gh CLI ✅ (authed as VinayakMokashi), winget ✅.
- **ffmpeg ✅ installed** (Gyan.FFmpeg 8.1.2 via winget, on PATH) — the plan
  previously said it wasn't; corrected 2026-07-25 after a local check.
- **Node.js and Docker NOT installed** (also no psql, no redis-server) — and
  nothing in the stack needs them. The pivot removed the last heavyweight
  dependency: no vector index, no local embedding model, no torch at startup.
- Secrets live only in `.env` (git-ignored). `.env.example` stays blank.

## 10. How to run

See [GETTING_STARTED.md](GETTING_STARTED.md). Quick reference:

| Command | Cost | Proves |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests -q` | $0 | everything; every paid seam is faked |
| `.venv\Scripts\python.exe scripts\serve_demo.py` | $0 | the real chat UI + real SSE, simulated Claude |
| `.venv\Scripts\python.exe scripts\demo_offline.py` | $0 | the engine plumbing + cache, in the console |
| `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"` | $0 | which publishers we keep/drop |
| `.venv\Scripts\python.exe scripts\link_probe.py <url>` | $0 | does a reel resolve, and does it have captions |
| `.venv\Scripts\python.exe scripts\telegram_bot.py --check-token` | $0 | the bot token still works |
| `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg` | ~paise | one real transcription |
| `.venv\Scripts\python.exe scripts\smoke_test.py "claim"` | ~cents | one real check, with its measured bill |
| `.venv\Scripts\python.exe scripts\link_smoke.py <url>` | ~cents | a real reel, end to end, with its bill |

- Real server + UI: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
  → http://127.0.0.1:8000  (**one worker** — the stream registry and the rate
  limiter are both in-memory)
- Share publicly: `.\scripts\share_demo.ps1` (add `-DemoMode` for the free variant)

## 11. Open items

### THE TODO LIST (updated 2026-09-11 — the authoritative one)

**Needs Vinayak, not code:**

1. **The first paid run of the new engine.** Everything is built; this is the
   next thing that should happen. Two runs settle every open cost question:
   - a known-debunked claim (should be single-pass, trusted sources found):
     `.venv\Scripts\python.exe scripts\smoke_test.py "Drinking hot water kills the coronavirus"`
   - a fresh rumour with no fact-checker coverage (should escalate to pass 2)
   Then paste `answer.usage` into §8 and replace the modelled table with
   measured numbers. Modelled at ~$0.16 and ~$0.26; the last time this project
   modelled a cost it was 40% high. Budget under a dollar for both.
2. **AFP Fact Check** (`factcheck.afp.com`, IFCN-certified) is still the only
   publisher dropped by the trust filter on live queries. Add it to
   `FACTCHECK_ONLY_DOMAINS` or leave it out? Curating the whitelist is a trust
   decision, deliberately not an automatic one.
3. **Spend caps before going public** — §8: the ceiling is now ~$26/day
   modelled (100 checks × ~$0.26), down from ~$99–211, because a submission can
   no longer fan out into eight paid claims. Lower `max_checks_per_day` anyway?
4. **The first live Telegram message.** The token is in `.env` and validates as
   `@Information_Verifier_bot` (`--check-token`, free, re-run any time). The bot
   has never touched live Telegram. Anyone who messages it spends real money, so
   this wants someone awake and watching: `uvicorn app.main:app` in one
   terminal, `scripts\telegram_bot.py` in the other.

**Worth doing next, in code (value order):**

5. **A transcript cache for links.** One viral reel forwarded by many people
   re-downloads and re-buys the whole ASR every time (~₹0.58 for a 70 s clip) —
   the same "per-user pricing wearing a cache's clothes" inversion the old
   translation cache existed to fix, still open on the most expensive input.
   `resolve_link` already returns a stable `(platform, video_id)` for free,
   before any spend, so the key is already in hand. **Best value on this list.**
6. **A/B Sonnet 5 against Opus 5** on one real reel, once item 1 has a
   baseline. Modelled at $0.26 vs $0.44 per two-pass check — if Opus is
   materially better at spotting "true things made misleading", that gap may be
   worth paying.
7. **Answers are never pruned.** `answer_cache` expires by TTL, but the
   `answers` table keeps every stranger's message indefinitely. `created_at` is
   written and never read.
8. **Two SSRF host parsers.** `links.allowed_link_host` re-implements
   `trusted_sources.trusted_domain_of`'s fail-closed parsing, and they already
   disagree on the hostname charset — two security boundaries to patch when the
   next parser-differential bypass appears.
9. **FAILED-answer finalization exists in four places** (media `fail()`, link
   `except`, and two branches in `run_check`). Forgetting `usage` in one is
   exactly how failed reports used to lose their bill.
10. **ASR metering sits at the ffmpeg boundary**, not the ASR provider seam, so
    a future path reaching `transcribe` without `normalize_to_wav` (Sarvam's
    batch API for >30 s clips) would be silently unmetered — while the bill
    still LOOKS complete.
11. **Long downloads share asyncio's default thread pool** with every report
    poll, so a few concurrent link jobs can make finished answers look stuck.
12. **The bot handles messages sequentially**, so one user's 4-minute check
    blocks every other chat, including `/help`.
13. **`/health` is a constant** — no way to see spend, queue depth, or which
    subsystems are degraded.
14. **A refusal still puts the raw exception text in `answer.error`**
    (`job.py:105`). The generic failure branch is friendly; this one is not.
15. **Facebook `/reel/<id>` URL form is unprobed.** `/videos/` URLs are
    measured working; when a real FB reel link comes along, one free
    `scripts\link_probe.py` run settles it.
16. **WhatsApp bot: deferred, deliberately.** Meta business verification +
    webhook tunnel + 5-recipient test cap. When it happens it reuses the
    Telegram bot's `format_reply` unchanged.

**Closed by the pivot (kept so nobody re-opens them):**
- ~~Verdict word never localized; `RATING_LABELS` showed romanized Hindi to
  Tamil and Bengali readers, in two places~~ — there is no rating enum any
  more, and the answer arrives in the reader's language as prose.
- ~~`aggregate.py` untested; the worst-first roll-up vacuously verified~~ —
  deleted with the pipeline.
- ~~The "a failed claim surfaces as UNVERIFIED" branch never exercised~~ —
  deleted with the pipeline.
- ~~A claim adjudicated while the semantic tier is paused is stored with no
  vector~~ — the semantic tier is gone (§7 says why).
- ~~An embedder cold start freezes report polling for everyone~~ — no embedder.
- ~~`test_devanagari.py` asserts a property of a constant~~ — fixed 2026-09-11;
  it now asserts the page's own escape character class is ASCII-only.
- ~~The localized-merge logic re-implemented in three renderers~~ — no
  localized block exists.

**Settled earlier, kept for the record:**
- ~~Hindi ASR accuracy~~ → 2026-07-28: real Hinglish speech from a reel
  preserved every alphanumeric (₹140, "27th", एफआईआर) — the synthetic TTS voice
  caused the old 5जी loss, not Sarvam.
- ~~/verify/link paid tail~~ → 2026-07-28: $0.279 measured.
- ~~The six public-link blockers~~ → all closed 2026-07-28: citations enforced
  on every serve path, search budget enforced across continuations, evidence
  delimited, CORS wildcard removed, media ASR moved behind the 202, orphaned
  paid reports resumable from the URL hash.

### Prerequisites already in place

- `.env` holds `ANTHROPIC_API_KEY`, `GOOGLE_FACTCHECK_API_KEY`, `SARVAM_API_KEY`,
  `HF_TOKEN`, `DB_PATH`, `TELEGRAM_BOT_TOKEN`. Never commit it;
  `.env.example` stays blank.
- Installed: Python 3.12, git, gh, winget, ffmpeg (Gyan 8.1.2),
  cloudflared 2026.7.3 (at `C:\Program Files (x86)\cloudflared\`).
- Still on disk but **no longer used or required**: `sqlite-vec`,
  `sentence-transformers`, EmbeddingGemma-300m (~1.2 GB in
  `~\.cache\huggingface`). Dropped from `requirements.txt` in the pivot;
  safe to delete the cache if the disk space is wanted.
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
