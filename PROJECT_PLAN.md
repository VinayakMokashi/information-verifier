# Information Verifier — Project Plan & Progress

> **This file is the single source of truth.** Any new work session (human or AI)
> should read this first to understand what we're building and exactly where we are.
> Keep it updated as the project moves. Last updated: **2026-10-18**
> (the public launch is built and reviewed twice; going live waits on the
> owner's steps — §0, §7, §11 A; HANDOFF.md §0 is the resume point).

---

## 0. Where we are right now (read this first)

**Right now (2026-10-18):**
- **The public website/app is built.** Steps 1–3 and 5 of the decision
  brief's build order are done, pushed and reviewed twice (§7, 2026-10-15
  to 2026-10-17). The step-5 reviews alone found 31 defects, all fixed.
- **Step 4, running it 24/7 on this PC at its own .com, waits on
  Vinayak's owner steps** in `docs/go-live.md`.
- **1333 tests pass.** A fresh reviewer for the third round of fixes
  found 8 low defects, all fixed the same day (§7, 2026-10-18); it
  judged the first real start safe. The app and the bot have not
  run since 2026-10-12, and the ledger stands at $1.7437.
- Everything built since 2026-10-11 has met only fakes and test keys,
  never real money.

HANDOFF.md §0 has the owner's list and the next steps in order.

**The new engine has now run for real (2026-09-22) — and it works.** One
prose answer per submission, the way Claude would answer if you pasted the
thing into a chat, streamed word by word, in the sender's language, with a
confidence % and the sources underneath. General-purpose: health, science,
history, politics — not only Indian political rumours.

**Measured, not modelled** (§8 has the detail):

| Check | Cost | Time |
|---|---|---|
| Known-debunked claim, one pass, fact-checkers found | **$0.048–0.061** | 28–51 s |
| Fresh rumour, two passes (whitelist, then open web) | **$0.150** | 57 s |
| Real reel (PEEK TV), Sonnet 5, one pass | **$0.082** + ₹0.58 ASR once | 34 s |
| Exact re-forward inside the cache TTL | **$0** | instant |

The model said $0.16 and $0.26; reality came in 2–3× cheaper. Sonnet 5 beat
Opus 5 on the same reel — right where Opus was wrong, at a quarter of the cost
(§7, 2026-09-22).

**Safety settings in force** (Vinayak, 2026-09-22; the budget 2026-10-15):
- **$1 a day**, deployment-wide — web page and Telegram bot share it. Each
  check reserves its kind's worst case and settles at its real cost; the
  day gets cheaper as it drains; 40 checks a day at most, as a backstop
  (it was a count: 2 a day, then 5 from 2026-09-29).
  Persisted in SQLite, so a restart cannot refill it; resets at midnight
  India time; a check served free from cache gives everything back.
- **Per person:** one check at a time (3 at once per IPv4 address) and 10
  an hour. Per day: 5 paid checks per Telegram user (and per WhatsApp
  number, to come), and 3 per web device, by the signed cookie a
  Turnstile pass earns (since 2026-10-16). Without a cookie, a visitor
  counts by address: 5 per IPv6 /64, 20 per IPv4 address (§7, 2026-10-16).
- Messages are deleted after **30 days**; what they cost is kept, with no
  content, in a spend ledger.
- A **spending dashboard** at `http://127.0.0.1:8000/dashboard` — this
  machine only (a 404 to anyone else, including through the share tunnel).

**Everything below is built, tested, committed and pushed.** `main` is clean;
**1333 tests pass** today (688 on 2026-09-22;
`.venv\Scripts\python.exe -m pytest tests -q`, free — every paid seam is
faked).

**Reviewed adversarially the same evening, twice:** two independent reviews
of the day's work found 13 defects — among them a trust-label bypass, a
DNS-rebinding hole in the dashboard, four ways the verdict tag could reach a
reader, and the daily cap leaking at midnight. Two more reviews of those
FIXES found 15 further defects, five of them introduced by the fixes
themselves. Every one was reproduced with a free script and fixed with a
test that fails against the old code (§7). **747 tests.**

Working end to end:
- **Text, image, voice/video and pasted Reel/Shorts/Facebook links** all reach
  the same engine, through the same `submit → {job_id} → poll` REST contract.
  Facebook share links (`facebook.com/share/r/...`) verified on real posts.
- **Whitelist first, then the open web** — 43 searchable domains, 57 trusted,
  every one verified against the live API (`scripts/crawl_probe.py`).
- **The label is evidence**: a "fact-checked" label needs a trusted URL the
  API returned, and the model's own "nothing trusted addressed this" lowers
  it. The source list shows what the answer rests on, not every raw result.
- **Streaming** over SSE; the persisted answer stays canonical.
- **Caches**: answers (exact match, TTL by tier) and link transcripts (by the
  platform's video id — a reel is transcribed once, not once per forward).
- **The Telegram bot** handles chats concurrently; one chat cannot pay twice.
- Every answer carries its own measured bill, split into Claude / search / ASR.

**To see it right now (free, $0):**
```powershell
.\.venv\Scripts\python.exe scripts\serve_demo.py     # then open http://127.0.0.1:8000
```

**2026-09-29: the Telegram bot is LIVE** — first real messages from
Vinayak's phone; the summary and the language chooser both ran against the
real model and worked (§7). Failed searches are now recorded per check,
and the cap is 5 a day. Found and fixed: the free test suite had been
refilling the real daily cap one slot per run (§7). **2026-10-10:** a
one-click launcher, `start.cmd`. **2026-10-11: three cost cuts, measured**
(§7) — a claim Google's free fact-check database already covers now costs
**$0.0084 in 6.7 s** (was ~$0.05 and 28–51 s); pass 1 says "not covered" in
one sentence instead of an essay; "hi" costs nothing. **2026-10-15:** no
credential reaches any printed line (§11 17 closed, and the bot token's own
leak through error text); translated Hindi lookups measured.
**2026-10-15/16: the pre-public blockers are fixed** — per-person limits,
the $1-a-day budget that gets cheaper as it drains, no cross-site paid
checks, no oversized-post freeze — and reviewed twice (§7). Later on
2026-10-16: checking pauses at no cost when Anthropic refuses for money,
the dashboard shows the day's money, and a web visitor's check needs a
Cloudflare Turnstile pass, which earns the device cookie that carries 3
checks a day (§7). Step 3 — restarts, the ledger, monitoring — the same evening.
Step 5 that night: a privacy notice and terms that read their periods from
the code's own settings, an AI line on every answer on every surface, the
bot's /privacy and /delete, a deletion tool for the owner, and an
installable app; drafting the notice against the code found the limiter
keeping visitors' addresses for weeks, and the bot billing unknown
commands as claims (§7). Its review found 18 more, all fixed the same night;
step 4 is ready for the owner (`docs/go-live.md`, `scripts/serve_forever.py`).
A re-check of those fixes found 13 more (2026-10-17), all fixed. **1316 tests.**

**Next** (2026-10-17; the goals were agreed 2026-10-11):
1. **Step 4** of going public. It is Vinayak's owner steps in
   `docs/go-live.md`; Claude checks and fixes what the first real run
   shows.
2. **The WhatsApp bot** (§11 B). His slow applications can start now.
3. **The remaining to-dos** (§11 C), in HANDOFF §6's value order.

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
- [x] **The first paid run** — 2026-09-22: $0.048–0.061 single pass, $0.150
      two-pass, $0.082 for a real reel; Sonnet 5 beat Opus 5 (§7, §8).

## 7. Decisions & findings log

*Newest first. This is the "why", and the most useful section to skim before
changing anything — several entries record measurements that overturned an
obvious-looking design.*

### 2026-10-23 — Going live, §1: the owner's settings, and three things the dashboards did not say

Vinayak worked through go-live.md §1, with each result read back, free.
- **Sarvam has no switch for this app's retention.** The docs describe
  "Data retention" with a Model APIs → "No retention (0 days)" override.
  His account's workspace page is "Data policy", with only Voice Agents.
  Organisation → Policy holds only encryption keys. So
  `SARVAM_ZERO_RETENTION` stays unset (the notice keeps saying Sarvam
  may keep voice notes, which is true). He emailed Sarvam support.
- **Anthropic:** a new workspace with a monthly spend limit, and a key
  bound to it.
  - The app sends no `anthropic-workspace-id` header, so an unbound
    key would fail every check with a 400.
  - Verified free: a models list returned HTTP 200 in
    `wrkspc_01VYAydX915BB2PdCgkXE7Zh`.
- **BACKUP_DIR** points to OneDrive; **CONTACT_EMAIL** (a Gmail
  address) and **OPERATOR_NAME** are set. All were checked without
  printing their values.
- **This PC:**
  - sleep on AC is Never; the lid on AC does nothing;
  - active hours are 7–1, set manually;
  - updates are paused until 2026-10-30;
  - it signs in with a **local account**, so the scheduled task in §5
    needs that account's password.
- **"Device encryption: On" was not protection.** `manage-bde -status
  C:` said Protection Off, Key Protectors: None Found. The key sits
  unsecured beside the data, which is why no recovery key ever existed.
  **Vinayak decided to leave it off until the VM** (§11 29), with
  Telegram's at-rest term a known gap.

The lesson, a fourth time: a settings page's word is not a
measurement. Sarvam's docs and its dashboard disagreed, and Windows'
"On" meant unprotected. Each was settled by reading the real state.

### 2026-10-18 — A fresh reviewer for the third round: the first start is safe; 8 low findings, all fixed

Vinayak took two of the three offers: a fresh reviewer, and one real
local check, which waits for go-live §1's new key. A reviewer who had read
none of 1ae3cc3..09dc74d attacked them, for free, in a `git archive`
extract with no `.env` and no real data
([review-fixes-round3.md](docs/research/2026-10-18/review-fixes-round3.md)).

**The first real start since 2026-10-12 is safe.** It runs the one-time
VACUUM, the sweep and the 30-day prune. It was measured on a synthetic
database that the 2026-10-11 code built in the real file's state: an
inert vec0 entry, an empty WAL, a stale -shm. Startup took 1.0 s and the
integrity check passed. With a reader open, the start succeeded and
the rewrite was redone next time. Two claims were re-checked by hand:
uvicorn 0.51 runs the lifespan before it binds, and the bot never opens
the database. **go-live.md §5 is correct**, checked against
cloudflared's source at the installed 2026.7.3.

**8 findings, all low; five more fixes that covered only their named
case.** All fixed, each pushed alone (the table at the end of the
review):
- G-8 (82b0708) is the real one. MEASURED on this PC: `os.replace`
  onto a file written a moment ago is refused ("access denied") on
  631 of 1,000 back-to-back writes, 12 of 60 half a second apart, and
  once in 20 even 2 s apart, in this project's folder. The bot
  swallowed it, so a restart could re-deliver an answer or lose a
  check. Retried at 10–200 ms, 860 of 860 landed (median 2 ms, worst
  451 ms). A save that never lands is rewritten at the next poll.
- G-2 (6eb2e57): a housekeeping step that raises now alerts the
  owner. The fallback account gets BACKUP_DIR.
- G-4 (4838389): the stop file is consumed once the stop is done. A
  second flake in its test was MEASURED, not guessed: **a CTRL_BREAK
  sent within moments of a start never reaches the child** (12 of 12;
  the venv launcher has not started the interpreter yet), so the bot
  was killed at its 15 s grace every time. Resending is no fix, because
  uvicorn force-exits on a second one. The test now waits for both
  children to be up (0.8 s, was 15–30 s).
- G-5 (aaf5398): forget.py's "run the same command again" now
  finishes the file.
- G-1 (f9fd678): find_db_copies lists every database of this
  project's schema, whatever its size, and orphaned WALs.
  - Run on %TEMP% (the real file only stat'ed, never opened): **284**
    synthetic and demo databases from earlier sessions' reviews,
    probes and tests. None is the real file's size, and the largest is
    274 KB against its 1.27 MB.
- G-3 (486a795): working files per process id; a start clears only
  dead processes' folders.
- G-7 (7f35db8): both main()s are run by tests now. Mutants M13–M15
  are caught.
- G-6 (ea2e82c): under the runner the app contains itself, so its
  ffmpeg dies with it. The job code moved to `app/processes.py`.

**How the suite ran this time:** each fix was committed locally, and
the full suite ran on exactly that commit in a git worktree in scratch
(no `.env`, no data) while the next fix was written. Then it was
pushed. A background command's "exit code 0" is its last pipe's, so
pytest's own code was read from the `FULL_PYTEST_EXIT=` line it printed.

### 2026-10-17 — The fixes re-checked: 13 more, all fixed

A second adversarial pass
([review-fixes-step5.md](docs/research/2026-10-16/review-fixes-step5.md))
covered the step-5 fixes and step 4's two never-reviewed pieces. It found
13 (4 medium, 9 low). The lesson held a third time: six were fixes
covering the case they named but not its rule. By theme:

- **Copies of people's data (F-1, medium).** My S5-10 clean-up searched
  by name and folder, and missed two more full copies of the real
  database: one in %TEMP% itself (via tempfile's default), one named
  `*.before-upgrade`. They and seven stale old-schema databases are
  deleted. `scripts/find_db_copies.py` now finds copies by header and
  table names, and deletes nothing.
- **The owner's runbook would not have worked (F-5, F-10, medium).**
  - The cloudflared service, installed as written, runs NO tunnel. The
    registry ImagePath edit is now in the runbook, from Cloudflare's own
    page and cloudflared's source.
  - A fallback service account could not reach Python or ffmpeg in the
    owner's profile.
- **The bot's promise (F-12, medium).** Its /privacy still said
  "deleted after 30 days" unqualified. It now takes "our copy" and the
  Sarvam line from the same switch as the web notice.
- **The runner (F-4, F-8).**
  - ffmpeg escaped the job in about half of cold starts: the supervisor
    now joins its job first.
  - No orderly stop was possible under Task Scheduler. A stop file now
    lets checks in flight finish.
- **The bot (F-2, F-6, F-9).**
  - A chat's mark outlived its day when another chat's write expired it.
  - After a restart, a message during the hand-over was paid for (found
    by the reviewer's extended explorer, now
    `scripts/bot_explorer_restarts.py`).
  - Two bots could run. There is now one lock.
- **The store (F-3, F-7, F-11, F-13).**
  - The demo's start emptied the real app's working files.
  - The WAL truncate stalled every write ~30 s behind a reader, then
    lied.
  - The one-time VACUUM could fail a start.
  - A restore plus a sweep counted $0.16 as $0.32.

All fixed by 09dc74d. Each test failed first, mutants were caught, and
6,000 explorer seeds ran clean. 1316 tests.

### 2026-10-16 (late night) — Step 5 reviewed: 18 findings, each reproduced, all fixed; step 4 made ready

An adversarial review of step 5
([review-step5.md](docs/research/2026-10-16/review-step5.md)) found 18
defects: 7 medium, 11 low, 16 of them reproduced. **Five were my own
fixes** that covered the case they named and missed the rule behind it
— 2026-09-22's lesson, again. By theme:

- **The notice promised what the code did not do:**
  - Sarvam's zero retention. It is now a switch the owner throws after
    the dashboard change (ebbe0aa).
  - "At most a day" for the bot's pending file. It now expires while
    the bot runs (df14115).
  - Who asked, held after the day: the bot's locks (df14115), and the
    limiter around midnight (2e4562c).
  - Deleted bytes left in the file and the WAL. Fixed with
    secure_delete, a WAL truncate, and one VACUUM at the next start.
  - Job ids in the "content-free" backups. They now carry a one-way
    reference.
  - An answer replayed from memory after its deletion.
  - Voice notes left in %TEMP% by a hard stop. Work now goes in
    data/tmp, emptied at startup.
    (The last four: 344ef13.)
  - Two overstated sentences (ae85077).
- **The deletion tool could not find, or over-deleted:**
  - a reel could not be found, because the stored message was
    overwritten; run_check now keeps what was sent;
  - a pasted #job= address matched nothing;
  - a cache repeat saved twice, undoing a deletion;
  - one viral forward was deleted for everyone who sent it.
  (All ed88772.)
- **The bot (df14115):**
  - "/privacy?" and "/stop." were still PAID checks;
  - claims starting "/startup…" were eaten as help;
  - "Hi" plus a claim left the claim unchecked;
  - "/status" stopped delivering a waiting answer;
  - the public bot had no contact warning.
- **Copies of the real database** in Claude's scratch folders: three,
  one mine from the deletion tool's dry run. All deleted. CLAUDE.md now
  says a real copy is deleted when its measurement ends (300f375).

The interleaving explorer from 2026-09-22 turned up in an old scratch
folder. It is now `scripts/bot_explorer.py`, free.
- Before the bot fix, over 300 seeds: chat locks kept in 291,
  "prompted" without a pending answer in 3, and a "hi" left
  unanswered in 13. That last one predates step 5 and is fixed too.
- After the fix: 2,000 seeds, no violations.

**Step 4, ready for the owner:**
- `scripts/serve_forever.py` (8a15b30) runs the app and the bot with
  nobody signed in:
  - it restarts either one with doubling pauses;
  - it logs to logs/;
  - its children die with it, through a Windows job object;
  - children get UTF-8, because piped, the first Devanagari print
    would kill the app.
  Measured on a real uvicorn: a graceful CTRL_BREAK stop in 0.2 s.
  Exit code 3 turned out to mean several things, so the code no longer
  reads it.
- `docs/go-live.md` (800d26c, kept current since) is the owner's half,
  as exact steps, each with its check.

**For Vinayak to know:** the next app start rewrites the real database
once (VACUUM). It is lossless and logged, so nothing deleted earlier
lingers in the file.

### 2026-10-16 (night) — Step 5 of the launch: privacy notice, terms, the AI line, deletion, an installable app

Drafted from [policy-legal.md](docs/research/2026-10-15/policy-legal.md)'s
recommendation as its verification corrected it, and then checked claim by
claim against the CODE, not the research. That second check is where the
findings came from:
- **The limiter kept visitors' addresses in memory for weeks** (60beff7).
  A subject's hourly record left only when 512 others pushed it out or the
  server restarted. `forget_idle()` drops what the limits already ignore,
  from the 6-hourly housekeeping loop; no decision changes (four mutants
  caught).
- **The bot billed unknown commands as claims** (bb623ae). MEASURED:
  "/privacy", before the bot knew it, reached the API as a PAID text
  check: one word passes the small-talk triage. A bare unknown /command
  now gets the help text. Also: "/id" arriving with a claim made the claim
  look sent mid-check, so it was never checked; instant commands are no
  longer counted as work in flight.
- **The answer cache holds the message too**, and an answer page opens
  for anyone holding its `#job=` address. Both are now stated in the
  notice.

What was built:
- dfb16b7: `/privacy` and `/terms` are served by `app/api/legal.py`
  (single-pass fill since 69e7d6d), not from static/. The periods they
  state are read from the settings the deleting code reads, and the tests
  move those settings.
- The page: "I'm an AI (Claude), and I can be wrong — open the sources
  before you rely on an answer. For ages 18+", beside Check, and
  "AI-written" on every answer.
- bb623ae (the bot): the AI line on EVERY answer (a Telegram chat never
  starts a new session, and Anthropic's policy asks for the disclosure
  per session), /privacy, and an honest /delete.
- 4806194: `scripts/forget.py` honours a deletion request. The notice
  promises one, and without a tool that promise meant hand-written SQL.
- 767d44f: the installable app.
  - Manifest, icons drawn by `scripts/make_icons.py` in headless Chrome,
    an Install button, and an iOS hint.
  - A GET share target that only fills the box.
  - No service worker: none is needed to install, and one would serve a
    stale page after deploys.
  - Headless Chrome over DevTools reported no manifest errors and no
    installability errors. A shared reel link filled the box and sent
    nothing.

Decided here (mine; Vinayak can overturn any):
- **What to publish as the operator's name and contact is his decision.**
  It lives in `.env` (`OPERATOR_NAME`, `CONTACT_EMAIL`), never in the
  repo. Until set, the pages say a contact comes before launch, and a
  public deployment warns at startup.
- **18+ is a line beside the button, not a checkbox.** It is a
  self-declaration either way; DPDP's child rules start 13 May 2027; and a
  box ticked before every check is friction for nothing. Revisit with the
  2027 rewrite.
- **Telegram /delete tells the truth.** Once an answer is delivered,
  nothing ties a chat to its message, so the bot cannot find it to delete.
  The person writes to the contact, and the owner runs `forget.py`.

Go-live preconditions this adds (HANDOFF §0):
- `CONTACT_EMAIL`;
- Sarvam's retention set to 0 days. The notice says "Our Sarvam account is
  set to keep none of it", which is true only once it is set;
- the privacy policy URL set in @BotFather.

**A DECISION RECORDED NOW, NEEDED BEFORE 13 MAY 2027 (Vinayak's):**
- DPDP Rule 8(3) requires every Data Fiduciary to keep "such personal
  data, associated traffic data and other logs of the processing" for at
  least one year from processing. Rule 6(1)(e) adds a second one-year duty
  for security logs. The verification read Illustration Case 1 as keeping
  the personal data itself, "even if X deletes her account".
- That collides with invariant 10 (messages deleted after 30 days), with
  the notice's own promise, with `/delete`, and with Telegram's bot terms
  §4.2(a) (delete on request).
- The options:
  - keep message content for a year (breach impact up, and the notice
    must say so);
  - keep only a content-free processing log, beside the ledger, on the
    narrow reading of "such personal data" (legally uncertain);
  - take advice in early 2027, then choose.
- Nothing changes before 13 May 2027. The notice already says it will be
  rewritten before then.

### 2026-10-16 (evening) — Step 3 of the launch: restarts, the ledger, monitoring

The ops audit's findings ([audit-ops.md](docs/research/2026-10-15/audit-ops.md)),
each reproduced first, fixed test-first, measured:
- **A check always ends** (OPS-06, b7d4ced): the finishing save is retried,
  the ledger row written even if it fails, the stream ALWAYS closed with the
  truth; a 5-minute sweep fails rows stuck mid-flight that no stream here is
  still on. **A killed check still lands in the ledger** (OPS-04, 2b5a261):
  its bill so far is checkpointed onto its row (a conditional write that can
  never overwrite a finished answer), and the sweeps write its ledger row.
- **One server per database** (OPS-05, 32462f1): an OS lock beside the
  database, taken before the startup sweep. Two real uvicorn processes on
  one database: the second printed why and exited 3; the first went on.
- **A restarted bot delivers what it was waiting for** (OPS-07 + R12,
  0ba4f62): pending checks persist in `data/bot_pending.json`.
- **/ready** (OPS-18, d65638f): a database write and read on the /reports
  pool within 3 s, the key, ffmpeg, real|demo — the bot refuses the demo.
- **Logs** (OPS-11/08/20, 7f97c0e): no access log (it printed visitor IPs and
  job ids, and a job id opens that person's message), platform errors
  scrubbed of URLs and post ids, `--workers 1` explicit, output
  line-buffered (piped, the startup line had not arrived after 20 s).
- **Backups** (OPS-10, 2581d1e): daily, of the CONTENT-FREE tables only. The
  audit suggested full copies kept 30 days — but a full copy holds messages,
  so a 30-day-old copy would keep one for 60 and break the 30-day promise.
- **A lock file** (OPS-24, a66cf5e): 29 exact packages, written from the
  installed metadata — `pip freeze` would have locked torch and the rest of
  what the pivot dropped, still in this venv. A brand-new venv built from it
  passed the whole suite. **yt-dlp** (OPS-25, 6c74d76) stays out of the lock;
  its warnings now reach the log once each; startup says when it is stale.
- **Owner alerts on Telegram** (OPS-19, d30e27e): paused for money, budget
  low or spent, 3 failures in a row, a restart or sweep that failed checks.

Owner decisions this raised (HANDOFF §0): update yt-dlp (58 days old);
install deno for YouTube; set OWNER_CHAT_ID and BACKUP_DIR.

### 2026-10-16 (later) — Paused for money; the money on the dashboard; Turnstile and the device cookie

- **A refusal for MONEY pauses checking, and costs nothing** (f545885). A
  spend limit, the tier's monthly cap, a billing problem or an empty
  balance fails every check until someone pays, and "failed requests aren't
  charged" (Anthropic's billing article). Before: a spend-limit 400 was
  taken for a whitelist rejection and retried, the open-web pass tried
  again, the reader was told "try again in a few minutes", and each such
  check KEPT its reservation, so a handful drained the day's $1 and a
  top-up would still read "budget used up" until midnight. Now: one call;
  "Checking is paused for now. Please try again later"; the reservation
  settles at the recorded cost (slot and allowance back at $0); new paid
  checks get 503 up front for 10 minutes, then one probes; cached repeats
  stay free; the console names Anthropic's reason. Reviewing it found its
  own flaw (dbd5f08): an answer already streamed was failed as "paused";
  now it is kept, marked cut short, never cached.
- **The dashboard shows the day's money** (42d1dd9): "$0.72 of $1.00", what
  it still buys, "Paused", the 40-check count as a backstop note — and its
  reads moved off the event loop. The test's first draft timed /health
  in-process and passed AGAINST the bug: a blocked loop runs nothing else,
  the test's own timer included. It now measures the loop's own lag
  (1.04 s before, under 0.5 s after).
- **Turnstile and the device cookie** (b6daec5, f724156, b79bb2a), as
  decided: a web visitor's paid check needs a Cloudflare Turnstile pass,
  verified BEFORE any slot, money or place in line is taken; a pass earns
  the signed `vd` cookie, and the device is the person — 3 checks a day.
  The bot and this machine are never challenged. The cookie's HMAC key is
  made fresh at each start: the counts it keys live in memory and reset on
  restart anyway, so a persistent key would buy nothing. Cloudflare's test
  keys were read off its own page, not remembered. Run end to end in REAL
  headless Chrome against Cloudflare's real siteverify with the test
  secret (free): two checks, two fresh tokens, siteverify True twice, one
  device counted twice. **Lesson: `--virtual-time-budget` races a third
  party's own timeouts** — the widget errored under it; the harness now
  holds the page's load event open on an image the scratch server answers
  when the driver is done, in real time. (A later failure was simply the
  network being down — the script "couldn't load" — read before fixing.)
- Going live needs `PUBLIC_HOSTS` and both Turnstile keys in .env
  (HANDOFF §0); startup warns about the second.

### 2026-10-16 — The pre-public blockers fixed; the fixes reviewed; the review's fixes re-checked

Built in the brief's order, each test-first (the commit messages carry the
measurements):

- **One 25 MB text post froze the whole server** (50dcf3b): the only body
  cap was the upload one, the triage walked every character ON the event
  loop, and the refused post was refunded — free to repeat. Real uvicorn:
  /health frozen 6.3–9.6 s → at worst 0.6 s. Non-upload routes cap at
  64 KiB, chosen by PATH (Content-Type is the client's word).
- **Other websites could submit paid checks through their visitors**
  (1080d2d): multipart is CORS-"simple", so no preflight ever asked. In
  real headless Chrome the vision call ran and a slot was taken → nothing
  paid. `RefuseCrossSite` reads Sec-Fetch-Site / Origin; a request with
  neither (the bot, curl) is not from a page and passes.
- **Counted per PERSON, not per connection** (020e26f): every Telegram user
  was one bucket — the bot, on 127.0.0.1. The bot now names the person
  (honoured only from this machine, `app/api/local.py`); web visitors are
  an IPv6 /64 or an IPv4 address. One check in flight per person.
- **Daily allowances** (55d3de0): Telegram 5, WhatsApp 5, web device 3 (the
  Turnstile cookie, to come), IPv6 /64 5, IPv4 20 (carrier NAT) — in
  memory only, so who someone is never reaches the disk.
- **The $1-a-day budget** (20e882d): each check reserves its kind's worst
  case (text $0.20, image $0.25, reel/voice $0.30) in ONE conditional
  statement and settles at its real cost; the 5-a-day count became a
  40-a-day backstop. Checked on a copy of the real database first.
- **Cheaper as the day drains; repeats free** (0951150): under 40% left, no
  open-web pass; under 15%, text only — a published fact-check or an honest
  "budget used up", never cached (measured: without that rule it WAS).

**A reviewer agent then attacked those fixes** and reproduced 15 issues
([review-blockers.md](docs/research/2026-10-15/review-blockers.md)). The
worst, R1: five visitors whose slow links were refused held all five daily
slots and told everyone "try again tomorrow" — so a claim now has two
phases, *admit* before any free work (only the person's place in line) and
*fund* right before the first paid step (5f8e7db; 5 of 5 slots held → 0).
R15: the limiter held its lock across SQLite writes while the event loop
took the same lock — under another writer, /health 7.02 s → 0.02 s
(3bd7772). Fixed: R1–R3, R6, R9, R11, R13–R15; later the same day R4
(456701b), R5 (786c046), R7 (478a2c1) and R8 (ba0653e). Deferred: R10,
R12 (§11 25–26).

**Re-running the reviewer's own scripts against those fixes found five
more** — "review the fix", again:
- **R11 survived its own fix** in the old call shape: `release(subject)`
  with no token still freed the OLDEST entry. The token is now required
  (2147412).
- A cancelled claim's rollback ran **on the event loop** when the claim had
  already finished — `add_done_callback` then runs inline (4f6be5c).
- A second cancellation left a person "in flight" for 15 minutes; the
  reviewer had called it moot (56c3990).
- A link cancelled while its money was being reserved had no test at all
  (f4f00b1).
- **The "free" suite held all five REAL keys** (dc3ebd4): 8 link and voice
  tests passed only because .env had a real Sarvam key, and any seam a test
  forgot to fake would have reached a provider with a key it bills. Dummy
  keys now come before the app is imported; 982 pass on a copy with no .env.

**Lesson: a harness written for one version silently stops testing the
next.** Three of the reviewer's scripts raised inside their own stubs (a
one-argument `release`) and printed BAD on every row, and the cancellation
script could no longer reach the path it was named for. Read what a re-run
printed before trusting either verdict, and when the code moved, adapt a
copy of the harness rather than the conclusion. And prove a new test
against a mutant while watching for a hang: f4f00b1's first draft spun
forever when the request ended before reaching the code under test.

### 2026-10-15 (later) — How it goes public: Vinayak's four decisions

From the brief ([docs/research/2026-10-15/decision-brief.md](docs/research/2026-10-15/decision-brief.md)),
itself built from verified research and two reproduced code audits in the
same folder:

1. **Where: this PC now, behind a Cloudflare NAMED tunnel; a cloud VM
   (AWS Lightsail Mumbai, ~₹730/month) later**, when uptime starts to matter.
   cloudflared runs on the VM too, so the move is a copy of the setup. Why
   the PC first: ~₹115–425/month all-in (domain + electricity) against ~₹730,
   and reel links keep working — YouTube blocks datacenter IPs at the very
   first request (verified, `ytdlp-cloud-ips.md`); on the VM they would need
   link traffic routed home or a residential proxy with its own byte budget.
2. **Budget: a $1-a-day ceiling** (~₹2,600/month at most; ~15 checks a day
   at the measured mix, ~8 on a day of fresh rumours), as a DOLLAR budget
   replacing the 5-checks count: reserve a check's worst case, settle at
   its real cost, get cheaper as the day drains (skip the open-web pass,
   then only cached and fact-check-shortcut answers), repeats free even at
   zero. Per person: 3 a day per web device (a cookie issued only after
   Cloudflare Turnstile), 5 per Telegram user, 5 per WhatsApp number; one
   check in flight per person; nobody more than a quarter of the day.
   Outside the app: a separate Anthropic workspace with a monthly spend
   limit, prepaid credits with auto-reload off, Sarvam prepaid with 0-day
   retention.
3. **The bot: open to anyone, 5 checks a day each** — chosen over the
   recommended owner-only-until-launch. Until the per-person limit exists,
   the bot stays as it is (it is not running); building that limit is first.
4. **Domain: a .com through Cloudflare Registrar.** Its billing requires 3D
   Secure on Indian cards and lists no RuPay/UPI (verified); if the card is
   declined, any registrar works with Cloudflare's nameservers.

**Build order** (brief §6), each step test-first, committed, reviewed:
the five reproduced blockers → the dollar budget, per-person limits and
Turnstile → restarts, the ledger and monitoring → running 24/7 here (the
domain, cloudflared as a service, auto-start) → privacy notice, terms, the
installable-app manifest → then WhatsApp, whose §4.7 AI-provider risk is
settled before anything is paid for.

### 2026-10-15 — Before any public URL: no secret in any printed line

Vinayak asked for the website/WhatsApp/to-do plan (§11 A–C), choices laid
out before anything is built. The fixes every option needs came first:

- **§11 17 closed** (e4a9822). Every credential field is `repr=False,
  exclude=True`; plain `str`, not `SecretStr`, because the providers, the
  demo's key-blanking and dozens of tests assign plain strings. The test
  pins the rule by field NAME, with a guard that the pattern still finds
  the five known keys (a pattern matching nothing would pass vacuously).
  Failed first: 25 leaks — 5 keys × repr/str/format/model_dump/json.
- **The bot token leaked the same way** (63f8049), found by reading for
  the rule rather than the instance: every Bot API URL carries the token,
  an httpx status error's text IS its URL, and the submit catch-all printed
  it. Anyone could trigger it — Telegram refuses `getFile` over 20 MB.
  `TelegramClient._check` raises without the URL (directly, so no chained
  original shows it; still an `httpx.HTTPStatusError`, which the poll loop
  retries on). The failing run printed exactly the predicted line.
- **And the advice that came with it was wrong** (9a737bd): after that
  refusal the person was told "try again later", which can never work.
  `file_size` arrives with the message, so an over-limit file is answered
  at once with what to send instead — no download, no slot.
- **Measured, free: translating Hindi/Hinglish forwards to English more
  than doubles Google fact-check matches** (3/12 → 7/12) — §11 20.
- PowerShell 5.1 splits a `git commit -m` here-string at embedded double
  quotes (the first commit attempt failed with "pathspec … did not match");
  commit messages go through `git commit -F <file>`.

### 2026-10-11 — Three cost cuts, each measured; and a second test-isolation leak

Vinayak: "I want us to try to reduce the costs." The profile first (ledger,
8 real checks, $0.99): cache writes 32%, web searches 28%, output 25%,
cache reads 9%, fresh input 4%, ASR 2%. **Every pass carries ~8,000 tokens
of fixed setup** (free token counter): ~2,000 our instructions, **~5,900
the web-search tool's own** (the basic `web_search_20250305` would be
~2,800). Approved: the three cuts that change what the app does, not how
well it answers, plus ~$0.20 of confirmation runs.

**1. The Google fact-check shortcut** (9b9cf25). Google's free Fact Check
API, already queried for every message, had a vetted fact-check for **5 of
10** typical forwards — all well-known English hoaxes; **none** of the
Hindi/Hinglish ones (Google matches words, and ClaimReview is mostly
English — §11 20). When it has one, the engine first asks the model to
answer from those fact-checks with **no tool at all**; only an answer it
backs with trusted="yes" is kept, anything else falls through to the
normal search having cost one small call. Its words are held until kept
(invariant 8). **PAID, MEASURED: "NASA says the Earth will go dark for 6
days" → $0.0084, 6.7 s, 1 call, 0 searches**, correct, "Fact-checkers",
95%, summary, 4 vetted sources (PolitiFact, FactCheck.org, Snopes ×2).
A covered claim used to be $0.048–0.061 and 28–51 s.

**2. Pass 1 says "not covered" in one sentence** (a61cf97, 5f871c0). The
prompt already said "keep that reply SHORT"; in all three two-pass checks
pass 1 wrote a full answer anyway (43–45% of the prose). Now the rule is
concrete, the summary rule exempts that sentence (they contradicted), and
`PASS1_STEP_NOTE` repeats it at the end of pass 1's own user turn, before
the language line. **PAID, MEASURED (a made-up Pune rumour): pass 1 wrote
one sentence, 318 output tokens.** Its first wording ("None of these
results address…") spoke of results the reader never sees — fixed in the
prompt, free, not yet re-run.

**3. "hi" no longer buys a check** (e8f77a9). `app/engine/triage.py`:
a whole message that is small talk (English/Hinglish/Hindi) or has no
letters/digits is refused before a daily slot is claimed. No length rule
(a claim can be one "word" in a script without spaces). The bot files it
as `smalltalk`, NOT `help`: help answers before the pending-report logic,
and "ok" is what people send when the bot asks for "any message" to show
a finished report — a test proves the help design would lose that report.

**The open-web pass is now the expensive part, and it was slow.** The
Pune run: pass 2 cost ~$0.13 of $0.1724, read **180,000 cache tokens**
across ~16 filtering rounds of the search tool, and took **295 s** —
longer than the bot waits (~270 s), so on Telegram it would have asked for
"any message". Earlier two-pass checks took ~57 s, so possibly an outlier;
it is the strongest case yet for A/B-testing the basic search tool
(§11 21).

**A second test-isolation leak, and a wrong fix reverted.** The full suite
began failing 1 run in 3 (`test_the_same_forward_twice_uses_one_slot_not_
two`). First diagnosis — "the cache-hit refund lands late" — was WRONG:
e250154 made the test wait, and it failed again with the wait (a 429).
The captured output told the truth: "[limits] the caller went away before
its slot arrived" printed DURING that test, and "refund not recorded: no
such table" in a brand-new test database. Claims cancelled by earlier
tests were settling on the limiter's 2-worker pool inside LATER tests'
databases. Bisecting pairs reproduced nothing (20 × 6): it was timing
across the file (5/12 runs of `test_limits.py`). Fixed for the rule
(2d07356): `limits.drain()` + the autouse fixture drains after every test,
before settings are restored; e250154 reverted. After: 0/15 file runs,
3/3 suites, same suite time. Lesson, again: read what the failing run
printed before naming a mechanism.

### 2026-10-10 — A one-click launcher, and what running it showed

Vinayak asked how to run the app; then for one click. **`start.cmd`**
(double-click — Explorer opens a `.ps1` in Notepad) runs **`start.ps1`**:
the app in one window, a wait until `/health` answers, then the bot in a
second. It starts nothing already running (Telegram allows one poller), and
refuses outright when `serve_demo.py` is running — the demo serves the same
app with fakes on the same port and its `/health` also says "ok", so a bot
wired to it would send people simulated verdicts. The process is checked,
not the port, for that reason.

Findings on the way:
- **The app and bot I started on 2026-09-29 were still running a week
  later**, invisible, logging into a temp folder; they outlived the session
  that started them. They rode out network drops (`ConnectError` retries)
  on their own; nobody had sent a check. Stopped on 2026-10-06 so Vinayak's
  own copies could start; he then ran them from two VS Code terminals.
- **Windows PowerShell 5.1 reads a BOM-less `.ps1` as ANSI**, so the
  launcher is pure ASCII (tests pin it, and that the check catches a
  non-ASCII file); `Start-Process` in 5.1 joins arguments unquoted, so the
  windows get `-EncodedCommand` (the project path has spaces).
- **Verified without touching his running copies**: `start.cmd` with both
  up (started nothing: 4 processes before and after), the demo guard (a
  stand-in process → refused, exit 1), and the fresh start through a copy
  moved to port 8010 with a stand-in bot (both windows; app up in 8 s).

### 2026-09-29 (later still) — The free test suite was refilling the real daily cap

**Found by looking at a number that could not be right.** After the restart
for the new cap, the dashboard said 0 used today — two checks had been paid
for that morning. The persisted counter really read 0 (and 2026-09-23's read
0 despite that day's paid reel). Only two statements write it: take a slot,
give one back. So something had given back two.

**Reproduced with a canary, never with the real database:** the suite run
with `DB_PATH` pointed at a file whose counters were all 2 → today's became
1. One slot per run; four runs since the morning's checks, floored at 0.
Bisected per test (`scratchpad/bisect_leak.py`): `test_a_burst_of_claims_
cannot_stall_the_answers` cancels 25 claims while a write lock is held; each
finishes later on the limiter's OWN pool and refunds its slot — after the
test's patches were undone, so the refund read the real `db_path` and a
limiter switched back on (its real default).

**Fixed for the rule, not the test** (6e21f09): anything running after a
test's patches are undone falls back to what `settings.db_path` held before
them — so a session fixture makes that a throwaway file before any test
runs, never restored. `tests/test_isolation.py` pins it and failed first.
Re-measured: canary 2 → 2 over a full run. The real counter was then set
back to 2 (raise-only).

**How long:** since the burst test arrived (2026-09-22 evening). Every
day's cap was refillable by running the free suite — invariant 5 was
never as strong as its tests said. The ledger is unaffected (it is only
written by real checks), so spend figures stand.

**A second finding from the same fix:** the new test's first, deliberately
failing, run printed a `Settings` object in pytest's assertion display —
with the start of the Anthropic API key. The tests now compare plain
strings; the wider exposure is §11 item 17.

### 2026-09-29 (later) — Failed searches get recorded; the cap goes to 5

**Search errors reach the bill** (c5e06c2, §11 16 closed). Each failed
search lands in `answer.usage.search_errors` by the API's error code
(`no_results` for an empty list), once per `tool_use_id`, and from there in
the spend ledger (a column added IN PLACE — the ledger is the spending
history, so no schema-version bump), the dashboard ("5 got nothing", codes
on hover) and the console bill. Codes only: anything that is not a short
snake_case name is stored as `unrecognized`, by the meter and again by the
ledger writer — the ledger may hold nothing anyone sent. The API returns a
failed search as HTTP 200 with a `web_search_tool_result` whose content is
one error object, not a list — the engine already branched on that, and
only printed it.

**The cap is 5 a day** (Vinayak: "use 5 or even more if you want"). Five,
not more: the point is a handful of quality checks a day, and measured
checks run $0.05–0.26, so a full day is at most ~$1.30. The pinning test
moved with it. Lower it back when the quality checks are done — or keep it,
if the bot gets real users.

### 2026-09-29 — The Telegram bot goes live; the summary and the chooser meet the real model

Vinayak, from his phone, with the logs watched. Both of the day's checks
were used deliberately, on the same well-covered rumour — "₹2000 के नए नोट
में नैनो GPS चिप लगी है" — so the second isolates the language chooser:

| Surface | Reply language | Cost | Time | Searches | Summary? |
|---|---|---|---|---|---|
| Telegram | Hindi (detected) | **$0.0587** | 25 s | 2 | yes |
| Web page | English (chosen) | **$0.0516** | 24 s | 3 | yes |

- **The bot works end to end on a real phone.** `/start` → help, a Devanagari
  forward → a Hindi answer, "trusted" badge, 90%, the summary blockquote,
  six sources. Rebuilt offline with `format_reply` from the stored answer:
  2,049 chars, valid Telegram HTML.
- **The real model writes the `<summary>` tag** — 2 of 2 (§11 9b answered,
  on a small sample). Both stood alone and matched the prose.
- **The chooser works against the real model**: Hindi input, English picked,
  English prose AND English summary. Not served from the cache, correctly —
  a different language is a different answer (cache key), so it was a fresh
  check.
- **Anthropic's prompt cache carried across checks**: two minutes after the
  first, the second wrote 1.9k cache tokens instead of 9.5k and read 33k —
  its Claude share was $0.022 against $0.039. Back-to-back checks are
  cheaper than the one-off numbers in §8.
- **Found by reading the server log: the bot's startup probe was a no-op.**
  It asked `APP_BASE/../health` → `/api/health`, a 404, and passed, because
  any response counted as "up". Fixed (aed10d3): strip the `/api/v1` prefix,
  require a 200 with the app's own `{"status":"ok"}`. The tests failed first
  with exactly the logged symptom; the restarted bot's probe then logged
  `GET /health 200`.
- **Domain-level `used=` is too coarse.** The model named `rbi.org.in`, so
  every RBI search result was kept — including the **₹20** note's
  security-features page and the RBI museum page, shown as receipts for a
  ₹2000 claim. Same seven sources both times. Breaks no invariant (it only
  narrows, and they are real RBI pages), but a reader who taps one learns
  nothing. §11 item 15.
- **Found while reconciling the ledger: an unrecorded $0.2559 link check**
  (2026-09-23 04:17 IST, on be8e51c — before the summary existed). The
  ledger said $1.1261 before today; the docs said $0.8702; the difference is
  exactly this row. A 128 s Hindi reel of political claims about Sonam
  Wangchuk. **5 searches billed, zero sources kept**, and both passes told
  the reader the search tool had failed ("सर्च टूल की सीमा खत्म", "टेक्निकल
  दिक्कत"), so the answer is general knowledge — honestly labelled `none`,
  35%. The reader got **two full answers**, pass 1's and pass 2's, largely
  repeating each other (§11 item 4, worse than measured before). 8.7k output
  tokens; $0.19 of it Claude. **Why the searches returned nothing cannot be
  known**: search error codes are only printed to the server console, which
  was not kept — the answer and the ledger record none of it. §11 item 16.

### 2026-09-23 — Two things the reader controls: a summary to skim, and the language

Vinayak, in his words: *"For all the answers or response, at the last give a
summary that is highlighted in some colour so that the user can quickly go
through it rather than reading everything. Keep the entire thing too as if
someone wants to read everything they should be able to as well."* And:
*"The user should be able to choose in which language they want the answer
to be in — give like some options with buttons and also a text box to enter
their desired language if it is not in the button."*

**The summary is a FIELD, not a paragraph.** The model ends its answer with
`<summary>two short sentences</summary>` before the verdict line;
`MarkerFilter` takes it out of the prose and hands it over separately, so
the surfaces can box it and the reader never sees the same two lines twice.
It is written in the reply's language, must stand alone ("never 'as
explained above'"), and must not mislead someone who reads only it — if
nobody reliable covered the claim, the summary says exactly that. The page
gives it an accent-coloured box, Telegram a blockquote, the console a frame.
**Accent, not the tier's green or amber:** a coloured box that looks like a
verdict gets read as one, and the tier badge already carries that job.

**Teaching the filter a second tag took two goes**, both caught by tests
before any commit: stripping the `<summary>` OPENER mid-stream released the
words it opens (the tag regex ran before the hold-back could see it), and
"unfinished" means something different for the two tags — a verdict tag is
unfinished until its `>`, a summary until its `</summary>`, because its own
`>` arrives immediately with the words after it. A summary cut off by
max_tokens keeps the words it had.

**The language is the reader's, not the sender's.** Any surface can send a
language NAME ("Hindi", "Marathi", "Kannada") — a name, not a code, because
the model reads it directly and the page's box lets anyone type one that is
not on a button. When it is set it REPLACES the detected language: saying
both would contradict, so `language_hint()` is skipped and the pick is
stated last, for the same measured reason the hint is (2026-09-22: with the
search tool attached, only the last line of the user turn held the reply's
language). The name is delimited, neutralised by `as_prompt_data`, and the
prompt says plainly that it is a language name, not an instruction.

**The cache key covers it.** The same claim in Tamil and in English are
different answers, and one must never be served for the other; case and
spacing are not a different language.

**The demo fake echoes the pick** instead of translating, which makes the
whole path testable at $0 — on the page as well as in the tests.

**Phone width, found by looking (again).** The chooser wrapped to three
lines on a 390 px screen, and since the composer is sticky that came
straight out of the conversation. Under 560 px it is one swipeable row.

**NOT YET MEASURED:** no paid run has happened since. Whether the model
actually writes the `<summary>` tag every time, and how well it answers in a
language the message was not written in, are open questions the first paid
check after this settles. The cost is a few more output tokens — call it
$0.001 a check until measured.

### 2026-09-22 (evening) — Two adversarial reviews: 13 defects, every one reproduced, every one fixed

Two independent reviewers went through the day's 20 commits — one for money
and concurrency, one for security and data — each proving its claims with
free scripts (fakes, temp databases). Every finding reproduced when I re-ran
it before touching code; every fix has a test that fails against the old
code; and the fixes went through the same review (below).

**The ones that mattered most:**

- **A trust label borrowed from a page the answer did not use.** Pass 2's
  `trusted="yes"` means "some source addressed it" — any web page. When its
  `used=` missed (the brand `timesofindia.com` for the host
  `timesofindia.indiatimes.com`), the keep-everything fallback kept an
  unrelated who.int result, and that labelled a Times of India answer
  "Fact-checkers" at 90% — past the 75 cap — cached for a week. **Kept is not
  relied on:** pass 2 now raises the label only for a trusted page the answer
  demonstrably rests on (a citation, or a domain its `used=` names). The real
  database holds one answer of this shape; its cache key predates today's
  prompt, so it can never be served.
- **The dashboard fell to DNS rebinding.** "From 127.0.0.1 with no proxy
  header" is also true of a malicious page the owner visits whose domain
  re-resolves to 127.0.0.1. The spend data listed job ids, and
  `/reports/{id}` — public, through the tunnel too — returns the person's
  message; the reviewer fetched one. The browser still sends the attacker's
  name as Host, so the gate now requires a local Host, and job ids are gone.
- **Four shapes of the verdict tag reached readers** (invariant 7): `used=`
  over 600 characters (full URLs), `used=` before `trusted=`, `<Verdict`
  split across deltas (the hold-back was case-sensitive; the regex was not),
  and a tag cut off by max_tokens (flush handed it over as text). **Three
  existing tests had pinned the leak as intended** — "visible, not silently
  eaten". Every tag shape now goes whether or not it parses, and the web
  page, which had no backstop at all, has the bot's. Fuzzed: 20,000 random
  splits and shapes, no leak, no lost confidence, tag-free prose
  byte-identical. Checked in headless Chrome.
- **The 2-a-day cap leaked at midnight.** A rejection refunded `today()`, not
  the day it was charged, so a bad link straddling midnight gave D+1 a third
  check.
- **A Telegram message could vanish** (its peek found the answer already
  delivered and returned in silence), **a deleted job froze its chat**
  ("still running" on every message — retention makes a 404 normal), and
  **one impatient chat could hold all 16 slots**.

**A design call on the bot.** A message that arrives while the chat's
previous check is undelivered is never checked automatically — at 2 a day,
an impatient "kya hua?" would spend half the day — but it always either
hands over the finished answer or says, in words, to send again. The poke a
timed-out wait asked for gets no extra note.

**A test that hangs is not a test that fails.** One new bot test hung
instead of failing. The cause was `Dispatcher.drain()`, latent since the
morning: on 3.12, `gather()` over tasks that are all already done completes
without yielding, and the done-callbacks that empty the task set run on the
NEXT loop turn — so a drain called in that turn spun forever, synchronously,
out of reach of any asyncio timeout. Its test runs the drain in a thread
and fails on the join timeout.

**Smaller ones:** `strict_host`'s `.strip()` removed Unicode whitespace that
browsers keep (a no-break space before `https://altnews.in/…` counted as Alt
News — and crashed the fact-check parser, dropping every prior fact-check);
a crawler-400 sequence could send `allowed_domains: []`; a transcription
that heard nothing was remembered as the post (its caption alone) for 30
days, against the cache's own stated rule; the ledger backfill labelled
every finished link and screenshot check "Voice / video"; `used="Alt News"`
stripped every source; claiming a slot froze the event loop while another
writer held the database (1 loop tick in 0.4 s, measured); and the bot gave
up on a slow link resolve at 30 s while the server went on to bill the job.

**Checked and sound, per the reviewers:** the cap's atomicity across threads
and processes; no double refund and no refund of paid work; exactly-once
delivery; the engine's spend bounds; the dashboard's other gates (tunnel
headers, case, HEAD/OPTIONS); `strict_host` against userinfo, backslashes,
IP forms and percent-encoding; the ledger storing no content; retention
deleting only finished rows. Answers stored before the error-text rewrite
still carry old technical text until retention deletes them — the real
database has none.

**The fixes, reviewed the same evening — 15 more defects, 5 of them
introduced by the fixes themselves.** Two fresh reviewers took the fix
commits, and a randomized interleaving search was run against the fixed bot.
Every finding reproduced:

- **Pass 2 could still relabel an answer.** The morning's fix asked for
  evidence the answer "rests on" a trusted page — but `used=` means "my
  reply draws on this", not "this page addressed the claim". Reproduced:
  pass 1 found a BOOM page about a DIFFERENT hoax and said trusted="no";
  pass 2 named that same URL, and the answer came out "Fact-checkers" at 90%
  under a heading reading "No fact-checker has covered this". A `used=` of a
  public suffix (`gov.in`) borrowed an unrelated PIB page's tier the same
  way. **The decisive fact was in the prompt all along:** CHAT_SYSTEM_WEB
  *instructs* pass 2 to say that no vetted source covered the claim, so any
  "fact-checked" label over its prose contradicts the answer it labels. Pass
  2 now never raises the label — the trusted page is still shown as trusted,
  and the answer stays "general web" under its 75 cap.
- **Four more tag shapes reached the reader** (invariant 7, second round): a
  `>` or `<` inside the quoted `used=` value, a `</verdict>` closing tag, and
  any tag past the hold cap. The pattern is quote-aware now and the cap is
  16000. The Telegram backstop also ran AFTER the text was split into
  paragraphs and ≤700-char pieces, so a long leaked tag lost only its first
  fragment — it strips the whole section first.
- **A regression of mine:** making unreadable words mean "unsaid" also caught
  `used="none"` — the words a model writes for an empty list — so every raw
  result came back as a receipt, the exact thing `used=` exists to stop. A
  short "nothing" vocabulary now means [].
- **A malformed confidence threw away a well-formed `trusted="no"`** — the
  model's only way to LOWER a label. `confidence="40%" trusted="no"` did not
  escalate and came out "fact-checked"; with a clean number the same tag
  escalated and came out "none". Each attribute is read on its own now.
- **A prior Google fact-check suppressed escalation.** With one in hand, a
  pass 1 that produced NO prose (an outage) ended as "couldn't be reached" —
  a failed check that still spent one of the day's two slots — while the
  open-web pass could have answered. Fixing it surfaced the other half: the
  escalated answer was then labelled "fact-checked" over pass 2's words.
- **`strict_host` never looked at the port**, so `https://altnews.in:443.evil.com/`
  was labelled a fact-checker although Chrome refuses the URL outright (found
  in a 2,332-URL differential against Chrome's own parser).
- **The page's basis line counted every source under one label** — "2 trusted
  sources" for an answer whose second source was listed under "General web".

**The money and concurrency half of the same round:**

- **A poke queued behind its own chat was still paid for.** The new rule was
  enforced when the per-chat lock was ACQUIRED, not when the message arrived:
  two quick pokes, the first holding the lock for its ~3 s peek, the check
  delivered in that window, and the second looked like a fresh start. The
  Dispatcher now decides "was this chat busy?" as the message arrives — and
  a **2,000-interleaving search of the FIXED bot** then found two more: a
  burst arrives before the first handler has submitted anything (so `pending`
  was empty for all of them), and "is the first handler still waiting?" was
  the wrong way to tell a poke from a new message, because that wait also
  ends when someone ELSE delivers the report — the second message's own words
  were dropped in silence, the very failure the first fix was for. The bot
  now records that a wait ASKED for "any message". Both explorers (1–3 slots
  and 16, 2,000 seeds each) end clean.
- **The event-loop fix traded a frozen loop for a full thread pool.** With a
  burst of claims in flight while another writer held the database, every
  worker of asyncio's shared pool was busy — and `GET /reports`, the only way
  an answer reaches the page or the bot, is a thread call too: reading a
  finished answer stalled 30 s. The limiter has its own two-worker pool now
  (measured after: 0.00 s), and the test times a real read behind a burst
  instead of counting loop ticks, because ticks passed on the broken version.
- **Any failure that bought nothing now hands its slot back.** Only an
  HTTPException did, so a database error inside a route burned half the day's
  budget with no job row and nothing in the log; and a request cancelled
  WHILE its slot was being claimed never reached the route body at all. The
  claim is a plain thread future now, so a cancelled caller still gets its
  slot returned from the pool thread.
- **The kind guess stopped guessing.** A bare news URL pasted as text was
  recorded as "Link" (it is not a platform link, so it goes to /verify/text),
  and a link whose scheme a phone auto-capitalised as "Text". Both are
  "unknown" now. The backfill also used INSERT OR REPLACE, so it could
  clobber a kind the live path had already proved.
- **The dashboard takes exactly one Host header** (a raw client on this
  machine could send two, local first; no browser can).

**The lesson, for the third time this project:** a fix that addresses the
mechanism a reviewer named, rather than the rule behind it, leaves the hole
open. Both label fixes were mine, and the second one's own test asserted the
contradiction as correct. Three of this round's defects were introduced by
the morning's fixes, and two more were found only by running a reviewer's
randomized search against the fixed code — a review of a fix is not a
formality here, it is where a third of the defects came from.

**Residuals, in §11:** an idempotency key on submissions; the answer cache
key does not cover the labelling code; the screenshot route's inline vision
call runs on the SDK's default timeout; a stray unclosed `<verdict` in
prose swallows the rest of the answer (invariant 7 wins over a model that
writes what it was told never to write); a malformed FINAL tag falls back to
an earlier parseable one.

### 2026-09-22 — The first paid runs, the 2-a-day cap, and what only reality could show

Vinayak's instructions for the day, in his words where they set policy: the
paid run ("let's do this now"); AFP ("you can decide"); the daily cap ("lower
it for now and do only 2 checks per day, just to be safe … make sure this
change is recorded somewhere"); the transcript cache, the Sonnet/Opus A/B and
message pruning ("do them"); the bot answering one person at a time, the
technical error text and the internal duplicates ("do whatever you think is
best"); a spending dashboard ("please add one"); Facebook Reels ("let's test
those"); Telegram go-live deferred ("maybe tomorrow"); WhatsApp on hold.

**DECISION — 2 checks per day (Vinayak).** `max_checks_per_day` 100 → 2,
deployment-wide. Recorded in `app/config.py` (with his words), pinned by a
test (a decision, not a tuning knob), and here. Lowering the number alone
would not have been "safe": the counter lived in memory, so every restart
refilled it — under `--reload`, every saved file. Demonstrated against the
old code (two checks, a simulated restart, a third sails through). It now
lives in SQLite, taken by one conditional UPSERT so the database itself
refuses slot 3 (rowcount 0 once full — measured), fails CLOSED if the
counter cannot be written, and counts India's day. A check served free from
cache hands its slot back; anything that paid for OCR/ASR, and any failure,
keeps it — a stream that died mid-answer may have been billed unmeasured.

**DECISION — AFP stays trusted (Vinayak left it to me).** IFCN-certified,
has an India desk; a general-purpose checker that trusts Snopes and Full Fact
but not AFP would be inconsistent. It cannot be *searched* (below) — it is
reached through Google Fact Check and the open-web pass, and still labelled
trusted when cited.

**Two blocked domains meant the widening had never searched.** Before any
paid check, `scripts/crawl_probe.py` (the docstring had referenced it since
09-11; it did not exist) asked the API which of the 45 searchable domains it
accepts. The 400, verbatim: *"The following domains are not accessible to our
user agent: ['apnews.com', 'factcheck.afp.com']"*. `allowed_domains` is
all-or-nothing and the engine answered ANY 400 by falling back to the five
core Indian domains — so since 09-11 every check would have searched only
those five. Both moved to FACTCHECK_ONLY; all 43 remaining accepted. The
engine now drops exactly the domains a 400 names and keeps the rest, and
never sends an empty list (it may mean "no restriction"). A 400 is not
billed, so finding this cost nothing.

**The measured costs** — see §8 for the table. The model was 2–3× high.

**English in, Hinglish out — and the prompt could not fix it.** The first
check ("Drinking hot water kills the coronavirus") answered in Hinglish.
Rewording the rule did nothing. Measured instead: the identical prompt with
NO search tool replied in English 5 of 5 times (four prompt variants, both
effort levels); WITH the tool, Hinglish 3 of 3 — search queries and results
all English. So the model is no longer asked to judge: `language_hint()`
states the language as the last line of the user turn (Indic script; Latin
with Hinglish function words; Latin with POSITIVE English evidence — "no
Hinglish" alone would call Spanish English). Verified English under the
exact failing condition. Diagnosis cost $0.197.

**A label that contradicted its own answer.** A fresh Nagpur Metro rumour
escalated correctly — but the footer read "Fact-checkers and official
sources" under a section headed "no fact-checker has covered this", because
pass 1 had found BOOM/Factly pages about a DIFFERENT hoax. Invariant 1 now
reads: the model can LOWER the label (its trusted="no" demotes), never raise
it. After the fact a label only goes down on serve. "General web" now needs
an actual general-web source (the A/B found Opus's answer labelled "general
web" over a list of nothing but fact-checkers).

**Zero citations, 22 raw results.** Neither paid run returned a single
citation — web_search_20260209 filters results through code execution — so
the source list was every raw result, Manchester City Council included, for
a Nagpur claim. The sentinel gained `used="domain domain"`: the model names
what it relied on, results are NARROWED to those, and it can never add one.
Verified with the real model: `used="fullfact.org politifact.com snopes.com"`.

**Sonnet 5 vs Opus 5, same reel (PEEK TV — the old $0.279 baseline).**
Sonnet: $0.082, 34 s, one pass, trusted, 85%, specific and right (the 22 July
protest, the harassment, the 27 July complaint with no FIR by 5 August, the
AI fakes BOOM documented; it said it could not verify the ₹140 detail).
Opus: $0.326, 89 s, two passes, 35% — it had the same Alt News and BOOM
articles in its own source list and still said no trusted source mentioned
her, then reasoned from training memory that the NEET protests were in 2024
while the PIB release in its sources is about NEET-UG 2026. **Sonnet 5 stays.**

**Four things that would have failed on the real machine, not in any test:**
the server could not START on the one database ever used (`DROP TABLE
claim_vecs` → `no such module: vec0`: SQLite cannot drop a virtual table
once its extension is uninstalled; every test uses a fresh file); a total
API failure stored a blank COMPLETE answer, which one test had pinned as
correct; Google Fact Check failed silently mid-run (the free human-verdict
evidence vanished with no log — and httpx errors carry the API key in the
URL, so the log now carries only type and status); and four scripts crashed
on Windows the moment output was redirected (cp1252), one of them
`crawl_probe.py` itself, right after making its call.

**Built:** the transcript cache (a reel is transcribed once — the A/B paid ASR
once for both models); retention (answers deleted after 30 days at startup
and every 6 hours; the spend ledger keeps costs with no content — pinned
against the schema itself); the spending dashboard (below); a concurrent
Telegram bot; plain-language errors everywhere a person can see one.

**The dashboard, looked at before called done.** Rendered in headless Chrome
at desktop and at a true 390 px (desktop Chrome will not size a window below
~500 px, so "phone" screenshots were cropped desktop renders until measured
in an iframe). Looking found four things no test could: the limit meter read
FULL at "0 of 2" in dark mode (its empty track was bright enough to pass for
a fill); experiments showed "Nothing found" and skewed the per-check average;
backfilled bills showed $0.09 of searches where $0.15 were bought (their
split read as zero — recovered from stored tokens); and at phone width the
last two date labels ran together. Local-only is enforced by client address
AND the absence of any forwarding header — the cloudflared tunnel connects
from 127.0.0.1, so "is it localhost?" alone would have published the
owner's spending to anyone holding the share link.

**The bot race, and a test that proved nothing.** Concurrency opened a way to
pay twice: two messages from one chat would both see no pending job and both
submit. A per-chat lock covers the decide-and-submit step. The first version
of its test PASSED WITH THE LOCK REMOVED — the fake send/submit never
suspended, so the race could not occur in a test. Real network calls do
suspend; the fakes now yield, and with a planted no-op lock the test fails
"one chat paid twice". Two tests then failed for a reason worth keeping:
asyncio's clock on Windows is `time.monotonic`, measured stepping 15–16 ms,
so `asyncio.sleep(0.01)` can return after ONE loop turn. Tests now wait on
conditions, not durations.

**Duplicates that had drifted.** The two host parsers (what may be labelled a
fact-checker / what the server may fetch) disagreed on trailing dots, and
both accepted empty labels — `evil..altnews.in` was TRUSTED as Alt News.
One parser now (`app/hosts.py`, RFC 1123 labels). `link_probe.py` promised
"could skip Sarvam" for any caption track while the app trusts only
uploader/-orig/_FB tracks; it now asks the app's own picker. The loose
sentinel regex (three copies) and ConsoleStream (two) have one home each.

**Facebook Reels (Vinayak asked).** Share-button links
(`facebook.com/share/r/...`) resolve, with duration advertised — over-cap
videos are refused before any download, unlike Instagram. Some reels fail
with yt-dlp's "Cannot parse data" by share link AND /reel/<id>, on the
latest yt-dlp (upgraded to 2026.08.19): removed/login-only posts. The reader
now hears exactly that.

**Process, twice over.** (a) A commit went in with a failing test: the chain
checked `tail`'s exit code, not pytest's. Commits since check pytest's own.
(b) Shell heredocs collapse doubled backslashes; it produced invalid escapes
five times today. Every .py now compiles with SyntaxWarning as an error —
and that test's first draft had one in its own docstring.

**Session spend:** $0.87 recorded on the dashboard (three app checks $0.26;
the A/B $0.41; language diagnostics $0.20), plus the crawl probe's second
call, whose cost was never printed (its crash) — a fraction of a cent.

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

**The adversarial pass over the pivot found four more, all the same shape.**
Every one of them threw away a check that had already been paid for:

  1. **A dead job stranded the page forever.** Both route-level failure paths
     (media ASR, link fetch) stored a FAILED answer and never published to the
     job's stream. Heartbeats keep the connection open, so from the page a dead
     job is indistinguishable from a slow one — "Checking…" stayed up
     indefinitely for a failure already in the database. Storing the row was
     enough when the page only polled; streaming made the stream half
     mandatory. This is precisely what the old §11 item about three-way
     FAILED-finalization duplication predicted, and the two copies had already
     drifted. Now one `fail_job()`, plus a client-side deadline on `follow()`
     so any future not-published bug degrades to polling rather than vanishing.
  2. **Escaping expands, and the Telegram budget measured the raw string.**
     `source_text` is ASR/OCR/caption text. 4,000 ampersands measure as 4,000
     characters and arrive as 20,000, blowing the hard limit — reply lost.
     Cutting the *escaped* string would be worse (a cut inside `&amp;` is the
     broken entity Telegram rejects), so the raw text is cut and shrunk until
     its escaped form fits.
  3. **`_soften()` only broke on spaces**, so CJK, Thai, or one enormous token
     produced an undroppable block and the answer vanished again — one layer
     below the fix that had just been made for it.
  4. **A source heading could outlive its sources**, telling the reader we
     found general-web sources and then showing none.

Each was reproduced against the unfixed code before the fix, and re-measured
after: a combined hostile input (CJK + entities + a 4,800-char heard block + 30
sources) now comes out at 3,829 characters with every tag balanced, the answer
present and the sources present.

**What was kept deliberately.** Every SSRF fence, the exact-host allowlist, the
yt-dlp extractor pinning, the rate limiter's atomic reservation, the caps
before spend, the `#job=` hash resume, `GoneError` clearing a dead hash, the
factory-not-promise `submit()` guard, and the escape-then-promote ordering in
every renderer. The pivot changed the answer's shape, not the things that stop
it costing money or lying.


### Earlier entries (2026-07-24 → 2026-07-28, the Truth Report era)

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

## 8. Cost model

**MEASURED 2026-09-22**, Sonnet 5 at effort `medium`, from each answer's own
`usage` (the API's usage fields, priced at list):

| Check | Measured | Modelled before | Searches | Time |
|---|---|---|---|---|
| Known-debunked claim, one pass ("Drinking hot water kills the coronavirus") | **$0.048** and **$0.061** (two runs) | ~$0.16 | 1–2 | 28–51 s |
| Fresh rumour, both passes (Nagpur Metro, in Hindi) | **$0.150** | ~$0.26 | 3 | 57 s |
| A real 70 s reel (PEEK TV), one pass | **$0.082** + $0.007 ASR | — | 2 | 34 s |
| Same reel on **Opus 5** (for comparison) | $0.326 | ~$0.44 | 5 | 89 s |
| Exact re-forward inside the cache TTL | **$0** | $0 | 0 | instant |
| 2026-09-29: covered claim via **Telegram**, Hindi | **$0.0587** | — | 2 | 25 s |
| 2026-09-29: same claim on the **page**, English chosen, 2 min later | **$0.0516** (Claude $0.022 — prompt cache warm) | — | 3 | 24 s |
| 2026-10-11: **Google fact-check shortcut** ("NASA: 6 days of darkness") | **$0.0084** — 1 call, no tool | — | 0 | 6.7 s |
| 2026-10-11: fresh rumour, both passes, pass 1 now one sentence (Pune Saturdays) | **$0.1724** (pass 2 ≈ $0.13: 180k cache reads, ~16 filter rounds) | — | 3 | **295 s** |

**Fixed setup per pass, counted 2026-10-10** (free token-count endpoint):
~2,000 tokens of our instructions + **~5,900 of the web-search tool's own**
(`web_search_20260209`; the basic `web_search_20250305` counts ~2,800). A
pass with no tool — the fact-check shortcut — pays only the first part.

Where it goes, over today's runs: roughly **four-fifths Claude, a sixth
search, the rest transcription**. Most of the Claude share is prompt-cache
traffic, not new input: the web-search tool's server-side loop re-reads its
own growing context from cache (0.1× price) at each step. A first check
writes ~10k cache tokens; uncached input is only a few hundred.

- Sonnet 5: **$2 / $10** per million tokens (cache writes $2.50, reads $0.20).
  Opus 5 is $5 / $25 — and lost the A/B on quality too (§7).
- Web search: $0.01 per search, capped by `chat_max_searches_trusted` (3) and
  `chat_max_searches_web` (2). The search tool's result filtering (code
  execution) showed up as its own steps but NOT as a billed line — raw usage
  counted only `web_search_requests`.
- Sarvam ASR: **₹30/hour**, billed per second (a 70 s reel ≈ ₹0.58). Paid once
  per video now — the transcript cache keys it by the platform's video id.
- A link with subtitles or a caption carrying the claim costs $0 to read.

**The old engine's anchor** (2026-07-28): the same PEEK TV reel cost $0.279
as a 6-claim Truth Report. The new engine answered it for **$0.082** (+ the
same ASR) — about 70% cheaper, and with a better answer.

Metering lives IN THE APP: every answer carries `answer.usage`, split into
Claude / search / ASR, and a spend ledger keeps those costs (never the
messages) after answers are deleted — it is what the dashboard reads:
**`http://127.0.0.1:8000/dashboard`**, this machine only.

**What bounds the spend** (all in `app/config.py`):

| Setting | Default | Bounds |
|---|---|---|
| `max_checks_per_day` | **2** | whole deployment, persisted; Vinayak 2026-09-22 |
| `max_checks_per_hour` | 10 | per visitor IP (abuse, not spend) |
| `day_boundary_utc_offset_min` | 330 | "a day" is India's day |
| `max_input_chars` | 5000 | text per submission |
| `chat_max_tokens` | 12000 | output tokens per pass |
| `chat_effort` | medium | thinking effort — `low` is the first cost lever |
| `chat_max_searches_trusted` | 3 | billed searches in pass 1 |
| `chat_max_searches_web` | 2 | billed searches in pass 2 |
| `web_tier_enabled` | true | set false to skip pass 2 entirely |
| `web_tier_confidence_cap` | 75 | ceiling on a web-only answer's confidence |
| `max_media_bytes` | 25 MB | upload size (enforced as bytes stream in) |
| `max_media_seconds` | 300 | audio duration (probed before decoding) |
| `answer_cache_ttl_trusted_h` | 168 | 7 days |
| `answer_cache_ttl_web_h` | 24 | 1 day |
| `transcript_cache_ttl_days` | 30 | a video's words, by platform id |
| `answer_retention_days` | 30 | messages deleted after this; costs kept |

**At 2 a day: ~$0.30/day at the measured two-pass cost, and under $1/day
even at the caps' worst case** (two full passes of output, five searches and
five minutes of audio is ~$0.42 a check). A free cache hit gives its slot back. Raising the cap is one number in
`config.py` (or `MAX_CHECKS_PER_DAY` in `.env`), and a test pins the default —
raising it should be deliberate.

**Always-free**: the whole test suite, `demo_offline.py`, `serve_demo.py`,
`share_demo.ps1 -DemoMode`, `factcheck_probe.py`, `link_probe.py`,
`telegram_bot.py --check-token`, and the dashboard. `crawl_probe.py` is free
when it finds a blocked domain (a 400 is not billed) and a fraction of a cent
when it does not.

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
- **Chrome and Edge are installed** — `chrome --headless=new --screenshot=...`
  renders pages for a real visual check (how the dashboard's defects were
  found). Desktop Chrome will not size a window below ~500 px: for a true
  phone width, load the page in a 390 px `<iframe>` inside a wider window.
- asyncio's clock here is `time.monotonic`, stepping 15–16 ms — never
  sequence async tests with short `asyncio.sleep` calls.

## 10. How to run

See [GETTING_STARTED.md](GETTING_STARTED.md). **To run it for real, double-click
`start.cmd`** (app + Telegram bot, each in its own window; §7 2026-10-10).
Quick reference:

| Command | Cost | Proves |
|---|---|---|
| `.venv\Scripts\python.exe -m pytest tests -q` | $0 | everything; every paid seam is faked |
| `.venv\Scripts\python.exe scripts\serve_demo.py` | $0 | the real chat UI + real SSE, simulated Claude |
| `.venv\Scripts\python.exe scripts\demo_offline.py` | $0 | the engine plumbing + cache, in the console |
| `.venv\Scripts\python.exe scripts\factcheck_probe.py "claim"` | $0 | which publishers we keep/drop |
| `.venv\Scripts\python.exe scripts\link_probe.py <url>` | $0 | does a reel resolve, and does it have captions |
| `.venv\Scripts\python.exe scripts\telegram_bot.py --check-token` | $0 | the bot token still works |
| `.venv\Scripts\python.exe scripts\crawl_probe.py` | $0–0.002 | every search domain is accepted by the API |
| http://127.0.0.1:8000/dashboard (server running) | $0 | what has been spent — this machine only |
| `.venv\Scripts\python.exe scripts\asr_probe.py clip.ogg` | ~paise | one real transcription |
| `.venv\Scripts\python.exe scripts\smoke_test.py "claim"` | ~cents | one real check, with its measured bill |
| `.venv\Scripts\python.exe scripts\link_smoke.py <url>` | ~cents | a real reel, end to end, with its bill |
| `.venv\Scripts\python.exe scripts\ab_models.py <url or claim>` | ~$0.40 | two models on the same input, each billed |

- Real server + UI: `.venv\Scripts\python.exe -m uvicorn app.main:app --reload`
  → http://127.0.0.1:8000  (**one worker** — the stream registry and the rate
  limiter are both in-memory)
- Share publicly: `.\scripts\share_demo.ps1` (add `-DemoMode` for the free variant)

## 11. Open items

### THE TODO LIST (updated 2026-10-17 — the authoritative one)

**THE NEXT STEPS, agreed 2026-10-11 (Vinayak: "We need to make this into an
app/website which anyone can access and also a whatsapp bot. And also work
on the remaining todo's"):**

A. **A website / app anyone can use.** **DECIDED 2026-10-15** (§7): this PC
   behind a Cloudflare named tunnel now, a Mumbai VM later; a $1/day dollar
   budget with per-person limits; the bot open to anyone at 5 a day each; a
   .com via Cloudflare. The research and the reproduced audits behind it are
   in `docs/research/2026-10-15/`; the brief's §6 is the build order.
   **STATUS 2026-10-17: BUILT, except step 4, which is the owner's.**
   - Steps 1 (the blockers), 2 (budget, per-person limits, Turnstile), 3
     (restarts, the ledger, monitoring) and 5 (privacy, terms, the AI line,
     deletion, the installable app) are done and reviewed twice. The
     step-5 reviews found 18 + 13, all fixed (§7).
   - Step 4, running it 24/7 here at the .com, is `docs/go-live.md`,
     waiting on Vinayak. HANDOFF §0 lists his steps.
   - Never yet met reality: Cloudflare streaming the answer (or buffering
     it), a real reboot under Task Scheduler, the budget against a real
     bill.
   The original framing, kept for the record — decisions first, then code:
   - **Where it runs, 24/7.** Options: a small cloud host (Render, Railway,
     Fly.io, or a ₹400–800/month VPS) with a persistent disk for SQLite and
     ffmpeg + yt-dlp installed — ONE worker (in-memory stream registry and
     rate limiter); or keep it on this PC behind a named Cloudflare Tunnel
     with a real domain (free, but the PC must stay on). `share_demo.ps1`
     already does a temporary tunnel.
   - **Who pays, and how much a day.** The cap is deployment-wide (5/day): the
     public would exhaust it in minutes, and then everyone is refused. Decide
     a daily dollar budget, per-person limits (IP today; phone number on
     WhatsApp), and a bot shield (Cloudflare Turnstile) — maybe sign-in.
     Set a monthly spend limit in the Anthropic console as the hard backstop.
   - **Before any public URL:** §11 17 (a `Settings` repr prints the API
     keys — fix first), §11 18 (who may use the bot), privacy note + terms
     (messages kept 30 days), SQLite backups (the ledger is the spend record).
     The dashboard already 404s for anyone but this machine. **All DONE by
     2026-10-16** (privacy notice and terms: §7, step 5).
   - **"App":** the page is mobile-first; a web-app manifest + icon makes it
     installable from the phone's browser ("Add to Home screen") — no app
     store needed. A store app is a separate, much larger project. **DONE
     2026-10-16** (767d44f; installable per Chrome, a share target that
     fills the box). Still to see on a real Android phone once the .com is
     live: the install prompt, and what WhatsApp's share sheet offers.
B. **The WhatsApp bot.** Meta's WhatsApp Business Platform (Cloud API):
   a Meta Business account, a phone number not already on WhatsApp,
   business verification (slow — start it early), and a public HTTPS
   webhook (which A provides). Replies inside the 24-hour window after a
   person writes are free-form; anything later needs an approved template —
   check Meta's current pricing before building. Code: a webhook route, a
   WhatsApp formatter (it uses *bold*/_italic_, not Telegram's HTML; the
   rest of `format_reply`'s budgeting carries over), media download via the
   Graph API into the existing image/voice paths, and the bot's per-chat
   lock + pending-report logic. A sandbox (Meta's test number, or a provider
   like Twilio) can be built against before verification completes.
   **Researched again 2026-10-15** (`docs/research/2026-10-15/whatsapp.md`,
   complete but not independently verified; decision-brief §4).
   - **Cost:** a reply inside the 24-hour window is ₹0.115, but each number
     gets 1,000 free service messages a month, so at the $1-a-day ceiling
     Meta's bill is ₹0. No company is needed to launch.
   - **What Vinayak can start now, in order:**
     1. a new SIM that has never been on WhatsApp, kept recharged;
     2. a free Udyam sole-proprietorship registration, in exactly the name
        Meta and the site will show (business verification follows, ~7
        business days, optional at first);
     3. the Meta developer account, an app, a business portfolio and a
        WhatsApp Business Account, in INR, built against the free test
        number (5 phones);
     4. a card in Billing Hub;
     5. a human escalation path, which Meta's Business Policy requires and
        the bot does not have yet.
     The privacy page already exists (step 5); its public URL comes with
     step 4.
   - **The risk** is Meta's terms §4.7 (AI providers whose primary
     function is AI are barred, at Meta's discretion). The Quint runs an AI
     fact-check bot on WhatsApp in India (May 2026). A written view from
     Meta before the build is optional.
C. **The remaining to-dos** — items 4–32 below. Their value order is in
   HANDOFF §6.

**Running it (with Vinayak present):**

1. **Double-click `start.cmd`** (app + bot in two windows; it refuses if the
   demo server is up). The PC must stay awake — the bot lives here. The cap
   is shared with the web page; a repeat is free; "hi"/"ok"/"thanks" cost
   nothing since 2026-10-11. A message sent while that chat's check is still
   running is NOT checked automatically — the bot says so. Before a restart
   after downtime, `getWebhookInfo`'s `pending_update_count` shows any
   backlog the bot will process on start (the cap bounds its cost).
   **After pulling new code, restart both windows** — a running app keeps
   the code it started with.
   **Unattended (step 4):** `scripts\serve_forever.py`, run by a Task
   Scheduler task at boot (`docs/go-live.md` §5). It replaces `start.cmd`'s
   windows, since only one app and one bot may run. `New-Item
   data\serve_forever.stop` stops it in order.

**On hold until A exists:**

2. **WhatsApp bot** — see B. Not "later" any more: next after A.

**Worth doing next, in code (value order):**

3. ~~**Raise the cap when ready.**~~ **5 a day since 2026-09-29.** Decide
   again after the quality checks: back to 2, or keep 5 for real users.
   **Superseded 2026-10-15:** the money is bounded by the $1-a-day budget,
   and the count stays only as a 40-a-day backstop.
4. **Answer quality on genuinely fresh rumours.** One two-pass run so far
   (Nagpur Metro) — excellent, but one. A handful more across health, science
   and Indian politics would say whether `chat_effort="medium"` is the right
   default, and whether pass 1 should be told harder to keep its "not covered"
   reply short (it wrote five paragraphs before escalating). MEASURED again
   2026-09-23 (the Wangchuk reel, §7 2026-09-29): pass 1 wrote a complete
   answer and pass 2 another, so the reader got the same ground twice and
   paid for 8.7k output tokens. **The two-answers half is FIXED 2026-10-11**
   (one sentence, 318 tokens, paid-measured); quality across health /
   science / politics is still to judge — with an eval set (item 22).
5. **Mixed-language messages** (an English caption over a Hindi transcript)
   get "reply in the Indic script" today — sensible for reels, but untested
   with a real sender who writes English about Hindi content.
6. **`/health` is a constant** — no way to see queue depth or degraded
   subsystems (the dashboard covers spend).
7. **ASR metering sits at the ffmpeg boundary**, not the ASR provider seam — a
   future path that transcribes without `normalize_to_wav` would be unmetered.
8. **Long downloads share asyncio's default thread pool** with report polling,
   so a few concurrent link jobs can make finished answers look stuck.
9. **Garbled source titles** — a WHO PDF surfaced as "Rum½ÝÀÛ ISSUE#2 FA@kS"
   (its own metadata). Cosmetic; a title that fails a sanity check could fall
   back to the publisher.
9a. **The Telegram bot cannot pick a language yet.** The API takes one on
   every route (2026-09-23) and the web page offers buttons plus a box; the
   bot needs a `/language` command or an inline keyboard, remembered per
   chat. Worth doing at go-live, when real messages show whether people even
   want it.
9b. **The summary against the real model: 2 of 2 carried one** (2026-09-29,
   Hindi and English). Small sample; keep counting on later paid runs.
10. **An idempotency key on submissions.** A caller that stops waiting for
   the 202 leaves a job the server finished and billed but nobody delivers.
   The bot now waits (300 s) far longer than the server's bounded inline
   work (a link resolve, 60 s) — except the screenshot route's vision call,
   which runs on the SDK's default timeout. A client-sent key (the bot's
   `chat:message_id`) that returns the existing job would close it for good.
11. **The answer cache key does not cover the labelling code.** It covers the
   prompt, model, effort and whitelist; a change to how the tier or
   confidence is computed can serve an old label for up to a week (trusted
   TTL). The labelling changed twice on 2026-09-22; checked both times that
   nothing reachable was mislabelled. An `ENGINE_VERSION` in `cache_key`
   would make it structural. (The transcript cache has this covered: its key
   carries a version, bumped to v2 when its rule changed.)
12. **Pass 2 can never say "an official source did cover this".** Its prompt
   tells it to say the opposite, which is why it may not label an answer.
   If that is worth changing, the prompt and the label rule move together —
   and a paid run decides it, not a guess.
13. **Two sentinel corner cases, both model-behaviour-dependent.** A stray
   unclosed `<verdict` in prose swallows the rest of the answer (invariant 7
   beats a model writing what it was told never to write), and a malformed
   FINAL tag falls back to an earlier parseable one. Neither is reachable
   from user input (`as_prompt_data`).
14. **Two slow link resolves can hold both daily slots** while they run, so
   everyone else is told the service is out of checks for up to a minute —
   and both slots come back, since a rejected resolve is refunded. A loop of
   bad links therefore throttles nobody but the person sending them.
   Pre-existing; reserve-first is what makes the cap real, so this is the
   price of it.
15. **`used=` narrows by domain, which is too coarse for big sites.**
   MEASURED 2026-09-29: `used` named rbi.org.in, so a ₹2000 answer showed
   the ₹20 note's page and the RBI museum as receipts. Options: let `used=`
   carry URL paths for the few results it rests on (the tag's size cap was
   raised once for exactly this, §7), or cap results per domain. Either
   must stay narrow-only, and a paid run decides whether the model fills it
   in reliably.
16. ~~**Search errors leave no trace after the console closes.**~~ **DONE
   2026-09-29** (c5e06c2): recorded per check in `usage.search_errors`, the
   ledger and the dashboard. The next politics check that hits one will
   say which error it was.
17. ~~**`Settings` prints its secrets.**~~ **DONE 2026-10-15** (e4a9822):
   every credential field is `Field(repr=False, exclude=True)` — plain
   `str`, because providers, the demo's key-blanking and the tests assign
   plain strings. `tests/test_secrets.py` pins the RULE by field name, so
   the WhatsApp and Turnstile keys to come cannot be the ones that print.
   Same day, same rule (63f8049): the **bot token** leaked through httpx
   error text (every Bot API URL carries it) whenever Telegram refused a
   file over 20 MB — `TelegramClient._check` now raises without the URL.
18. ~~**The bot answers anyone.**~~ **DECIDED 2026-10-15: it should** —
   Vinayak chose "anyone, 5 a day each" over an owner-only allow-list
   (§7). Built: each Telegram user is counted as themselves (020e26f; the
   anonymous-admin and post-as-channel stand-ins, 2d3b5c8), with 5 paid
   checks a day each (55d3de0), inside the $1-a-day budget (20e882d).
19. ~~**The bot's own startup check accepts the demo server.**~~ **DONE
   2026-10-16 with OPS-18**: `/ready` says `mode: demo` for the free demo
   (fake_stages sets it) and the bot refuses it at startup. The original
   note: `app_is_up`
   wants `{"status": "ok"}`, which `serve_demo.py` also returns, so a bot
   started by hand next to a running demo would send fake verdicts.
   `start.ps1` guards by process; the structural fix is a `/health` that
   says which mode it is in, and a bot that refuses `demo`.
20. **Google's fact-check lookup misses Hindi and Hinglish.** MEASURED
   2026-10-10: 5/10 typical forwards had a vetted match, all English; none
   of the Hindi/Hinglish versions — not even the ₹2000 GPS-chip story in
   Devanagari. Translating the query to English first (one tiny call, or a
   cheap model) would let the $0.0084 shortcut serve most Indian forwards.
   **MEASURED 2026-10-15 (free, the engine's own `search_factcheck`):** 12
   Hindi/Hinglish forwards of known hoaxes — **3/12** had a vetted match as
   forwarded, **7/12** in a hand English translation (5G, NASA darkness,
   hot water ×2, WhatsApp charges, salt-water gargle, UNESCO anthem). Google
   matches WORDS: the ₹2000 GPS-chip story misses even in English, as do
   free laptops, Coca-Cola/HIV, cow urine and onion-in-socks. Translation
   more than doubles the shortcut's reach; worth building (a match still
   needs the model's trusted="yes" to be kept).
21. **A/B the basic search tool** (`web_search_20250305`) against the
   filtering one. ~3,100 fewer setup tokens per pass, citations that would
   fix item 15's ₹20-page problem, and no filtering rounds — the Pune run's
   pass 2 took 295 s and read 180k cache tokens over ~16 of them. But raw
   results go into the context unfiltered, so it may cost MORE per search.
   Only a paid side-by-side on a few claims can say (~$0.30).
22. **An eval set** — six to ten claims with known answers (health, science,
   Indian politics; English, Hindi, Hinglish; one reel). It is the quality
   check this project lacks, and it gates every remaining cost trade-off:
   effort `low` vs `medium` (Anthropic measured a third to half off for 1–3
   points on research tasks), 2 vs 3 vetted searches, item 21. ~$0.60 a run.
24. **A QUESTION FOR VINAYAK: "is this true? <link>".** A message with a
   link plus other words is checked as TEXT (a pinned rule: a long
   forward's claim is in its words). But for "dekho <reel> sach hai kya" the
   words are only a question, and checking the reel itself would answer far
   better. Option: when exactly one checkable link is surrounded by a short
   question (a few words), check the link. Not done without his say
   (2026-10-15; it came up fixing review R3).
23. **Pass 2 can outlast the bot's wait.** 295 s measured against the bot's
   ~270 s poll window: the person is asked for "any message" to collect it.
   Either raise `_POLL_MAX`, or bound pass 2's search work (item 21 may
   solve it).
25. **The bot's right to name a person rests on "this request looks
   local"** (review R10, deferred 2026-10-16). Behind a local reverse proxy
   that adds no forwarding header (nginx's default shape), every visitor
   looks local and could name a fresh person per request, escaping every
   per-person limit; and if the bot ever runs anywhere but beside the app,
   its naming is ignored without a word and all of Telegram becomes one
   person. Neither is today's setup. Fix before either changes: a shared
   secret in `.env`, sent by the bot as a header and compared with
   `hmac.compare_digest`, honoured from anywhere; and a 202 that echoes the
   person it counted, so the bot can complain loudly when it was not.
26. ~~**After a bot restart, "wait for its answer" promises an answer the
   bot has forgotten**~~ **DONE 2026-10-16 with OPS-07**: the bot's pending
   checks are written through to `data/bot_pending.json` and a restarted bot
   delivers them (`Dispatcher.resume`). The original note (review R12): The bot keeps its
   pending job ids in memory; restarted while someone's check runs, it
   relays the one-in-flight refusal about a check whose answer will never
   arrive. Root fix: persist the pending job ids (OPS-07). Cheaper and
   complementary: for a BOT-named person only (never an address, where it
   would hand one NAT neighbour another's job), return the running job's id
   with the 429, so the bot can resume and deliver it.
27. **The address brakes do not apply on top of a device cookie** (the
   research's L3, deferred 2026-10-16). With a valid `vd` cookie the device
   IS the person (3 a day); the per-address limits (IPv6 /64 5, IPv4 20)
   then no longer count, so clearing cookies and solving Turnstile again
   buys 3 more — bounded by that friction, the hourly limit and the $1 day.
   Counting both (device AND address, all or none) touches every give-back
   path (refund, the free cache hit, both rollbacks), so it is its own step,
   with its own review.
28. **DECISION FOR VINAYAK, before 13 May 2027: DPDP Rule 8(3)'s one-year
   minimum retention** against the 30-day deletion (invariant 10), the
   notice, /delete and Telegram's delete-on-request. The facts and the
   options are recorded in §7 (2026-10-16, night). Take advice early 2027.
29. **Telegram's bot terms §4.4(a): data "encrypted at rest and stored
   separately from its encryption key".** The SQLite database (messages
   for 30 days, the bot's pending file) is plain. Cheapest: Windows Device
   encryption / BitLocker on this PC — an OWNER CHECK (Settings → Privacy &
   security → Device encryption); an encrypted disk on the VM later. Else
   encrypt the answer payloads with a key kept outside the database.
   **MEASURED 2026-10-23:**
   - Settings says "On", but `manage-bde -status C:` says **Protection
     Off, Key Protectors: None Found**. The key sits unsecured beside
     the data (a local account never activates it).
   - Not met until a TPM and recovery-password protector are added and
     enabled (HANDOFF §0 owner item 6).
   **DECIDED 2026-10-23 (Vinayak): leave protection OFF on this PC, and
   revisit at the move to the VM.**
   - A cloud VM's disk is normally encrypted by the provider.
   - Until then, Telegram §4.4(a) is a known, accepted gap. A lost or
     stolen laptop exposes what it holds, including 30 days of messages.
   - Weighed and not taken: turning it on (lockout only if the recovery
     key is lost too); and shortening retention to 7 days.
   - Do not reopen this before the VM unasked.
30. **Individualised advice** (Anthropic's Usage Policy from 12 Nov 2026:
   medical, legal and financial "High-risk AI Recommendations" need a
   qualified person's review; general information is excluded). "Is this
   forwarded health claim true?" is general information; "should I stop
   my medicine?" is not. The terms disclaim advice (dfb16b7); the prompt or
   triage should also decline the individual part and answer the general
   claim. A prompt change changes the cache fingerprint and needs one paid
   check to verify, so ASK first.
31. **A "report this answer" control** — required only if the app ever
   goes on the Play Store (Play's AI-content policy; pwa-app.md F9).
   Deferred with the Play route itself.
32. **The re-check's "notes, not findings"** (2026-10-17, the end of
   `docs/research/2026-10-16/review-fixes-step5.md`). All low; none blocks
   launch.
   - Task Scheduler's default priority 7 runs the app, the bot and ffmpeg
     below normal priority, on a PC the owner also uses.
   - `forget.py` does not find a bare job id typed in capitals. The page
     does not accept one either.
   - An unknown command followed by one or two words ("/check 5G se")
     gets the help text, not a check; with three or more it is checked.
     MEASURED 2026-10-17 (`classify_message`, offline): "/check 5G se
     corona", the review's own example, IS checked as text.
   - A claim stalled for more than 5 minutes is judged on an emptied
     per-person table, because `forget_idle` clears without re-dating.
     Only a sleeping machine stalls that long, and go-live.md sets sleep
     to Never.

**Closed on 2026-09-22 (kept so nobody re-opens them):**
- ~~The first paid run of the new engine~~ — done; measured in §8.
- ~~AFP whitelist~~ — kept trusted (my call, per Vinayak); not searchable
  (the crawler 400 names it), reached via Google Fact Check and pass 2.
- ~~Spend caps before going public~~ — 2/day, persisted, India's day.
- ~~Transcript cache for links~~, ~~Sonnet vs Opus A/B~~ (Sonnet stays),
  ~~answers never pruned~~ (30 days; costs kept), ~~bot handles one chat at a
  time~~, ~~raw exception text in answer.error~~ (all user-facing errors
  audited), ~~two SSRF host parsers~~ (one, `app/hosts.py`), ~~Facebook
  /reel/ form unprobed~~ (share links verified), ~~spending dashboard~~.
- ~~The 13 review findings of the evening~~ — all fixed, each with a test
  that fails against the old code (§7, "Two adversarial reviews").

**Settled earlier, kept for the record:**
- ~~Hindi ASR accuracy~~ → 2026-07-28: real Hinglish speech preserved every
  alphanumeric; the synthetic TTS voice caused the old 5जी loss.
- ~~The six public-link blockers~~ → all closed 2026-07-28.
- ~~Everything the pivot closed~~ → see the 2026-09-11 list in git history.

### Prerequisites already in place

- `.env` holds `ANTHROPIC_API_KEY`, `GOOGLE_FACTCHECK_API_KEY`, `SARVAM_API_KEY`,
  `HF_TOKEN`, `DB_PATH`, `TELEGRAM_BOT_TOKEN`. Never commit it;
  `.env.example` stays blank. Going live adds `PUBLIC_HOSTS`,
  `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`, `CONTACT_EMAIL`,
  `OPERATOR_NAME`, `SARVAM_ZERO_RETENTION`, `OWNER_CHAT_ID` and
  `BACKUP_DIR` (HANDOFF §0, the owner's list).
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

### WhatsApp notes (researched 2026-07-25; on hold — the Telegram bot was built instead)

*Superseded by the 2026-10-15 research (`docs/research/2026-10-15/whatsapp.md`,
summarised under §11 B). Kept for the record.*

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
