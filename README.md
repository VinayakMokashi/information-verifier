# Information Verifier

A multi-modal fact-checking engine built to combat fake news and propaganda in India.
Send **text, a screenshot, or a voice note** — the engine extracts the verifiable
claims, checks each against a **whitelist of trusted sources** (Indian fact-checkers,
government portals, wire services), and returns a **Truth Report** with a rating,
reasoning, the correction, and clickable citations.

Works in Hindi, Marathi, Tamil, Bengali and English. Mobile-first, no app to install.

> Status: text, image and audio/video all work end-to-end, with a mobile web page
> and a semantic claim cache. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for exactly
> where things stand and what's next.

## Why the design looks the way it does

- **The trusted-source whitelist is enforced, not suggested.** Web search is
  restricted server-side via Claude's `allowed_domains`, and Google Fact Check
  results are filtered through the same whitelist before they can reach the
  adjudicator. The engine cannot wander the open web — that restraint *is* the
  product.
- **Every LLM boundary returns a validated Pydantic object** (`messages.parse`).
  The output of this system is a public accusation of falsehood; "the model
  returned malformed JSON and we rendered it anyway" is not an acceptable
  failure mode.
- **The rating scale can abstain** (`UNVERIFIED`). Silence in the trusted sources
  is not evidence of falsehood; forcing a true/false call on a novel claim is how
  a fact-checker manufactures confident wrong answers.
- **A claim cache turns per-user cost into per-rumour cost.** One viral forward
  reaches millions. Exact re-forwards are free; paraphrases are matched
  semantically — but a cached verdict is *never* served on embedding similarity
  alone, because claims differing by a single token can embed closer than genuine
  paraphrases. A cheap LLM check confirms every match first.
- **We show you what we heard.** Speech-to-text and OCR are guesses. The
  transcript is displayed above the verdict, so a mis-hear is visible instead of
  becoming a confident answer to a question you never asked.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env      # then fill in ANTHROPIC_API_KEY
```

See it **free**, with simulated verdicts and no API key:

```powershell
.\.venv\Scripts\python.exe scripts\serve_demo.py    # http://127.0.0.1:8000
```

Run it for real:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Full walkthrough: [GETTING_STARTED.md](GETTING_STARTED.md).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/verify/text` | Submit text → `{job_id, status}` (202) |
| `POST` | `/api/v1/verify/image` | Submit an image (multipart `file`) |
| `POST` | `/api/v1/verify/media` | Submit audio or video (multipart `file`) |
| `GET`  | `/api/v1/reports/{job_id}` | Poll for the Truth Report |
| `GET`  | `/health` | Liveness |
| `GET`  | `/` | The mobile web page |

Submit, get a `job_id`, poll. The web page and any future WhatsApp or Telegram
bot use exactly this contract.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{"text": "WHO ne kaha hai ki 5G se coronavirus phailta hai."}'
# -> {"job_id":"<id>","status":"QUEUED"}
curl -s http://127.0.0.1:8000/api/v1/reports/<id>
```

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLite + sqlite-vec · ffmpeg
Claude Opus 4.8 (extraction, adjudication, vision OCR) · Claude Haiku 4.5
(language detection, retrieval, cache confirmation) · Sarvam Saaras v3 (Indic
speech-to-text) · EmbeddingGemma-300m (local embeddings, $0) · Google Fact Check
Tools API. No Node, no Docker, no build step.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

114 tests, always free — every paid API is faked, including a test that proves
the "free" demo mode cannot reach a paid provider.

## Documentation

- **[PROJECT_PLAN.md](PROJECT_PLAN.md)** — source of truth: status, roadmap,
  cost model, and the decisions log explaining why things are the way they are.
- **[GETTING_STARTED.md](GETTING_STARTED.md)** — step-by-step, for humans.
- **[CLAUDE.md](CLAUDE.md)** — conventions and invariants for AI sessions.
