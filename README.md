# Information Verifier

A multi-modal fact-checking engine built to combat fake news and propaganda in India.
Submit text or an image; the engine extracts the verifiable claims, checks each one
against a **whitelist of trusted sources** (Indian fact-checkers, government portals,
wire services), and returns a **Truth Report** with a rating, reasoning, the correction,
and citations.

> **Phase 1** (this repo): text + image, running on SQLite with zero infrastructure.
> Audio/video and the WhatsApp/PWA surfaces are wired at the interface level and land in Phase 2.

## Why the design looks the way it does

- **The trusted-source whitelist is enforced by the model, not by us.** The engine uses
  Claude's native `web_search_20260209` tool with `allowed_domains`, so search is
  restricted to the whitelist server-side. No scraping, no result-filtering code.
- **Every LLM boundary returns a validated Pydantic object** (`messages.parse`). The
  output of this system is a public accusation of falsehood — "the model returned
  malformed JSON and we rendered it anyway" is not an acceptable failure mode.
- **The rating scale can abstain** (`UNVERIFIED`). Silence in the trusted sources is not
  evidence of falsehood; forcing a true/false call on a novel claim is how a fact-checker
  manufactures confident wrong answers.
- **A claim cache turns per-user cost into per-rumour cost.** One viral forward reaches
  millions; each hit would otherwise re-run the pipeline. (Phase 1 = exact match;
  Phase 2 = semantic via pgvector — see Roadmap.)

## Models

| Task | Model | Why |
|---|---|---|
| Adjudication, extraction, image OCR | `claude-opus-4-8` | Correctness and citation fidelity |
| Language detect + translation | `claude-haiku-4-5` | High-volume, cheap |

## Pipeline

```
normalize (Haiku)  ->  extract claims (Opus)  ->  per claim, in parallel:
    cache gate  ->  retrieve (web_search whitelist + Fact Check API)  ->  adjudicate (Opus)
->  aggregate  ->  persist  ->  Truth Report
```

## Setup

```bash
python -m venv .venv
# Windows PowerShell:  .venv\Scripts\Activate.ps1
# bash:                source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env          # then fill in ANTHROPIC_API_KEY (others optional)

uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs for interactive API docs.

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/verify/text` | Submit text → `{job_id, status}` (202) |
| `POST` | `/api/v1/verify/image` | Submit an image (multipart `file`) → `{job_id, status}` |
| `GET`  | `/api/v1/reports/{job_id}` | Poll for the Truth Report |
| `GET`  | `/health` | Liveness |

### Example

```bash
# 1. Submit
curl -s -X POST http://127.0.0.1:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{"text": "WHO ne kaha hai ki 5G se coronavirus phailta hai."}'
# -> {"job_id":"<id>","status":"QUEUED"}

# 2. Poll
curl -s http://127.0.0.1:8000/api/v1/reports/<id>
```

## Layout

```
app/
  main.py            FastAPI app + lifespan (init_db)
  config.py          settings + model IDs
  trusted_sources.py the whitelist (allowed_domains)
  api/               routes + wire DTOs
  models/            Pydantic contracts: Claim, Verdict, Evidence, TruthReport
  engine/            normalize, extract, retrieve, adjudicate, aggregate, pipeline, prompts
  providers/         llm (Anthropic), vision (OCR), factcheck (Google), asr (Sarvam Protocol)
  store/             SQLite db + repository (reports + claim cache)
```

## Roadmap (Phase 2+)

- **Semantic claim cache**: embed claims → pgvector similarity so paraphrased
  re-forwards also hit. (Anthropic has no embeddings API — needs an embedding model.)
- **Postgres + pgvector + ARQ/Redis** replacing SQLite + BackgroundTasks.
- **Audio/video**: wire `providers/asr.py` (Sarvam) into a `/verify/media` route;
  add keyframe extraction (needs `ffmpeg`).
- **Localization**: back-translate the summary into the user's input language.
- **Delivery surfaces**: WhatsApp Business Cloud API webhook; Next.js PWA.
```
