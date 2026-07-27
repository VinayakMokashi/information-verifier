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

Two things that trip everyone up first:
- ⚠️ When the server starts, the terminal **looks frozen** — it isn't. That's the server
  running and holding that terminal. Leave it open; don't type in it.
- ⚠️ After you submit a claim, the first report check may say **`PROCESSING`**. That's
  normal — wait ~10 seconds and check again; it turns `COMPLETE`.

**1. Open a terminal in the project folder.** In VS Code: *Terminal → New Terminal*
(it opens in the project folder). Confirm the prompt ends in `...\Information_Verifier`.

**2. Start the server:**
```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```
Wait for `Application startup complete.` / `Uvicorn running on http://127.0.0.1:8000`.
The terminal now sits quietly — that means it's working. Leave it running.

**3. Open it in your browser: http://127.0.0.1:8000**

That's the actual app — paste a message, upload a screenshot, or send a voice
note, and the verdict appears on the page. Nothing else to do.

*(If you'd rather poke the raw API, **http://127.0.0.1:8000/docs** is the
interactive control panel; steps 4–5 below use that.)*

**4. Submit a claim:**
- Click **POST /api/v1/verify/text** → **Try it out**.
- In the Request body, keep the format: `{ "text": "your claim here" }`
- Click **Execute**. Under *Server response* you get code `202` and
  `{ "job_id": "…", "status": "QUEUED" }`. **Copy the `job_id`.**

**5. Read the Truth Report:**
- Click **GET /api/v1/reports/{job_id}** → **Try it out**.
- Paste the `job_id` → **Execute**.
- If `PROCESSING`, wait ~10s and **Execute** again. When `COMPLETE`, the response shows
  `overall_rating` and each claim's rating, confidence, reasoning, correction, citations.

**6. Stop the server:** click the terminal, press `Ctrl+C`.

> Prefer no copy-pasting? `scripts\smoke_test.py "your claim"` does the identical thing
> and prints the report directly.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError` | You didn't use the venv Python. Prefix with `.\.venv\Scripts\python.exe` |
| Report status `FAILED`, error mentions *authentication* | Key missing/typo in `.env` |
| `429` with *"You've used N checks this hour"* | That's our own spend guard, not the API. Tune it in `app/config.py`. |
| `429` / *rate limit* or *credit* error from Anthropic | Add credits at console.anthropic.com |
| Server won't start, "address in use" | Another server is running; close it or use `--port 8001` |
| Voice note gives `503` | `SARVAM_API_KEY` missing from `.env` |
| Voice note gives `413` | Clip is over 25 MB or 5 minutes — send a shorter one |
| The verdict answers a different claim than you sent | Check the "We read this from your file" line — the transcription was wrong. Retype it as text. |

---

## Sharing it with someone else

```powershell
.\scripts\share_demo.ps1              # real checks — costs money per check
.\scripts\share_demo.ps1 -DemoMode    # simulated verdicts — free
```

This prints a `https://….trycloudflare.com` link that works on any phone, with no
install on their side. In real mode **anyone with the link spends your API
credits**, so share it privately; built-in limits cap it at 10 checks per visitor
per hour and 100 per day (tune in `app/config.py`). Press `Ctrl+C` to stop — the
link dies with it.

---

## What each command gives you

| Command | Cost | What it proves |
|---|---|---|
| `scripts\demo_offline.py` | Free | The whole pipeline + cache + report logic works |
| `scripts\serve_demo.py` | Free | The real web page + API, with simulated verdicts |
| `python -m pytest tests -q` | Free | The full test suite (web, cache, media, trust filter) |
| `scripts\factcheck_probe.py "claim"` | Free | Which fact-check publishers we keep vs drop |
| `scripts\asr_probe.py clip.ogg` | ~paise | Sarvam transcription of one audio clip |
| `scripts\smoke_test.py` | ~cents | A real, cited fact-check on one claim |
| `uvicorn app.main:app` | free to run | The live web app: open http://127.0.0.1:8000 |
| `.\scripts\share_demo.ps1` | per check | A public share link (cloudflared quick tunnel) |

---

## The web page

Start the server (`uvicorn app.main:app` for real checks, `scripts\serve_demo.py`
for the free simulated demo) and open **http://127.0.0.1:8000** — a mobile-first
page where you can paste text, upload a screenshot/meme, or send a voice note /
video. To show friends on their phones, run `.\scripts\share_demo.ps1` and share
the printed `https://….trycloudflare.com` link (it dies when you press Ctrl+C —
and in real mode every check they run spends your API credits, so share privately).
