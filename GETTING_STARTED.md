# Getting Started — a step-by-step guide

This gets you from "code on disk" to "a live fact-check on a real claim."
Commands are for **Windows PowerShell** (your setup). Run them from the
project folder: `c:\Users\Vinayak Mokashi\Python Sab\Information_Verifier`.

---

## Step 0 — What's already done (one-time setup)

These were done for you already; listed here so you can redo them on another
machine:

```powershell
python -m venv .venv                       # create an isolated Python environment
.\.venv\Scripts\python.exe -m pip install -r requirements.txt   # install libraries
```

You do **not** need to repeat these unless you move the project.

> Tip: the safe way to run anything is with the venv's own Python:
> `.\.venv\Scripts\python.exe ...`. That guarantees the installed libraries are found.

---

## Step 1 — See it work for FREE (no key, no cost)

This runs the **real pipeline** with **simulated** AI answers, so you can see a
full Truth Report and how the cache works — without spending a paisa.

```powershell
.\.venv\Scripts\python.exe scripts\demo_offline.py
```

You'll see two runs: the first "cold", the second served entirely from cache.
If you see a formatted TRUTH REPORT, everything is wired correctly.

---

## Step 2 — Get an Anthropic API key (needed for REAL checks)

1. Go to **https://console.anthropic.com** and sign in (this is separate from
   your claude.ai chat subscription).
2. Open **Billing** → add **$5** in credits. That covers dozens to a few
   hundred test checks.
3. Open **API Keys** → **Create Key** → copy it (starts with `sk-ant-...`).

> Optional, free: a **Google Fact Check API** key adds structured fact-checker
> data. Get one at https://console.cloud.google.com (enable "Fact Check Tools
> API"). The app works fine without it.

---

## Step 3 — Put the key in a `.env` file

```powershell
Copy-Item .env.example .env
notepad .env
```

In Notepad, paste your key after `ANTHROPIC_API_KEY=` so the line reads:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Save and close. (The `.env` file is git-ignored, so your key won't be shared.)

---

## Step 4 — Run a REAL fact-check (costs a few cents)

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py
```

Or check your own claim:

```powershell
.\.venv\Scripts\python.exe scripts\smoke_test.py "Aadhaar card is mandatory to vote in India."
```

This runs the genuine engine — real reasoning, real web search of the trusted
sources — and prints a real Truth Report.

---

## Step 5 — Run it as a web service (for the app/UI later)

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** in your browser. This is an
auto-generated control panel where you can:

- expand **POST /api/v1/verify/text**, click *Try it out*, type a claim, **Execute**
- copy the `job_id` from the response
- expand **GET /api/v1/reports/{job_id}**, paste the id, **Execute** to read the report

Press `Ctrl+C` in the terminal to stop the server.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | You didn't use the venv Python. Prefix with `.\.venv\Scripts\python.exe` |
| Report status `FAILED`, error mentions *authentication* | Key missing/typo in `.env` |
| `429` / *rate limit* or *credit* error | Add credits at console.anthropic.com |
| Server won't start, "address in use" | Another server is running; close it or use `--port 8001` |

---

## What each command gives you

| Command | Cost | What it proves |
|---|---|---|
| `scripts\demo_offline.py` | Free | The whole pipeline + cache + report logic works |
| `scripts\smoke_test.py` | ~cents | A real, cited fact-check on one claim |
| `uvicorn app.main:app` | free to run | The live web API a UI/WhatsApp bot will call |
