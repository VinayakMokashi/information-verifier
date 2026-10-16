# Information Verifier

Paste a WhatsApp forward, a screenshot, a voice note, or an Instagram Reel /
YouTube Shorts / Facebook video link — and get back a straight answer about
whether it's true, with a confidence % and sources you can click.

The answer reads like a person explaining something, not a form: one piece of
prose, streamed as it's written, **in the language the rumour arrived in**.
Hindi, Marathi, Tamil, Bengali, English. Mobile-first, no app to install.

It checks fact-checkers and official sources first — Alt News, BOOM, Factly,
PIB, Snopes, Full Fact, WHO, CDC, NIH, NASA, NOAA, Cochrane, PubMed, and more.
If nothing vetted has covered the claim, it searches the wider web and **says
so**, in its own clearly-labelled section. General-purpose: health, science,
history, politics — not just Indian political rumours.

> Status: text, image, audio/video and pasted links (Instagram, YouTube,
> Facebook) all work end to end, with a streaming chat page and a Telegram bot.
> **Measured on real checks (Sept 2026): about $0.05 when a fact-checker has
> covered the claim, $0.15 when it has to search the wider web, $0 for a
> repeat.** Capped at 2 checks a day for now, with a spending dashboard for the
> owner. See [PROJECT_PLAN.md](PROJECT_PLAN.md) for exactly where things stand.

## Why the design looks the way it does

- **Tier is evidence, not assertion.** Whether an answer counts as
  "fact-checked" is computed from the host of every URL the API actually
  returned — never from what the model says about its own searching. It is
  recomputed on every serve, including cache hits.
- **The whitelist is enforced, not suggested.** Pass 1 restricts web search
  server-side via Claude's `allowed_domains`, and Google Fact Check results are
  filtered through the same list. The open web is a *second* pass that arrives
  labelled, in its own section, with its own sources and a capped confidence.
  Merging the two is how a reader ends up thinking a blog carried a
  fact-checker's authority.
- **The engine can say it doesn't know.** "Nothing reliable has addressed this"
  is a real answer. Silence in the trusted sources is not evidence of
  falsehood, and forcing a true/false call on a novel claim is how a
  fact-checker manufactures confident wrong answers.
- **Prose is never a receipt.** A model can write a convincing fake URL. Its
  markdown renders as *text* — no links, no images, no HTML — and every link
  you see comes from the structured citation objects the API returned. (This
  also closes an exfiltration path: a markdown image would fire on render and
  leak your forwarded message to whoever's server it points at.)
- **We show you what we heard.** Speech-to-text and OCR are guesses. The
  transcript is displayed above the answer, so a mis-hear is visible instead of
  becoming a confident reply to a question you never asked.
- **An answer cache turns per-user cost into per-rumour cost.** One viral
  forward reaches millions; the second person to send it pays nothing. Entries
  expire — "no fact-checker has covered this" is wrong the day one does.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock   # exact tested versions
.\.venv\Scripts\python.exe -m pip install -U yt-dlp              # kept current on purpose
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt  # to run the tests
Copy-Item .env.example .env      # then fill in ANTHROPIC_API_KEY
```

See it **free**, with a simulated Claude and no API key — the canned answer
streams word by word over the real SSE endpoint, so the transport is genuine:

```powershell
.\.venv\Scripts\python.exe scripts\serve_demo.py    # http://127.0.0.1:8000
```

Run it for real (one worker — the stream registry and the per-visitor limit
are in-memory):

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

What it has spent is at **http://127.0.0.1:8000/dashboard** — shown only to
the machine the server runs on, never through a share link.

Full walkthrough: [GETTING_STARTED.md](GETTING_STARTED.md).

## API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/v1/verify/text` | Submit text → `{job_id, status}` (202) |
| `POST` | `/api/v1/verify/image` | Submit an image (multipart `file`) |
| `POST` | `/api/v1/verify/media` | Submit audio or video (multipart `file`) |
| `POST` | `/api/v1/verify/link` | Submit a public Reel / Shorts / Facebook URL |
| `GET`  | `/api/v1/reports/{job_id}` | Poll for the finished answer |
| `GET`  | `/api/v1/stream/{job_id}` | Watch it being written (SSE) |
| `GET`  | `/health` | Liveness |
| `GET`  | `/` | The chat page |

Submit, get a `job_id`, poll — and optionally stream while you wait. The
persisted answer is always canonical; the stream is a preview. The web page and
the Telegram bot (`scripts/telegram_bot.py` — long polling, no tunnel; needs a
@BotFather token in `.env`) use exactly this contract.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/verify/text \
  -H "Content-Type: application/json" \
  -d '{"text": "Drinking hot water kills the coronavirus"}'
# -> {"job_id":"<id>","status":"QUEUED"}
curl -s -N http://127.0.0.1:8000/api/v1/stream/<id>     # live, as it is written
curl -s    http://127.0.0.1:8000/api/v1/reports/<id>    # the stored answer
```

## Stack

Python 3.12 · FastAPI · Pydantic v2 · SQLite · ffmpeg
**Claude Sonnet 5** (the whole check, streaming, plus vision OCR) ·
`web_search_20260209` · Google Fact Check Tools API ·
Sarvam Saaras v3 (Indic speech-to-text) · yt-dlp (link ingestion).
No Node, no Docker, no build step, no vector database, no local model.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

778 tests, always free — every paid API is faked, including a test that proves
"free" demo mode cannot reach a paid provider, one that proves every script can
still import what it claims to, and one that proves a chat on the Telegram bot
cannot pay for the same check twice.

## Documentation

- **[PROJECT_PLAN.md](PROJECT_PLAN.md)** — source of truth: status, roadmap,
  cost model, and the decisions log explaining why things are the way they are.
- **[GETTING_STARTED.md](GETTING_STARTED.md)** — step-by-step, for humans.
- **[CLAUDE.md](CLAUDE.md)** — conventions and invariants for AI sessions.
