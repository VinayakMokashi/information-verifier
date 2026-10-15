# Code audit: operations, reliability and privacy, running 24/7 for strangers

Audited 2026-10-15 against the repo as it stood then (free reproduction scripts, scratch databases, dummy keys). **Verification: independently verified (verdicts inline).** Durable copy of the agent's result (the raw journals are session-internal).

## Summary

I audited the repo at ee49622 for what breaks when it runs 24/7 for strangers, in shape H (this PC behind a named Cloudflare tunnel) and shape C (a cloud host behind the platform's proxy). The result is 28 findings: 3 blockers, 22 should-fix and 3 nice-to-have. Two leaks I was about to report were fixed by the other engineer while I worked (the Settings repr printing keys, e4a9822, and the bot token in error text, 63f8049), so they are not listed.

How it was checked: every script is free and ran from the scratch folder (so the repo's .env was never read), with dummy keys and a scratch database. Port 8000 was never used, data/verifier.db was never opened, and `git status` on the repo is still clean. Scripts and logs are in C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/audit/ops; the evidence fields call it `audit/ops/`.

**Blockers:**
- **OPS-01:** one request freezes the whole server. A 24 MB body to /verify/text runs the small-talk triage on the event loop before any limit applies. Measured: 6.2 s per request, /health waited 5.7 s, and the request ends in a refunded 413, so it costs the sender nothing.
- **OPS-02 (§11 A):** the cap is 5 checks a day for everyone. Messages like "a", "1" or "asdf" each buy a full check, so five of them shut everyone out until midnight India time.
- **OPS-03:** the per-visitor limit counts the connecting address, not the visitor. On a cloud host every visitor shares the proxy's single bucket; the obvious fix (`FORWARDED_ALLOW_IPS=*`) lets one visitor fake their address and skip the limit. On this PC, all Telegram users share one bucket. Measured for all four cases.

**Should-fix, by theme:**
- **Restarts lose paid work:**
  - A check killed mid-flight drops its spend from the ledger (measured: about $0.071 spent, ledger shows $0), keeps its daily slot, and must be paid for again. On a host, uvicorn waits for running checks with no limit, but the platform kills it after its grace period.
  - A second copy of the app on the same database marks the running copy's checks as failed before it dies on "address already in use". Measured: the bot told the person the check had failed, then it finished and was billed anyway. Ways to trigger it: share_demo.ps1, a hand-started uvicorn, link_smoke.py, start.ps1's 2 s health probe timing out, or `WEB_CONCURRENCY` starting extra workers.
  - run_check's final save has no guard. One SQLite error there leaves the job stuck "still running" forever and its stream never closes.
  - The bot keeps "which chat is waiting for which check" only in memory, so a bot restart means the answer is never sent.
- **Thread pool (§11 8, measured):** on a 1-vCPU host, 5 reel downloads made reading a finished answer take 19.4 s, while /health still answered in 10 ms.
- **The daily cap for strangers:**
  - Once the cap is reached, even free cached answers are refused.
  - If the screenshot-reading call fails, the slot is burned and the person gets a bare 500.
  - A viral forward sent by several people at once is paid for by each of them; the cache only helps after the first finishes.
  - Idempotency (§11 10): the screenshot-reading call runs before the reply, with the SDK's 600 s × 3 timeout. If the client gives up first (Cloudflare cuts at 100 s), the job is still billed and nobody can retrieve it.
- **Privacy:**
  - Server logs keep visitor IPs and job ids, and a job id opens that person's message through the public API (shown by replaying a logged id).
  - There is no privacy notice at all (§11 A), although messages go to Anthropic, Google, Sarvam and the video platforms.
- **Operations:**
  - /health always says ok (§11 6, §11 19).
  - There is no monitoring or alerting, and on a cloud host the owner cannot open the dashboard at all.
  - On a host, print() output is buffered and lost when the process is killed (measured).
  - The .env file and the database path are resolved from the working directory, so a different start directory means no keys and a fresh, empty database.
  - On this PC nothing restarts the app, bot or tunnel after a reboot, crash or sleep.
  - There is no Dockerfile or Procfile, and ffmpeg and a JavaScript runtime are not declared.
  - The requirements are unpinned: a fresh install today gets anthropic 1.14.0, a new major version built on httpx2, instead of the tested 0.119.0.
  - yt-dlp has no update path on a long-running server. With no JavaScript runtime installed it fetches YouTube in a deprecated mode, and the code silently discards the warning that says so.
- **No wall-clock limit (§11 23):** a check can run longer than the bot's ~270 s wait.

**Nice-to-have:** the bot's per-chat locks are never removed; uvicorn drops idle connections after 5 s while cloudflared keeps them 90 s, which causes occasional 502s; every public report includes what that check cost.

**Checked and fine:**
- WAL mode is on, with a 30 s busy timeout and an atomic single-statement claim for the cap.
- The India-time day boundary does not depend on the server's timezone.
- The 15 s live-stream heartbeat is well inside Cloudflare's 100 s idle limit.
- The per-visitor table is capped at 512 entries; finished streams take about 162 KiB each and are dropped after 15 minutes.
- The dashboard's local-only check holds under both shapes.
- On this PC uvicorn listens only on 127.0.0.1, so nothing is exposed to the home network.
- The installed yt-dlp is currently the latest release.

## Findings

### OPS-01. One unauthenticated request freezes the whole server: a 25 MB JSON body runs the small-talk triage on the event loop, before any limit
*blocker · applies to: both · `app/api/routes.py:259` · tracked: new*

**Scenario.** A stranger POSTs /api/v1/verify/text with a 24 MB 'text' (anything that is not a greeting). FastAPI parses it and nothing_to_check() loops over every character in Python ON THE EVENT LOOP (~6 s here, slower on a 1-vCPU host). Then the 5,000-char check rejects it with 413 and refunds both the daily slot and the per-visitor stamp. While it runs, every other request waits: page polls, SSE streams, the bot's submissions, /health. Repeating it at ~4 MB/s of upload keeps the service unusable for everyone, costs the attacker nothing, and is never counted by any limit.

**Evidence.** audit/ops/loop_block.py printed: 'triage alone on 25.2M chars: 6.2 s (body cap for every route = 25 MiB; text limit = 5000 chars)', 'attack request -> HTTP 413 after 6.8 s', 'meanwhile, GET /health (needs only the event loop) waited up to 5.7 s'. Code: routes.py:259 triages before _quota (261) and before the length check (262). main.py:59/156 LimitUploadSize applies max_media_bytes (config.py:70, 25 MiB) to EVERY route, JSON ones included. triage.py:38 is a per-character Python loop.

**Fix.** Cap JSON bodies for /verify/text and /verify/link at about 64 KB (in LimitUploadSize, by path or content-type) and keep 25 MB only for the multipart routes. Check len(req.text) > max_input_chars BEFORE triage, or triage only text[:max_input_chars]. Keep CPU-bound normalisation off the event loop.

**Verifier: reproduced.** Ran the earlier verifier's free script scratchpad/audit/vops/v01_loop.py (real app under uvicorn on a random 127.0.0.1 port, dummy keys, scratch DB). Output: '/health baseline 497 ms; during the attack: worst 5.31 s over 2 probes', 'attack -> HTTP 413 after 6.1 s: That message is 26214336 characters; the limit is 5000', 'daily slots used after it: 0  per-IP stamps: {127.0.0.1: 0}'. Code matches the finding: schemas.py:20 VerifyTextRequest.text has no max_length. main.py:59 LimitUploadSize uses max_media_bytes (25 MiB) for every route. routes.py:259 nothing_to_check() runs on the loop before _quota (261) and before the length check (262), and both the slot and the per-IP stamp are refunded. The JSON parse and pydantic validation of 25 MB also run on the loop, so the fix needs a per-route body cap and not only a reordered check. The attack costs nothing and is never counted, and one cheap VPS uploading about 4 MB/s keeps the loop blocked, so blocker under the 'cheaply lock everyone out' rubric stands.

### OPS-02. The 5-a-day cap is deployment-wide: five junk messages from one stranger lock everyone out until midnight IST
*blocker · applies to: both · `app/config.py:88` · tracked: 11.A*

**Scenario.** A curious visitor sends 'a', '1', 'x', 'asdf', 'test 2'. Each passes the free triage and buys a full check plus a slot, and failed checks keep their slot too. From then on every page visitor and every Telegram user gets 429 'This service has reached its daily limit of 5 checks. It resets at midnight India time' until 00:00 IST. That includes people whose answer is already cached for $0 (OPS-15).

**Evidence.** Triage probe from the scratch folder: 'a', '1', 'x', 'asdf' -> 'BUYS A CHECK + SLOT'; '?', 'hi' -> refused free. audit/ops/cap_semantics.py (cap 3): 'X again, cap reached -> HTTP 429: This service has reached its daily limit of 3 checks. It resets at midnight India time — please try again tomorrow.' limits.py:144 refuses first whenever used >= max_checks_per_day. routes.py:116-132 refunds only clean $0 cache hits.

**Fix.** The §11 A decision: per-person daily limits keyed correctly (OPS-03) under a daily dollar budget, a bot shield (Turnstile) checked before claiming, cache hits served without a slot (OPS-15), and the Anthropic console's monthly limit as the hard backstop.

**Verifier: confirmed-by-reading.** config.py:88 max_checks_per_day=5. limits.py:144 refuses everyone with _daily_refusal() once _daily.used(day) >= cap, with no per-person component. triage.py _SMALL_TALK refuses only whole-message greetings, so 'a', '1', 'x' and 'asdf' each buy a check and a slot (only 'test'/'testing' are refused). routes.py:116-132 _settle_quota refunds only clean $0 cache hits, so failed checks keep their slot. Five junk messages lock the web page and the bot (which goes through the same API) until midnight IST. This is a blocker by the rubric. It is tracked in 11.A.

### OPS-03. The per-visitor hourly limit counts the connecting address: behind a cloud proxy everyone shares one bucket, '*' makes it spoofable, and all Telegram users share 127.0.0.1
*blocker → **should-fix** (verifier) · applies to: both · `app/api/limits.py:119` · tracked: new*

**Scenario.** (C) The platform proxy connects from a private IP that uvicorn does not trust (FORWARDED_ALLOW_IPS defaults to 127.0.0.1), so request.client.host is the proxy for EVERY visitor. One stranger's 10 checks in an hour lock every other visitor out for that hour, at no cost to them, once the daily cap is raised for the public. The obvious fix, FORWARDED_ALLOW_IPS=*, makes uvicorn take the LEFTMOST X-Forwarded-For entry, which the client writes, so one visitor rotates it and is never limited. (H) Web visitors are keyed correctly (cloudflared on 127.0.0.1 is trusted and the rightmost XFF hop is the real IP), but every Telegram user arrives from 127.0.0.1 without XFF and shares one bucket. §11 A plans to build per-person limits on this key.

**Evidence.** audit/ops/proxy_ip.py, hourly cap 2. H (default trust): A,A,A,B -> 202,202,429,202. C (proxy untrusted, FORWARDED_ALLOW_IPS=10.0.0.1): A,A,B,C -> 202,202,429,429. C with '*': five requests from one visitor with spoofed first XFF entries -> 202 x5. H bot (no XFF): user1,2,3 -> 202,202,429. uvicorn 0.51: config.py:355-356 defaults FORWARDED_ALLOW_IPS to '127.0.0.1'; middleware/proxy_headers.py get_trusted_client_address returns x_forwarded_for_hosts[0] when always_trust.

**Fix.** Under C, set FORWARDED_ALLOW_IPS to the platform proxy's CIDR (never '*'), or read the platform's own client-IP header (Fly-Client-IP; CF-Connecting-IP only when the origin accepts Cloudflare IPs alone). Let _client_of take an end-user key the bot supplies (an HMAC of the chat id, sent with a bot-to-API shared secret) so each bot user gets their own bucket. Add a test with an untrusted peer.

**Verifier: confirmed-by-reading.** limits.py:118-119 keys on request.client.host. uvicorn 0.51 config.py:356 defaults FORWARDED_ALLOW_IPS to 127.0.0.1. proxy_headers.py get_trusted_client_address returns x_forwarded_for_hosts[0] (client-controlled) when always_trust ('*'), and otherwise the rightmost untrusted hop. So (H) web visitors are keyed correctly through cloudflared. Every Telegram user arrives from 127.0.0.1 (telegram_bot.py:34 APP_BASE) and shares one bucket. Under (C) every visitor shares the proxy's bucket. All of the mechanics are right. Downgraded because it is not reachable as harm today: the hourly limit is 10 and the global daily cap is 5 (config.py:78/88), so the daily cap always binds first and a shared or spoofable hourly bucket changes nothing at the current settings. It becomes a blocker as soon as the cap is raised or the 11.A per-person limits are built on this key, so it must be fixed together with OPS-02.

### OPS-04. A check killed mid-flight (redeploy, crash, reboot) loses its spend from the ledger, keeps the slot, and must be paid for again
*should-fix · applies to: both · `app/store/repository.py:431` · tracked: new*

**Scenario.** (C) A redeploy sends SIGTERM. uvicorn then waits with no time limit for running checks, but the platform kills the process after its grace period (tens of seconds) while checks run 30-295 s. (H) The same happens when the window is closed, the process crashes, or Windows Update reboots. On restart sweep_orphans marks the job FAILED ('The server restarted while this check was running.') with usage=None. backfill_from_answers skips rows without usage, so the pass 1 tokens, searches and ASR already bought never reach the ledger or the dashboard. The slot stays consumed and the person must resubmit and pay again.

**Evidence.** audit/ops/orphan_ledger.py: pass 1 billed into the job's meter (8,000 in + 2,500 out + 3 searches, about $0.071), then a hard kill. Output: 'after restart: status='FAILED' error='The server restarted while this check was running.' usage=None', 'dashboard ledger, all time: checks=0 usd=0 failed=0', 'daily cap counter: used=1 of 5'. job.py:129-135 writes usage only at the very end. repository.py:282 backfill skips usage None. uvicorn server.py:284-299 waits on timeout_graceful_shutdown=None; httptools_impl.py:310-311 tracks the background task as a server task.

**Fix.** After each paid step (each pass, each ASR batch) write the meter snapshot onto the row, and have the sweep record a ledger row ('interrupted') from it. On SIGTERM stop accepting new checks and mark in-flight jobs with their partial bill from the lifespan shutdown. Set --timeout-graceful-shutdown just below the platform's grace and raise that grace (Render and Fly allow up to 300 s). Consider letting an interrupted check be resubmitted without a new slot.

**Verifier: confirmed-by-reading.** job.py:128-135: answer.usage is written only in the finally, after chat.answer returns, and the ledger row is written right after it. A process killed mid-check leaves the row PROCESSING with usage None. repository.py:431-455 sweep_orphans sets FAILED and the restart error without touching usage. backfill_from_answers (repository.py:282) skips usage None, so that spend never reaches the ledger or the dashboard, which CLAUDE.md calls 'the truth'. The daily_checks slot is never refunded. Under (H) any closed window, crash or reboot triggers this, and under (C) any redeploy. should-fix is right, because the Anthropic console still holds the true bill.

### OPS-05. A second copy of the app on the same database fails the running copy's in-flight checks, then dies on 'address already in use'
*should-fix · applies to: both · `app/main.py:128` · tracked: new*

**Scenario.** uvicorn runs the lifespan (init_db + sweep_orphans) BEFORE binding the port. Any second start against the same DB marks every in-flight check FAILED, then fails to bind and exits. Second starts include: scripts/share_demo.ps1 in REAL mode (starts uvicorn on 8000 unconditionally); a hand-run 'uvicorn app.main:app'; scripts/link_smoke.py (TestClient(app) runs the lifespan); start.ps1 when its 2 s /health probe times out on a busy app; an extra worker (OPS-08). The bot polls, sees FAILED, tells the person 'Check nahi ho paya: The server restarted…' and drops the job. The original check then completes, is billed, and is never delivered.

**Evidence.** audit/ops/second_instance.py output: 'A, 2 s into the check: PROCESSING'. Instance B printed '[startup] failed 1 job(s) orphaned by a restart', then '[Errno 10048] error while attempting to bind'. Then 'A, right after B: status='FAILED''; 'bot.wait_for_report returned: FAILED -> ? Check nahi ho paya: The server restarted while this check was running.'; 'A, after its check really finished: status='COMPLETE' sections=1'. uvicorn server.py:104 awaits lifespan.startup() before create_server. share_demo.ps1:25, start.ps1:28, link_smoke.py:44.

**Fix.** Make the first lifespan step take an exclusive single-instance lock (an OS file lock on data/server.lock, or a SQLite row with pid + heartbeat), and exit before sweeping if a live owner holds it. Alternatively stamp an instance id on each job and sweep only rows whose owner's heartbeat is stale. Make share_demo.ps1 reuse a running app, and keep TestClient-based scripts off the real DB.

**Verifier: confirmed-by-reading.** uvicorn server.py: startup() awaits self.lifespan.startup() before creating listeners. main.py:122-128 runs init_db() and sweep_orphans() in the lifespan, so a second process on the same DB fails every QUEUED/PROCESSING row before it tries (and on Windows fails) to bind 8000. Real second starts exist. share_demo.ps1 REAL mode starts uvicorn on 8000 unconditionally. link_smoke.py:44 'with TestClient(app)' runs the lifespan against the configured (real) DB. start.ps1 starts a new app whenever its 2 s /health probe fails, which OPS-01 or a busy loop can cause. The bot then reports the restart error for a check that still completes and is billed.

### OPS-06. run_check's final save is unguarded: one SQLite error leaves a stuck job, a lost paid answer, a stream that never closes, and a wedged bot chat
*should-fix · applies to: both · `app/engine/job.py:132` · tracked: new*

**Scenario.** The docstring says 'Never raises', but the save in the finally, and the repo.get at line 50, are not guarded. One error at that moment ('database is locked' past the 30 s busy timeout, e.g. the owner has verifier.db open in a DB browser or a copy tool holds a lock; or 'database or disk is full' on a long-running host) causes all of this: the answer just paid for is lost; the ledger row (line 135) is never written; the row stays PROCESSING until the next restart; the stream never gets done/error, so it is never pruned and every SSE subscriber waits on heartbeats; the page loops on 'Abhi bhi chal raha hai'; the bot's chat is wedged, answering every later message with 'Aapka pichla check abhi bhi chal raha hai' until a restart.

**Evidence.** audit/ops/stuck_job.py makes only the final COMPLETE/FAILED save raise sqlite3.OperationalError('database is locked'). Output: 'POST -> 202', 'stream: done=False finished_at=None events=93 last='summary'', 'GET /reports -> status='PROCESSING' sections=0 usage=None', 'a day later, still registered: True'. stream.py:119-123 prunes only streams with finished_at set. telegram_bot.py handle_message's stale_job branch returns 'still running' while the report is not finished.

**Fix.** Guard each finalisation step separately: retry the save, still record the ledger, and ALWAYS publish error/done (stream finalisation in its own finally). Add an in-process periodic sweep that fails PROCESSING rows older than the maximum check duration, and prune streams by age, not only by finished_at.

**Verifier: confirmed-by-reading.** job.py:49 says 'Never raises', but line 50 repo.get and lines 130-132 (the finally's repo.save) are unguarded. If that save raises, the ledger record (135) and the stream's error/done (136-139) never run, the row stays PROCESSING, and _settle_quota is skipped. repository.py:405-409 prune deletes only COMPLETE/FAILED rows, so the message also outlives its retention until a restart sweeps it. In the bot, telegram_bot.py:651-676 answers every later message from that chat with 'pichla check abhi bhi chal raha hai' while wait_for_report returns None, which lasts until an API restart. The trigger is rare: db.py:105-108 sets a 30 s busy timeout with WAL, so it takes an external lock holder or a full disk. The consequences are severe enough that should-fix is fair.

### OPS-07. The bot forgets every in-flight check on restart: the answer is billed but never sent, and the person hears nothing
*should-fix · applies to: both · `scripts/telegram_bot.py:771` · tracked: new*

**Scenario.** The bot confirms Telegram's offset before doing the work, and keeps chat -> job only in memory. Restart it mid-check (a redeploy of the bot service on a host, closing its window, a reboot) and the check still completes and is billed, but no reply is ever sent. A follow-up 'kya hua?' is treated as small talk. A resend is a new check: a $0 cache hit if the first finished, but only if the cap still has room (OPS-15).

**Evidence.** telegram_bot.py:771 'self.pending: dict[int, str] = {}' (nothing persists it). :916 'offset = updates[-1]["update_id"] + 1' is confirmed before dispatch (by design, to avoid re-billing on redelivery). A restarted process starts with an empty Dispatcher.

**Fix.** Persist pending (chat_id -> job_id, plus prompted) in a small SQLite file of the bot's own, and on startup re-poll and deliver each entry. Or let the API store an opaque client_ref with each job so a restarted bot can list its undelivered jobs.

**Verifier: confirmed-by-reading.** telegram_bot.py:771 keeps pending only in memory. :916-918 confirms the update offset before dispatching. The comment at :718-719 ('Remembered BEFORE the wait: if this process dies mid-poll, the job is still recoverable on the next message') is false across a process restart, because a new Dispatcher starts with an empty dict. After a bot restart the check completes and is billed, and nothing is ever sent. A follow-up 'kya hua' is in _SMALL_TALK and gets the small-talk reply.

### OPS-08. WEB_CONCURRENCY silently starts several workers; nothing enforces the one-worker rule
*should-fix · applies to: cloud-host · `app/main.py:118` · tracked: new*

**Scenario.** uvicorn's --workers defaults to $WEB_CONCURRENCY, which some platforms and buildpacks set (Heroku's Python buildpack does). A plain 'uvicorn app.main:app' start command then runs N processes: N separate per-IP tables (N times the limit); N stream registries, so a page whose EventSource lands on another worker is replayed 'done' with no text; and every worker that starts, or is restarted by uvicorn's supervisor, runs sweep_orphans and fails its siblings' in-flight checks (OPS-05). The one-worker rule exists only in comments and docs.

**Evidence.** WEB_CONCURRENCY=2 python -m uvicorn app.main:app (CWD audit/ops, dummy keys, scratch DB; log in audit/ops/webconc.log) printed 'Started parent process [41464]', 'Started server process [43344]', 'Started server process [41044]' and two '[startup] spending dashboard' lines, i.e. two lifespans and two sweeps. Windows then failed to share the socket (WinError 10022), which is irrelevant on Linux. uvicorn config.py:351-352 reads WEB_CONCURRENCY.

**Fix.** Pass --workers 1 explicitly in every start command (Procfile/Dockerfile/start.ps1). Add a startup guard that refuses WEB_CONCURRENCY>1 or a held single-instance lock (OPS-05).

**Verifier: confirmed-by-reading.** uvicorn config.py:351-352 sets workers from WEB_CONCURRENCY when --workers is not given. No start command passes --workers 1 (start.ps1 runs '-m uvicorn app.main:app'), and app/main.py has no guard. The daily cap stays correct across workers because it is in SQLite. The per-IP table and stream registry (in memory) split, and each worker's lifespan runs sweep_orphans, which fails its siblings' jobs on any worker restart (as in OPS-05). This applies only to cloud hosts or buildpacks that set WEB_CONCURRENCY, so should-fix for (C).

### OPS-09. Thread-pool starvation, measured: on a 1-vCPU host five reel downloads stall every report poll and new submission while /health stays green
*should-fix · applies to: both · `app/api/routes.py:385` · tracked: 11.8*

**Scenario.** Several kinds of slow work all occupy asyncio's default pool: link downloads (up to 180 s, links.py:75), ffmpeg (up to 3 x 120 s), and resolves past their 60 s wall (the thread keeps running). That same pool serves every GET /reports, every job save and every new submission's row write, and it has min(32, CPUs+4) workers: 5 on 1 vCPU, 6 on 2, 20 on this PC. Five concurrent reel checks on a small host stall every reader of a finished answer, and every new text submission, for as long as the downloads run. Past 100 s these become Cloudflare 524s, and a submission stalled that long is billed but undelivered (OPS-13). /health stays instant, so a platform health check sees nothing wrong.

**Evidence.** audit/ops/starve.py (real routes, run_check, repository and gather_link_text; the download is a blocking sleep, as yt-dlp's is). 1 vCPU, 5 links x 20 s: 'GET /reports/<finished job> -> 200 in 19.40 s', 'POST /verify/text (new check) -> 202 in 19.41 s', 'GET /health -> 200 in 0.01 s' (baseline /reports 8 ms). 2 vCPU, 4 links: 0.03 s. This PC (20 workers): 5 links -> 0.02 s; 20 links x 10 s -> 8.79 s.

**Fix.** Run yt-dlp, ffmpeg and subtitle fetches on a dedicated bounded executor (like limits._pool), and cap concurrent link jobs with a semaphore that queues the rest. Give DB reads their own small pool so GET /reports never waits behind downloads. As a stopgap, install a larger default executor at startup.

**Verifier: confirmed-by-reading.** routes.py:383-389 runs download_link_audio and normalize_to_wav via asyncio.to_thread on the default executor. resolve_link (routes.py:490) does too, and its thread keeps running past the 60 s wait_for. get_report (553), _new_job (161) and _settle_quota (129) use the same default pool, which has min(32, cpu+4) workers: 5 on 1 vCPU. On this PC (20 workers, cap 5/day) it is not reachable. On a 1-vCPU cloud host, five concurrent link checks (exactly one day's cap) occupy the whole pool for the download duration, while /health (no thread) stays instant. Severity is right for a host and grows when the cap is raised.

### OPS-10. No database backup exists, and a plain file copy of the live WAL database is incomplete
*should-fix → **nice-to-have** (verifier) · applies to: both · `app/store/db.py:107` · tracked: 11.A*

**Scenario.** The spend ledger (the money record) and the daily counter live only in data/verifier.db. It is git-ignored and no backup code exists. A dead disk, an accidental delete, or (C) a volume never attached or lost erases the whole spending history. The obvious backup, copying verifier.db while the app is busy (Copy-Item, a sync folder, a scheduled copy), misses whatever is still in verifier.db-wal. In the test the copy did not even contain the ledger table.

**Evidence.** audit/ops/backup_copy.py: 'journal_mode: wal'; 'live database : 20 ledger rows, $3.20'; 'plain file copy : OperationalError: no such table: spend_ledger'; 'sqlite3 .backup() : 20 ledger rows, $3.20'. A grep for backup/VACUUM/wal_checkpoint in app/ and scripts/ finds nothing; the only mention is PROJECT_PLAN §11 A's to-do. .gitignore excludes data/.

**Fix.** Run a scheduled online backup (sqlite3 Connection.backup or VACUUM INTO) to a dated file, ship it off the machine or volume, and test a restore. To keep the 30-day promise, keep the content-free tables (spend_ledger, daily_checks) long-term but full-DB copies no longer than answer_retention_days.

**Verifier: confirmed-by-reading.** db.py:107 sets journal_mode=WAL. A grep for backup|vacuum|wal_checkpoint in app/, scripts/ and start.ps1 finds nothing, and .gitignore excludes data/. A plain copy of a live WAL database without its -wal file missing recent commits is standard SQLite behaviour. Downgraded because losing the DB does not harm users or open spend. The Anthropic console remains the authoritative bill and the hard backstop. A lost daily_checks row only resets today's counter. It costs the owner the dashboard history, which matters but is not a before-real-users item.

### OPS-11. Logs keep visitor IPs and job ids, and a job id read from a log opens that person's message through the public API
*should-fix · applies to: both · `app/api/routes.py:551` · tracked: new*

**Scenario.** uvicorn's default access log prints, on every poll, the visitor's real IP (taken from X-Forwarded-For) and the job id in the URL. On a host that is the platform's log store, plus any log drain, kept independently of the app's 30-day retention; on this PC it is the console window. Anyone who can read those logs can call GET /api/v1/reports/<id> and read the message, the OCR/ASR text and the answer for 30 days. The app's own prints add which reel was checked: routes.py:447 logs 'transcript cache hit for v2:<platform>:<video id>', and links.py:162 logs yt-dlp's error text, which carries the post id. limits.py:13-16 says a visitor's IP is personal data the app has no reason to write; the access log writes it anyway.

**Evidence.** audit/ops/logs.py and logs_unbuffered.py start the app the way start.ps1 does; requests come from 127.0.0.1 with XFF, as cloudflared sends them. Logged: 'INFO: 203.0.113.7:0 - "GET /api/v1/reports/12f9acd4e4024117ad0cea6efdf0c97d HTTP/1.1" 200 OK' (x3) and '[link] transcript cache hit for v2:instagram (simulated):FAKE-REEL-1: no download, no ASR'. Replaying the logged id: 'GET /api/v1/reports/12f9acd4... -> 200: input_text = 'My sister Priya (ward 14, Pune) says the new vaccine made her infertile - true?''.

**Fix.** Run uvicorn with --no-access-log, or a custom access logger that drops the client address and logs route templates instead of ids. Log the platform and outcome rather than video ids or URLs. Set the host's log retention to 30 days or less, and say what is logged in the privacy note.

**Verifier: confirmed-by-reading.** start.ps1 launches '-m uvicorn app.main:app' with the default access log. Through ProxyHeadersMiddleware that log prints the XFF-derived visitor IP and the full path, including /api/v1/reports/<job_id>. get_report (routes.py:550-556) needs only the id and returns input_text and source_text. routes.py:447 prints the transcript key, which carries the platform video id. links.py:239 prints up to 300 chars of yt-dlp error text, which can carry the URL or post id. Under (H) only the owner's console sees this, so it is low risk. Under (C) a platform log store keeps IPs and ids beyond the 30-day promise. should-fix stands for a host.

### OPS-12. No privacy notice anywhere, although strangers' messages go to Anthropic, Google, Sarvam, the video platforms and the host
*should-fix · applies to: both · `static/index.html:253` · tracked: 11.A*

**Scenario.** A stranger pastes a forward naming a relative and a health condition, or a screenshot of a family group. Neither the page nor the bot's /start text says any of the following. The text (up to 8,000 chars), the screenshot itself, transcripts, and search queries derived from them go to Anthropic. The first 250 characters go to Google's Fact Check API as a URL query parameter. The audio goes to Sarvam. The server fetches the linked post from Instagram/YouTube/Facebook. Traffic passes through Cloudflare or the host. Messages are stored for 30 days, and anyone holding the #job= link can read them. §11 A lists this note before any public URL.

**Evidence.** static/index.html:253-255 is the only notice on the page ('Answers cite fact-checkers and official sources. I can be wrong — open the sources…'). scripts/telegram_bot.py:59 HELP says nothing on retention or recipients. Recipients in code: chat.py:595 search_factcheck(text[:250]) -> factcheck.py:83 'query' param; vision.py:25 sends the image; asr.py:50 posts the audio; links.py downloads the post.

**Fix.** Put a short notice beside the composer and in /start: who receives what, the 30-day retention, 'anyone with this link can read this check', and 'don't send other people's private details'. Add a terms/disclaimer page and a contact, ideally with a delete-my-check action.

**Verifier: confirmed-by-reading.** static/index.html:253-255 is the only notice ('Answers cite fact-checkers... I can be wrong'). There is no mention of privacy, retention, recipients or link-holder access anywhere in static/. telegram_bot.py:59-70 HELP says nothing about storage or recipients. The recipients in code are confirmed: chat.py:595 search_factcheck(text[:250]) sends the text as factcheck.py:83's 'query' URL parameter, vision.py sends the image to Anthropic, and ASR sends audio to Sarvam. A missing notice is not itself a leak, so should-fix before real users is the right level.

### OPS-13. Idempotency gap: screenshot OCR runs before the 202 with a 600 s x 3 timeout, so a client or proxy that gives up leaves a billed check nobody receives
*should-fix · applies to: both · `app/api/routes.py:288` · tracked: 11.10*

**Scenario.** /verify/image makes the paid vision call inline, before the job exists, with no timeout of its own. The shared client allows up to 600 s per attempt and retries twice (with backoff, or up to 60 s when the API sends retry-after). Behind Cloudflare the browser gets a 524 at 100 s, and the page says 'Something went wrong on our side. Please try again in a minute.' Meanwhile the server finishes OCR, creates the job, runs and bills the check and uses a slot, and nobody holds the job id. The person retries and pays again. The same happens to any submission stalled behind OPS-09, or to a phone whose connection drops before the 202 arrives.

**Evidence.** audit/ops/edge_cut.py scales it down (the vision call takes 3 s, the client gives up at 1 s): 'vision client: timeout=Timeout(connect=5.0, read=600, write=600, pool=600) max_retries=2 (ocr_image passes neither)', 'client: gave up waiting for the 202 … - no job id', 'server: job rows=[('COMPLETE',)] | daily slots used=1'. vision.py:25 sets no timeout/max_retries; llm.py:12 is one shared client with SDK defaults (the claude-api reference confirms 10 min and 2 retries, with retried timeouts reaching timeout x 3).

**Fix.** Move OCR behind the 202, as /verify/media already does, so every route answers in about a second. Give ocr_image an explicit timeout (e.g. 60 s) and max_retries=1. Accept an Idempotency-Key (the page generates a UUID per submission and reuses it on retry; the bot uses chat:message_id) and return the existing job instead of creating another.

**Verifier: confirmed-by-reading.** routes.py:285-288 calls the paid ocr_image inline before the job exists, and spend.begin() means the slot is kept. vision.py:25 passes no timeout or max_retries. llm.py:12 is one shared AsyncAnthropic with SDK defaults (600 s, 2 retries). Cloudflare cuts at 100 s, the bot's _SUBMIT_TIMEOUT read is 300 s (telegram_bot.py:394), and the page's fetch has no retry key. When the vision API is slow or overloaded (retries), the client gives up while the server finishes, creates the job, bills it and keeps the slot, and the job id is never delivered. It is reachable only when OCR is slow, so should-fix is fair.

### OPS-14. A viral forward is paid for once per sender: identical submissions in the same minute all miss the cache
*should-fix → **nice-to-have** (verifier) · applies to: both · `app/engine/job.py:68` · tracked: new*

**Scenario.** The answer cache is consulted once when a check starts and filled only when it finishes, 30-295 s later. When a hoax goes viral, many strangers paste the same text within that window. Every one of them misses the cache, buys a full check ($0.05-0.17) and takes a daily slot. With public traffic this is the common case, not an edge case.

**Evidence.** audit/ops/viral.py: '4 strangers, same text, same minute -> engine runs=4, cached=[False, False, False, False], daily slots used=4'; 'a 5th, after they finished -> cached=True engine runs=4 slots used=4'.

**Fix.** Single-flight by cache_key: an in-flight map key -> job_id (in memory under the one-worker rule, or a SQLite table). An identical submission either gets the running job's id or waits for its result as a $0 cache hit, and gets its slot back.

**Verifier: confirmed-by-reading.** job.py:67-68 reads the cache once at start and :110 writes it only after chat.answer finishes, so identical concurrent submissions all miss, each pays, and each keeps a slot. The mechanism is real. Downgraded because this is a cost-efficiency optimisation, not a reliability or privacy defect. At the current 5/day global cap the extra spend is bounded to a few checks. The 'common case with public traffic' framing depends on a viral audience this deployment does not have yet. Worth doing together with the 11.A cap rework.

### OPS-15. Once the day's cap is reached, even $0 cache hits are refused
*should-fix · applies to: both · `app/api/routes.py:261` · tracked: new*

**Scenario.** Every route claims a slot before anything else; only later does run_check discover a cache hit and hand the slot back. When the day's checks are gone (by mid-morning with strangers), the most common request, a viral forward whose answer is already cached and costs nothing, gets 429 'please try again tomorrow'.

**Evidence.** audit/ops/cap_semantics.py: 'X again (cache hit, $0) -> HTTP 202 cached=True | slots used=2 (refunded: there was room)'; then 'X again, cap reached -> HTTP 429: This service has reached its daily limit of 3 checks…'. routes.py:261 runs _quota before job.py:67-68 looks up the cache; routes.py:116-132 refunds only afterwards.

**Fix.** For /verify/text, compute cache_key(text, language) and look up the answer cache BEFORE claiming, and serve a fresh hit without a slot (still under the per-visitor abuse limit). Do the same for links once the transcript key is known after resolve.

**Verifier: confirmed-by-reading.** routes.py verify_text: nothing_to_check() then `async with _quota(request)` claims the slot (limits.claim) BEFORE _new_job/background _check; the cache lookup happens only inside job.py run_check (`key = cache_key(text, language)`; `repo.cache.get`), and the refund is _settle_quota after the fact (cached and estimated_usd == 0 -> give_back_day). So when claim() refuses at the cap, a request whose answer is sitting in the cache gets the 429 just like a paid one. Same order on /verify/link (claim, then resolve, then transcript/answer cache in the background). It is reachable on both shapes and the bot goes through the same routes. Should-fix is right. It is a UX/fairness gap, not a money leak, and the fix must still sit under the per-visitor limit.

### OPS-16. Any error from the vision call burns the daily slot and returns a bare 500
*should-fix · applies to: both · `app/api/routes.py:285` · tracked: new*

**Scenario.** spend.begin() is set before ocr_image, so any exception from the vision call escapes as an unhandled 500 'Internal Server Error' and the slot is NOT refunded, even though a refused request was not billed. Such exceptions include an image the API refuses (size or format), an overload after retries, a timeout, or a rejected key. The page shows 'Something went wrong on our side'; the person retries the same photo and burns another slot. Five tries end the day for everyone.

**Evidence.** audit/ops/cap_semantics.py, with ocr_image raising anthropic.BadRequestError: '1. photo the vision API refused -> HTTP 500 body='Internal Server Error' | slots used=1 job rows=0'. routes.py:285-290; the refund at routes.py:111-112 runs only when not spend.started.

**Fix.** Catch anthropic.APIStatusError, APIConnectionError and APITimeoutError around ocr_image. Refund when the API answered with an error status (not billed) and return a readable 422/503. Check the upload's byte size, and ideally its dimensions, before calling, and reject oversize photos with 413 before any spend.

**Verifier: confirmed-by-reading.** routes.py verify_image: spend.begin() runs before `await ocr_image(...)` (vision.py makes a bare async_client.messages.create with no try). Any anthropic exception propagates out of _quota, whose except branch refunds only `if not spend.started`, so the slot is kept. grep finds no exception_handler anywhere in app/, so the client gets Starlette's plain 500 and index.html:581 shows 'Something went wrong on our side'. The most common trigger, which the audit underplays: LimitUploadSize allows 25 MB (max_media_bytes) for images too, and index.html does no client-side resize, but the Messages API rejects images over about 5 MB. So an ordinary phone-camera photo (5-12 MB) uploaded from the web page is refused by the API with a 400 every time and burns a slot on each retry. The Telegram path is mostly safe because msg['photo'] is Telegram's recompressed copy. The fix must refund only on an API error status (4xx, 529), not on a timeout, which may have been billed.

### OPS-17. No wall-clock bound on a check; the bot gives up at about 270 s and the page at about 8 minutes
*should-fix · applies to: both · `app/engine/chat.py:60` · tracked: 11.23*

**Scenario.** A check has no overall deadline. A link's download (up to 180 s), ffmpeg and ASR run first, then up to 6 continuations per pass, each a streamed request with a 600 s read timeout. The bot polls 90 x 3 s, about 270 s, against a measured 295 s pass 2, then asks the person for 'any message'. The page follows SSE for 240 s and polls for 240 s more, then shows 'Abhi bhi chal raha hai — refresh karke dobara dekhiye' (Hinglish on an English page).

**Evidence.** chat.py:60 _MAX_CONTINUATIONS = 6 with no deadline. telegram_bot.py:36-37 _POLL_S = 3.0, _POLL_MAX = 90. static/index.html:263 POLL_MS = 2500, POLL_MAX = 96, used for both follow() (line 504) and poll(). The 295 s pass is PROJECT_PLAN §11 23's measurement.

**Fix.** Give each check a deadline (asyncio.timeout around chat.answer that keeps the prose already written and marks it truncated), sized to include the link fetch. Make the bot's and page's windows exceed it, or let the bot deliver late answers by itself.

**Verifier: confirmed-by-reading.** chat.py:60 `_MAX_CONTINUATIONS = 6`, loop at :361, and no asyncio.timeout or deadline anywhere in chat.py or job.py. llm.py builds AsyncAnthropic with the SDK defaults (600 s timeout, 2 retries). telegram_bot.py:36-37 `_POLL_S = 3.0, _POLL_MAX = 90` (about 270 s), then it sends the 'Check abhi bhi chal raha hai ... koi bhi message bhejiye' message. index.html:263 `POLL_MS = 2500, POLL_MAX = 96` is used for both the SSE deadline (:504) and poll() (:451), and :471 throws the Hinglish 'Abhi bhi chal raha hai' on an html lang=en page. One mitigating fact: both surfaces recover without paying again. The bot's next message delivers the stale job (the pending/prompted path), and the page restores from the #job= hash (:479), so the answer is late rather than lost. Should-fix stands because a measured 295 s pass 2 already exceeds the bot's window for real users.

### OPS-18. /health is a constant: it stays green while the DB is locked, the pool is starved, the keys are missing, or it is the demo server
*should-fix · applies to: both · `app/main.py:166` · tracked: 11.6, 11.19*

**Scenario.** /health returns {'status':'ok'} without touching the database, the thread pool, the keys or the mode. A platform health check (C), start.ps1's probe and the bot's app_is_up (H) therefore all accept: an instance whose DB is locked or full; one whose pool is starved (OPS-09: /health 10 ms while /reports took 19 s); one started without .env, where every check fails and keeps its slot (OPS-21); or the free demo server (§11 19).

**Evidence.** main.py:164-166. serve_demo.py serves the same app object. audit/ops/starve.py: 'GET /health -> 200 in 0.01 s' while 'GET /reports/<finished job> -> 200 in 19.40 s'.

**Fix.** Keep /health as liveness. Add /ready: a DB write+read through the same pool /reports uses, with a short timeout; keys present; ffmpeg/ffprobe found; mode real|demo; version; in-flight checks; today's cap usage as a count. Point the platform health check and the bot's startup check at it, and have the bot refuse demo.

**Verifier: confirmed-by-reading.** main.py:164-166 `@app.get('/health') async def health(): return {'status': 'ok'}`. It touches no database, pool, keys or mode. start.ps1 Test-AppUp and the bot's app_is_up (telegram_bot.py:857-867) accept exactly that. start.ps1 does detect serve_demo.py by process name, so the demo case is partly mitigated on H, but nothing does this on C or for a hand-started demo. Should-fix is right.

### OPS-19. No monitoring or alerting at all, and on a cloud host the owner cannot even open the dashboard
*should-fix · applies to: both · `app/api/dashboard.py:48` · tracked: new*

**Scenario.** Nothing tells the owner about any of these: a spend spike; an error storm (a revoked key or a Sarvam outage fails every check, each keeping its slot); the cap exhausted by noon; yt-dlp breaking; the server being down. The only views are the console window (H) or platform logs (C, buffered: OPS-20), and /dashboard. /dashboard is served only to a request from 127.0.0.1 with Host localhost and no proxy header; on a cloud host no browser is ever that, so the spend record becomes invisible except from a shell inside the container.

**Evidence.** A grep for sentry, alert, notify, smtp, metrics and logging in app/ and scripts/ finds nothing. dashboard.py:48-59 _local_only requires peer in {127.0.0.1, ::1}, no proxy header, and a localhost Host header.

**Fix.** Send owner alerts through the bot that already exists: DM the owner's chat id when the cap reaches 80%, hourly spend exceeds $X, 3 checks fail in a row, the app starts with orphans, or a link probe fails. Point an external uptime monitor at /ready. Put /dashboard and /api/v1/admin/* behind Cloudflare Access or an owner token for remote viewing, keeping the local-only gate as well. Set the Anthropic console's monthly limit and Sarvam balance alerts.

**Verifier: confirmed-by-reading.** dashboard.py _local_only requires a peer in {127.0.0.1, ::1}, none of six proxy headers (cf-connecting-ip and x-forwarded-for included), exactly one Host header and a localhost Host. Behind any cloud proxy (C) the peer is a private proxy IP and the page always 404s, and on H through the tunnel it 404s too (it is intended for the PC itself). grep -il for sentry|smtp|notify|'import logging' over app/ and scripts/ finds nothing, and app/ has 41 bare print() calls. The Anthropic console's own usage page is the only remote spend view, and it does not show the daily cap or failures. Should-fix is right.

### OPS-20. On a host, print() diagnostics are block-buffered: lines show up hours late and are lost when the process is killed
*should-fix · applies to: cloud-host · `app/main.py:130` · tracked: new*

**Scenario.** Every diagnostic in the app is a bare print() with no timestamp. When stdout is a pipe (any PaaS, Docker without a TTY, systemd), Python buffers it in 8 KB blocks. At low traffic '[job] check failed …' appears hours late, and on a hard kill (OOM, an expired grace period, exactly when the log is needed) the buffered lines, '[startup] failed N job(s) orphaned' included, are lost. On this PC the console is a TTY and prints immediately, which hides the problem until the move.

**Evidence.** audit/ops/logs.py runs the server with stdout piped and then terminates it: the app's '[link] transcript cache hit …' print never appeared. audit/ops/logs_unbuffered.py (same with PYTHONUNBUFFERED=1): it did. uvicorn's own lines (logging, flushed per record) appeared in both runs.

**Fix.** Set PYTHONUNBUFFERED=1 (or python -u) in the deploy recipe. Move the prints to logging with timestamps and levels, with one config for app and bot.

**Verifier: confirmed-by-reading.** All app diagnostics are bare print() (41 in app/, plus the bot's) with no flush and no timestamp. CPython block-buffers stdout when it is not a TTY, while uvicorn's logging StreamHandler flushes per record, which matches the auditor's piped run. Some PaaS buildpacks set PYTHONUNBUFFERED (Heroku's does), but official python Docker images do not. The finding also reaches shape H once OPS-22's fix is applied: a service wrapper (NSSM or Task Scheduler) that redirects stdout to a file makes it a non-TTY, with the same buffering. Should-fix is right because the fix is one environment variable.

### OPS-21. Config is resolved from the working directory: a different start directory means no keys and a brand-new empty database
*should-fix · applies to: both · `app/config.py:25` · tracked: new*

**Scenario.** Start the app from any other directory: a Windows service or Task Scheduler (which start in C:\Windows\System32), a container WORKDIR, or a hand run from scripts\. It silently finds no .env, so every key is empty, and creates an empty database at ./data/verifier.db there. That means a fresh daily counter (5 more checks that day), an empty ledger on the dashboard, and 404s for old #job= links. It still starts and /health says ok. Every check then fails and keeps its slot, or, on a machine with an 'ant auth login' profile, the SDK quietly bills that account. Nothing at startup says which DB is in use or whether keys were found. DB_PATH in .env is relative too ('./data/verifier.db').

**Evidence.** audit/ops/cwd_config.py (child process with CWD = audit/ops, no key env vars; only app.config imported): 'db_path = ./data/verifier.db -> C:\Users\…\scratchpad\audit\ops\data\verifier.db', 'anthropic key = EMPTY', 'telegram token = EMPTY', 'daily cap = 5'. config.py:25 env_file='.env'; :38 db_path='./data/verifier.db'; .env line 14 DB_PATH=./data/verifier.db. start.ps1 works only because it sets the working directory (start.ps1:36-43).

**Fix.** Resolve .env and the default DB path from the project root (Path(__file__).resolve().parents[1]), or require an absolute DB_PATH outside development. At startup, print the absolute DB path and which keys are present (yes/no). Fail readiness, or refuse to start in real mode, when ANTHROPIC_API_KEY is empty.

**Verifier: confirmed-by-reading.** config.py `SettingsConfigDict(env_file='.env')`, `db_path: str = './data/verifier.db'`, .env:14 `DB_PATH=./data/verifier.db`, and db.py:105/155 connect and makedirs relative to the CWD. This verification task itself depends on that behaviour. The reachability is narrower than written: `python -m uvicorn app.main:app` from a wrong CWD fails loudly (app is not importable), and the bot from scripts\ prints 'No TELEGRAM_BOT_TOKEN' and exits. The silent case needs --app-dir or PYTHONPATH with another CWD. That is exactly what a service wrapper produces (NSSM's default AppDirectory is the exe's folder, .venv\Scripts), and it is the setup OPS-22 recommends, so it stays should-fix. start.ps1 is safe because it sets -WorkingDirectory $root.

### OPS-22. Home PC: nothing restarts the app, bot or tunnel after a reboot, crash or sleep
*should-fix · applies to: home-tunnel · `start.ps1:36` · tracked: new*

**Scenario.** The app and bot run in two console windows started by hand. A Windows Update reboot, a power cut, the PC going to sleep, a crash, or a closed window takes the site down until the owner notices and double-clicks start.cmd again. A named tunnel installed as a service would come back on its own and show Cloudflare error pages (502/1033) to every visitor in the meantime. The repo has no named-tunnel setup (share_demo.ps1 makes a temporary trycloudflare tunnel), no sleep prevention and no restart-on-failure; §7 2026-10-10 records the processes running unseen for a week.

**Evidence.** start.ps1:36-43 Start-Window launches 'powershell -NoExit' windows; :60 starts uvicorn in one of them; start.cmd ends in 'pause'. No Register-ScheduledTask, NSSM, sc.exe or powercfg anywhere. share_demo.ps1:31 runs 'tunnel --url' (a quick tunnel).

**Fix.** Run the app, the bot and 'cloudflared service install' (named tunnel) as services that start at boot and restart on failure (NSSM, or Task Scheduler 'at startup' with restart settings), with the working directory set explicitly (OPS-21). Disable sleep on AC power (powercfg), set Windows Update active hours, and add the external uptime monitor from OPS-19.

**Verifier: confirmed-by-reading.** start.ps1 Start-Window launches `powershell -NoExit` console windows. uvicorn runs with no service, no restart and no keep-alive option, and start.cmd ends in `pause`. The script's own banner says 'Keep both windows open and the PC awake.' There is no Register-ScheduledTask, NSSM, sc.exe or powercfg in the repo. Closing a window or a Windows Update reboot also discards all logs, which are only console scrollback. Should-fix for shape H is right.

### OPS-23. Cloud host: no deployment recipe, and system dependencies (ffmpeg) are undeclared; without ffmpeg every reel needing ASR fails after taking a slot
*should-fix · applies to: cloud-host · `app/providers/media.py:47` · tracked: new*

**Scenario.** There is no Dockerfile, Procfile or runtime pin, and the only launchers are Windows PowerShell scripts with .venv\Scripts paths. A host built from requirements.txt alone has no ffmpeg/ffprobe. Voice notes then get 'The audio in that file couldn't be read' (refunded). Every reel without subtitles is accepted, fails in the background with 'The audio in that post could not be read.' and keeps its slot, while /health stays ok. If DB_PATH is not pointed at the mounted volume, every redeploy wipes the ledger and resets the daily counter.

**Evidence.** media.py:47 raises MediaError('ffmpeg is not installed on this server.'). routes.py:399-412 turns it into the generic link failure after the 202, and the background path never refunds (routes.py:478-482 docstring). The repo root has no Dockerfile, Procfile or runtime.txt; start.ps1, start.cmd and share_demo.ps1 are Windows-only.

**Fix.** Write a Dockerfile: python:3.12-slim plus ffmpeg and deno, a non-root user, PYTHONUNBUFFERED=1, DB_PATH=/data/verifier.db on the volume, and CMD 'uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 120 --forwarded-allow-ips <proxy CIDR>'. Make /ready fail when ffmpeg/ffprobe are missing, and check for them before claiming a slot on /verify/link.

**Verifier: confirmed-by-reading.** media.py _run maps FileNotFoundError to MediaError('ffmpeg is not installed on this server.'). On the link path, gather_link_text calls normalize_to_wav behind the 202. _run_link_job's except calls fail_job with _friendly_link_failure (MediaError -> 'The audio in that post could not be read.'), and verify_link's docstring confirms that a background failure keeps the slot. The upload route runs normalize inline inside _quota without begin(), so it refunds, as stated. The repo root has no Dockerfile, Procfile or runtime.txt, and the only launchers are .ps1/.cmd. Applies to C only, and should-fix is right.

### OPS-24. Unpinned dependencies: a fresh install today pulls an untested major version, anthropic 1.14.0 on httpx2
*should-fix · applies to: both · `requirements.txt:2` · tracked: new*

**Scenario.** Every requirement is an open lower bound and there is no lock file. A new server, or 'pip install -U -r requirements.txt' here, resolves today to anthropic 1.14.0 instead of the tested 0.119.0. 1.x is a major release that moved to httpx2 and removed long-deprecated surface; starlette also goes to 1.8.0 instead of 1.3.1. The app monkeypatches messages.create/parse (usage.instrument) and relies on streaming and usage shapes that only the test suite would catch, and the suite already warns that starlette's TestClient is deprecating httpx. pytest is installed into production as well.

**Evidence.** pip index versions: anthropic latest 1.14.0 (installed 0.119.0), starlette 1.8.0 (installed 1.3.1), httpx 0.28.1. anthropic-1.14.0 wheel METADATA (audit/ops/dl_anthropic): 'Requires-Dist: httpx2<3,>=2.0.0'. The claude-api skill's sdk-upgrade guide says 1.x 'removed long-deprecated surface … HTTP layer moved from httpx to httpx2'. The stuck_job.py run printed 'StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.' requirements.txt:2 'anthropic>=0.116', :19 'pytest>=8.0'.

**Fix.** Freeze the tested venv into a lock file (pip-tools or uv, with hashes) and deploy from it. Cap majors in the meantime (anthropic>=0.116,<1) and do the 1.x upgrade deliberately. Move pytest to requirements-dev.txt.

**Verifier: reproduced.** requirements.txt has only open lower bounds (`anthropic>=0.116`, `fastapi>=0.115`, `httpx>=0.27`, `yt-dlp>=2026.8.19`, `pytest>=8.0` in the same file) and there is no lock file. Today `pip index versions` returns anthropic (1.14.0) and starlette (1.8.0), while the venv has anthropic 0.119.0 and starlette 1.3.1. The auditor's downloaded anthropic-1.14.0 wheel is present in audit/ops/dl_anthropic. A fresh install therefore crosses a major SDK version that the app monkeypatches (usage.instrument). Should-fix is right.

### OPS-25. yt-dlp has no update path on a 24/7 server, and with no JavaScript runtime installed it runs YouTube in a deprecated mode whose warning the app throws away
*should-fix · applies to: both · `app/providers/links.py:137` · tracked: new*

**Scenario.** The platforms change and yt-dlp must follow (requirements.txt:14-17: 'upgrade first when it breaks'). A long-running server has no update path. On this PC the venv stays at whatever was installed; on a host it changes only on redeploy, dragging the other unpinned packages with it (OPS-24). Reel links then fail for every stranger as 'That link could not be read' until someone notices. Separately, no JavaScript runtime (deno, yt-dlp's default) is installed here or declared for a host, so YouTube runs in yt-dlp's deprecated mode without one. yt-dlp warns 'YouTube extraction without a JS runtime has been deprecated, and some formats may be missing', but _Silent.warning and no_warnings drop that line, so the day YouTube stops working without a runtime, nothing explains why.

**Evidence.** Installed yt-dlp 2026.8.19, which is also the latest on PyPI today. 'which deno node' finds neither, and yt-dlp-ejs is not installed. yt_dlp/extractor/youtube/_video.py:2972-2999 selects the no-JS clients and issues that warning. links.py:137 'def warning(self, m): pass'; links.py:210 '"no_warnings": True'.

**Fix.** Keep yt-dlp out of the lock file and update it on a schedule (weekly 'pip install -U yt-dlp' plus a restart on H; a scheduled rebuild on C). Install deno on both shapes. Log yt-dlp warnings once per process instead of discarding them. Run the free scripts/link_probe.py daily against 2-3 known public reels and alert the owner when it fails.

**Verifier: confirmed-by-reading.** The tree moved: commit ca76538 (Facebook links) landed during this verification, so the line numbers shifted, but the cited code is unchanged. links.py:145-156 `class _Silent` has `def warning(self, m): pass` and `def error(self, m): pass`, and ydl opts set 'quiet': True, 'no_warnings': True, 'logger': _Silent() (:282-288). The installed yt_dlp/extractor/youtube/_video.py:2998 has the 'YouTube extraction without a JS runtime has been deprecated' warning. `which deno node` finds neither, and yt-dlp-ejs is not installed. Installed yt-dlp 2026.8.19 equals the latest on PyPI today, so it is current now, but the repo has no update mechanism. Should-fix is right.

### OPS-26. Slow memory growth: bot per-chat locks are never removed, and streams are pruned only when finished and only when a new check starts
*nice-to-have · applies to: both · `scripts/telegram_bot.py:772` · tracked: new*

**Scenario.** Dispatcher.locks gains one asyncio.Lock per chat ever seen and never drops it: about 164 B each, about 16 MB per 100k chats. pending and prompted also keep entries for chats that never come back. The stream registry is bounded for finished jobs (about 162 KiB each for 15 minutes) but keeps never-finished streams forever (OPS-06), and it prunes only inside create(). The per-IP table is capped at 512 entries and is fine.

**Evidence.** audit/ops/mem.py: 'stream registry: ~162 KiB per finished check (600 deltas), kept 15 min…', 'pruned only inside create(): 200 streams still held with no new job', 'per-IP table: capped at 512 entries (evicts LRU) -> bounded', 'bot Dispatcher.locks: 100000 chats -> 15.7 MiB, never removed (~164 B per chat ever seen)'. telegram_bot.py:648 locks.setdefault(...); stream.py:109 and :119-123.

**Fix.** Drop a chat's lock when it is free and the chat has no pending or in-flight work. Put a TTL on pending and prompted. Prune streams by age in the housekeeping loop as well as in create().

**Verifier: confirmed-by-reading.** telegram_bot.py:648 `locks.setdefault(chat_id, asyncio.Lock())`, Dispatcher.locks at :772, with no removal anywhere. stream.py _prune() is called only from create() and removes only finished streams older than the TTL. In practice streams are created only after a slot is claimed (_new_job is inside _quota), so at 5 checks a day the registry is tiny. Locks grow one per chat that ever messages, including small talk, at about 164 B each. Nice-to-have is right, or lower.

### OPS-27. uvicorn drops idle keep-alive connections after 5 s while proxies keep them 60-90 s, causing occasional 502s on POSTs
*nice-to-have · applies to: both · `start.ps1:60` · tracked: new*

**Scenario.** cloudflared keeps idle connections to the origin for 90 s by default, and an AWS ALB for 60 s; uvicorn closes them after 5 s. A request sent on a connection uvicorn has just closed is reset, and a proxy will not retry a POST. The result is an occasional 502 on /verify/*, which the page shows as 'Something went wrong on our side'.

**Evidence.** audit/ops/keepalive.py: 'reuse after 4s idle: … second={"status":"ok"}' and 'reuse after 6s idle: first=HTTP/1.1 200 OK | second=<ConnectionAbortedError>'. uvicorn main.py:530 defaults timeout_keep_alive to 5; start.ps1:60 passes no keep-alive option. cloudflared's 90 s keepAliveTimeout is its documented default and was not measured here.

**Fix.** Start uvicorn with --timeout-keep-alive 120, longer than any proxy's idle timeout.

**Verifier: confirmed-by-reading.** start.ps1 runs `python -m uvicorn app.main:app` with no --timeout-keep-alive, so uvicorn's default of 5 s applies. cloudflared's documented originRequest keepAliveTimeout is 1m30s. The real exposure is a narrow race, not every idle reuse. cloudflared's Go http.Transport watches idle connections and drops one when uvicorn's FIN arrives, so only a request dispatched in the same instant fails, and Go will not retry a POST. That makes the 502s occasional, which is consistent with nice-to-have. The auditor's raw-socket test overstates how often it happens.

### OPS-28. Every public report includes its own bill, which tells strangers which inputs cost the most
*nice-to-have · applies to: both · `app/models/answer.py:137` · tracked: new*

**Scenario.** GET /reports/{id} returns the whole Answer, including usage (models, tokens, estimated_usd). Strangers learn exactly what each of their checks cost the owner and which inputs are expensive (pass 2, long reels). Once the cap becomes a dollar budget, that tells an abuser how to spend it fastest.

**Evidence.** audit/ops/cap_semantics.py: 'per-check bill a stranger can read from GET /reports: True'. routes.py:551 response_model=Answer; answer.py:137 'usage: ReportUsage | None = None'.

**Fix.** Serve a public view without usage (response_model_exclude={'usage'} or a separate DTO), and keep the bill in the DB, the ledger and the dashboard.

**Verifier: confirmed-by-reading.** routes.py:551 `@router.get('/reports/{job_id}', response_model=Answer)`, and answer.py's Answer carries `usage: ReportUsage | None`. A visitor only ever sees reports for job ids they hold (their own checks, or ones shared with them), so this reveals per-input cost patterns, not the owner's total spend. Nice-to-have is right.

## Verifier: missed (new findings)

- Deleted messages stay on disk: no PRAGMA secure_delete or VACUUM anywhere (db.py sets only journal_mode=WAL and busy_timeout). Answers pruned after 30 days (repository.py:396-411) leave their text in SQLite free pages and in the -wal file until overwritten, and in any file copy or backup of the DB. This weakens invariant 10 ('Messages are forgotten') and compounds OPS-10's backup advice. Suggested severity: should-fix on a host and nice-to-have on (H).
- A job stuck in QUEUED/PROCESSING is never deleted by the retention prune (repository.py:408-409 deletes only COMPLETE/FAILED rows), so any stuck row from OPS-06 keeps that person's message beyond 30 days until a restart's sweep_orphans flips it. This is a privacy follow-on of OPS-06 that the finding does not mention.
- FastAPI's default /docs, /redoc and /openapi.json are public on any tunnel or host URL (main.py builds FastAPI() without docs_url=None or openapi_url=None). They advertise every endpoint, including the dashboard path, and its local-only check is then the only gate. Nice-to-have.
- The misleading comment at telegram_bot.py:718-719 ('if this process dies mid-poll, the job is still recoverable on the next message') claims crash-safety that the in-memory pending dict does not provide (see OPS-07). It should be corrected along with the fix so the next session does not rely on it.
- Retention gap that compounds OPS-04/OPS-06: AnswerRepository.prune() (repository.py:395-410) deletes only rows with status IN ('COMPLETE','FAILED'), and the only thing that fails QUEUED/PROCESSING rows is sweep_orphans() at startup. A job stuck in PROCESSING (OPS-06's unguarded final save, or a wedged pass) therefore keeps the sender's message in the database for as long as the process stays up, which can be past the 30-day retention promise (invariant 10). On a 24/7 server, a restart is not a schedule. The periodic housekeeping loop should also fail PROCESSING rows older than a hard ceiling, then prune them.
- The concrete everyday trigger for OPS-16, missing from the audit: LimitUploadSize applies the 25 MB media cap to /verify/image, and static/index.html does no client-side downscale, but the Messages API refuses images over about 5 MB (and over the pixel limits). So a normal phone-camera photo uploaded from the web page gets a 400 from the API, the user sees a bare 500, and the slot is burned on every retry. The fix needs a pre-spend byte and dimension check (413 before begin()), or a server- or client-side downscale. Refunds should go only on API error statuses (4xx or 529), never on a timeout, which may have been billed.
- On shape H, all operational history lives only in console-window scrollback. There is no log file and no rotation, so closing a window, a reboot or OPS-22's restart loses every '[job] check failed' and '[startup] failed N job(s) orphaned' line. Combined with OPS-19 (no alerting), the owner cannot reconstruct an incident after the fact. A rotating file log (timestamped, without message text, per OPS-11) belongs in the same change as OPS-20.

