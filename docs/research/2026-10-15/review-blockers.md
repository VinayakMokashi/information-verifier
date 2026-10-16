# Adversarial review of the 2026-10-15 security/ops fixes

status: complete

Reviewer: subagent (Opus 5.5), 2026-10-15. Scope: the fixes committed today —
e4a9822, 63f8049, 9a737bd, ca76538, 50dcf3b, 1080d2d, 020e26f — read against
docs/research/2026-10-15/audit-security.md and audit-ops.md.

Every finding below was reproduced with a free script under the session
scratchpad (`scratchpad/review/`), run with that folder as the working
directory, `DB_PATH` on a scratch file, and every key set to the dummy
`invalid-audit-key`. No paid call, no real database, no port 8000.

The working tree was being edited live during this review (55d3de0, the
per-person daily allowance, landed after it started, and more was
uncommitted), so the scripts run against `git archive` snapshots of fixed
commits in `scratchpad/review/snap-<sha>/` (020e26f = the seven fixes; 55d3de0
and then 0951150 = HEAD as it moved), never the live tree. `_rboot.py` asserts
which snapshot was imported (`REVIEW_SNAP=<sha>` selects it). Each finding
says whether it still holds at 55d3de0 and at 0951150 (the $1-a-day budget,
which landed while this review ran).

## Summary

| # | Severity | Commit | In one line |
|---|---|---|---|
| R1 | blocker - FIXED 5f8e7db (re-checked) | 020e26f | The refunded-hold lockout still works with 5 subjects (5 IPv6 /64s from one free /48); at 0951150 three suffice and also force everyone into the no-search shortcut mode |
| R2 | should-fix - FIXED 2f4d825 (re-checked) | ca76538 | `https://www.facebook.com:<port>/share/...` makes the server connect to any port; Facebook drops them, so each is a free ~31 s hold (and, with a raised cap, pool starvation) |
| R3 | should-fix - FIXED 2f4d825 (re-checked) | ca76538 | A share link + newline (a normal Telegram message) is an uncaught `httpx.InvalidURL` -> 500 -> "try again later"; it was a 422 before |
| R4 | nice-to-have - FIXED 456701b (re-checked) | 1080d2d, 50dcf3b | With a root_path (`--root-path` / `UVICORN_ROOT_PATH`) both middlewares stop matching: cross-site POSTs pass again, uploads over 64 KiB are refused |
| R5 | nice-to-have - FIXED 786c046 (re-checked) | 1080d2d | A DNS-rebinding page is "same-origin" and passes; the paid routes never check Host |
| R6 | nice-to-have - FIXED 05418fa (re-checked) | 020e26f | The person is released after the bookkeeping, so "poll until COMPLETE, then submit" gets "already running" about half the time |
| R7 | nice-to-have - FIXED 478a2c1 | 50dcf3b | The pinned body-cap arithmetic is x6 per character; an emoji is x12 |
| R8 | nice-to-have - FIXED ba0653e (re-checked) | (63f8049's class) | `scripts/factcheck_probe.py` prints the Google key on any HTTP error; `ANTHROPIC_LOG=info` makes the app log it on every lookup |
| R9 | should-fix - FIXED 2d3b5c8 (re-checked) | 020e26f | One in flight per IPv4 address = per carrier-NAT pool/office: strangers told "you already have a check running" |
| R10 | nice-to-have - DEFERRED (PROJECT_PLAN 11.25) | 020e26f | Bot identity is inferred from "looks local": spoofable behind a header-less local proxy, silently collapses if the bot moves |
| R11 | nice-to-have - FIXED 05418fa + 2147412 (re-checked) | 020e26f | A check longer than the 900 s TTL: its late release pops the next check's entry (two run at once) |
| R12 | nice-to-have - FIXED with OPS-07 (2026-10-16; the bot's pending checks persist and resume) | 020e26f x OPS-07 | After a bot restart, "wait for its answer" promises an answer the bot forgot |
| R13 | nice-to-have - FIXED 2d3b5c8 (re-checked) | 020e26f | All anonymous group admins (and all "post as channel" senders) are one Telegram person |
| R14 | should-fix - FIXED 2d3b5c8 (re-checked) | 0951150 (outside the seven) | Cache-hit repeats skip every limit: unbounded job rows and in-memory streams from one visitor |
| R15 | should-fix - FIXED 3bd7772 + 4f6be5c (re-checked) | 020e26f (+5f8e7db) | `release()` (and at HEAD `admit()`) take the limiter lock on the event loop while a claim holds it across a contended SQLite write: /health froze 7 s |

Sound (details at the end): release exactly once on all 28/29 route paths at
all three snapshots; cancellation; the hop-by-hop SSRF fence; RefuseCrossSite's
header handling and the app's own page in real Chrome; the body cap for every
legitimate request; Settings never displays a key; the bot's token paths; the
20 MiB Telegram rule.

## Findings

### R1. The refunded-hold lockout (audit blocker 5) still works: it needs five visitors instead of one
*blocker · 020e26f (with ca76538 as the amplifier, R2) · `app/api/limits.py:194` (the daily fast path) and `app/api/routes.py:533` (the claim before the free resolve) · still true at 55d3de0; WORSE at 0951150 - three subjects suffice (below)*

**Scenario.** The fix stops ONE subject from holding several slots (one check
in flight per person). It does not stop five subjects from holding one each.
Five IPv6 /64s (one free Hurricane Electric /48 is 65,536 of them; or five
IPv4 addresses) each submit one link whose free resolve is slow and then
refused. While they run, all five daily slots are taken, and every other
person - web and Telegram - is told "This service has reached its daily limit
of 5 checks ... please try again tomorrow". Each attempt is then refunded:
no job row, no ledger row, $0, nothing on the dashboard. The hourly limit
allows each subject 10 such holds an hour, so a continuous lockout needs
about 5 x 3600 / (10 x hold) subjects an hour - with R2's ~31 s hold, about
60 /64s an hour. The audit's third fix item for this finding - "do not tell
people 'try tomorrow' when slots are only held" - was not done, and the
HANDOFF line "which also ends the free refunded-link lockout (blocker 5)"
overstates the fix. The pinning test,
`tests/test_per_person.py::test_slow_refunded_links_cannot_hold_everyones_slots`,
sends all five links from ONE TestClient peer, so it passes while the
lockout stands. Raising the cap does not help: N slots need N subjects, and
a /48 holds 65,536.

**Reproduction.** `scratchpad/review/r05_lockout_five.py`: real uvicorn on a
random port, visitors arriving as the tunnel delivers them (127.0.0.1 +
X-Forwarded-For), `www.facebook.com` resolved to a local socket that accepts
and never answers. Printed at 020e26f, and identically at 55d3de0:

```
== 1. one visitor, five at once
   answers: 4 x (429, 'You already have a check running...'), 1 x (502, ...)
== 2. five visitors (five /64s), one each
   held: used_today=5 of 5  in_flight=[five ip6:2001:db8:0:N::/64 subjects]
   an unrelated visitor's text check -> HTTP 429: This service has reached its daily
   limit of 5 checks. It resets at midnight India time — please try again tomorrow.
   attackers' answers after 17.1 s: [(502, 'The platform could not be reached right now...')]
   afterwards: used_today=0  answers rows=0  spend_ledger rows=0
```

**Worse at HEAD 0951150 (the $1-a-day budget, landed during this review).**
A link claim now RESERVES $0.30 of the $1.00 before its free resolve, so
THREE held links commit $0.90, the day's mode reads "shortcut", every other
person's screenshot, voice note and link is refused "until midnight", and
their texts are answered in the no-search shortcut mode - all for free, all
refunded afterwards. `scratchpad/review/r05b_lockout_budget.py`
(REVIEW_SNAP=0951150, default settings):

```
held by 3 subjects: committed $0.90  mode now: shortcut
  victim's reel link -> (429, "Today's budget for this service is nearly used up. Screenshots,
  voice notes and links can be checked again after midnight India time; ...")
  victim's text      -> (202, ...)      the engine was told mode=['shortcut']
attackers' answers: [(502, 'The platform could not be reached right now...')]
afterwards: committed $0.00  mode full
```

**Suggested fix.** Do not hold a DAILY slot - or, at HEAD, a budget
reservation - during free work. For /verify/link, run the free resolve under
the per-person in-flight gate only, and take the slot and the reservation
(atomically, as now) after it succeeds; same for the media route's free
ffmpeg decode. Independently: when the cap or budget is reached only by
unsettled claims, say "busy - try again in a minute", never "tomorrow", and
do not let unsettled reservations choose the budget mode. Optionally count
IPv6 by /56 for the in-flight and hourly limits.

### R2. A Facebook share link with an explicit port makes the server connect to that port, and hold a slot for ~31 s
*should-fix · ca76538 · `app/providers/links.py` `expand_share_link` (and `allowed_link_host`, which admits any port) · still true at 55d3de0 and at 0951150*

**Scenario.** `allowed_link_host` reads only the host, so
`https://www.facebook.com:1/share/r/x/` (or `fb.watch:6379/...`) passes, and
`expand_share_link` requests exactly that port. Before ca76538 such a URL
failed at once with no request: none of the pinned extractors claims a URL
with a port. Now (a) any visitor can make the server open TCP connections to
any port on Facebook's hosts from the owner's home IP, and (b) because
Facebook's edge silently drops closed ports, every such link is a reliable,
free ~31 s hold of the person's in-flight slot and one of the day's slots,
ending in a refunded 502 - the cheapest way to drive R1.

**Reproduction.** `scratchpad/review/r03_share_port.py` (hermetic) printed
`allowed_link_host=www.facebook.com requested=['www.facebook.com:1']` (also
`:22`, and `fb.watch:6379`), "pinned extractors claiming
https://www.facebook.com:1/share/...: none", and through the real route with
a filtering socket: `3 s in: used_today=1 (of 5) in_flight=['ip:testclient']`,
then `HTTP 502 after 15.9 s`, refunded. ONE live, free connection attempt by
the app's own `expand_share_link` (`scratchpad/review/r06_live_port_probe.py`):
`https://www.facebook.com:1/share/r/17RQxbYP2j/ -> after 31.0 s:
LinkError[network] The platform could not be reached right now.`
Before/after, network blocked (`scratchpad/review/r19_before_after_ca76538.py`):
at ca76538^ `resolve_link -> LinkError[other] That link could not be read.
(0.5 s)`, route `HTTP 422`, no connection attempted; at 020e26f the same URL
attempts the connection (`LinkError[network]`, route `HTTP 502`).

Once the daily cap is raised (the per-person allowances of 55d3de0 are the
step towards that), the same holds also starve asyncio's default thread pool
(20 threads here; every resolve is a `to_thread`), and every read of a
finished answer waits behind them (OPS-09's mechanism, now on demand):
`scratchpad/review/r17_share_port_pool.py`, cap 100, 30 holds from 30 /64s:
`GET /reports before: 0.02 s`, `GET /reports during 30 port-trick holds
from 30 /64s: 21.84 s`. At today's cap of 5, at most 5 holds run at once.

**Suggested fix.** Refuse an explicit port other than 443 for fetchable links
(in `allowed_link_host`, so the route, the bot's classifier and the share
expansion all agree), and give the share expansion one overall deadline
(e.g. 10 s for all hops), not 15 s per socket operation per hop. Run link
resolves on a small pool of their own, not asyncio's default one.

### R3. A share link with a line break after it is a 500, and the bot says "try again later" - which can never work
*should-fix · ca76538 · `app/providers/links.py` `expand_share_link` (only `httpx.HTTPError` is classified) · still true at 55d3de0 and at 0951150*

**Scenario.** A Telegram user sends a Facebook share link with a question on
the next line ("https://www.facebook.com/share/r/17RQxbYP2j/\nKya yeh sach
hai?"). The bot's classifier reads only the host, so it is a "link". Python's
`urlsplit` silently drops tab/CR/LF, so `allowed_link_host` and
`_is_share_link` both pass; httpx then refuses the URL with `httpx.InvalidURL`,
which is not an `httpx.HTTPError`, so it escapes `expand_share_link` and
`resolve_link` and the route answers a bare 500. The bot turns that into
"Server par kuch gadbad hai — thodi der baad dobara bhejiye" - the same
"try again later that can never come true" 9a737bd removed for big files.
Before ca76538 this URL reached yt-dlp and got a readable 422. (No money or
slot is lost: `_quota` refunds and releases.) The same uncaught path exists
for hop Locations httpx cannot parse (`https:evil.example`, a non-ASCII
host, `javascript:`) - Facebook-controlled, so only a 500, never a fetch.

**Reproduction.** `scratchpad/review/r04b_share_newline_bot.py` (real
handle_message + AppClient against the real app over ASGI) printed:
`classify_message -> ('link', 'https://www.facebook.com/share/r/17RQxbYP2j/\nKya yeh sach hai?')`,
`[bot] API answered 500 with no detail`,
`bot says: 😕 Server par kuch gadbad hai — thodi der baad dobara bhejiye.`
`scratchpad/review/r04_share_edges.py` part B: tab, LF and CR variants each
`route -> HTTP 500 Internal Server Error`; part A: `UNCAUGHT InvalidURL` /
`UnicodeEncodeError` / `InvalidCodepoint` for those Locations.
`scratchpad/review/r19_before_after_ca76538.py`: at ca76538^ the same
message gives `HTTP 422 {"detail":"That link could not be read."}`; at
020e26f `UNCAUGHT InvalidURL: Invalid non-printable ASCII character in URL,
'\n' at position 44.` and `HTTP 500 Internal Server Error`.

**Suggested fix (R3).** In `expand_share_link`, treat any exception from building
or requesting a URL as `LinkError` (catch `Exception`, or at least
`httpx.InvalidURL` and `ValueError`), and refuse a link containing any
control character or whitespace in `allowed_link_host` (fail closed, the
module's stated discipline) - or have the bot and route take only the first
whitespace-delimited token as the link.

### R4. RefuseCrossSite and the upload cap read `scope["path"]`, which uvicorn prefixes with root_path - set one, and both silently stop working
*nice-to-have (latent: no launcher sets it today) · 1080d2d + 50dcf3b · `app/main.py:69` and `app/main.py:156` · still true at 55d3de0 and at 0951150*

**Scenario.** uvicorn builds `scope["path"] = root_path + path`, and takes
root_path from `--root-path` or the `UVICORN_ROOT_PATH` environment variable
(click's `auto_envvar_prefix`). Starlette routes on the path with root_path
stripped (`get_route_path`), so every route still works - but the two raw
middlewares compare the UNstripped path: `/v/api/v1/verify/image` is not in
`_UPLOAD_PATHS` and does not start with `/api/v1/verify/`. Result: another
site's page can again submit paid checks, and every real screenshot or voice
note over 64 KiB is refused as "That message is too long". Any sub-path
deployment (a reverse proxy at /verifier) would hit this on day one.

**Reproduction.** `scratchpad/review/r07_cross_site.py`, real uvicorn with
`root_path="/v"`: `cross-site page -> /api/v1/verify/image  202  PAID` and
`our page, a 300 KB screenshot  413  {"detail":"That message is too long..."}`.

**Suggested fix.** In both middlewares use
`starlette._utils.get_route_path(scope)` (or strip `scope.get("root_path")`
yourself) before comparing, and add the root_path case to the tests.

### R5. A DNS-rebinding page passes RefuseCrossSite: "same-origin" to its own name is trusted without looking at the Host
*nice-to-have · 1080d2d · `app/main.py:113-136` (`_cross_site`) · still true at 55d3de0 and at 0951150*

**Scenario.** A page the owner visits re-resolves its own name to 127.0.0.1
and POSTs to `http://evil.example:8000/api/v1/verify/...`. The browser calls
that same-origin (`Sec-Fetch-Site: same-origin`, or `Origin` equal to the
`Host` it sent, `evil.example:8000`), so `_cross_site` waves it through and
the paid check runs - and, being same-origin, the page can read the answer.
The dashboard already defeats exactly this with its Host check
(app/api/local.py); the paid routes do not check Host at all. Bounded by the
daily cap, needs the owner's own browser on the server's machine, and
Chrome's Local Network Access largely blocks rebinding to loopback - hence
nice-to-have.

**Reproduction.** `scratchpad/review/r07_cross_site.py` (raw sockets to
real uvicorn from 127.0.0.1): `DNS-rebinding page (same-origin to its own
name)  202  PAID`; `DNS-rebinding page, old browser (Origin only)  202  PAID`.

**Suggested fix.** Refuse a paid POST whose Host is not one of this app's
names (the local names `is_this_machine` accepts, plus the public hostname
from settings) - a Host allowlist, as `TrustedHostMiddleware` would do.

### R6. A finished check still counts as "running" for a moment: a client that waits for COMPLETE and then submits is told to wait for its answer
*nice-to-have · 020e26f · `app/api/routes.py:142-158` (`_check` releases after `_settle_quota`) · still true at 55d3de0 and at 0951150*

**Scenario.** run_check saves the COMPLETE answer (pollers see it at once),
then writes the ledger, emits "done", returns; `_check` then runs
`_settle_quota` (a thread hop, and a pool hop on a cache hit) and only then
releases the person. A client that follows the REST contract - poll
/reports until COMPLETE, then submit the next one - lands in that gap and
gets 429 "You already have a check running. Wait for its answer, then send
the next one." about every other time with the fake engine. A human on the
page or the bot is rarely that fast (the bot polls every 3 s), but under the
thread-pool starvation the ops audit measured (OPS-09) the gap grows to
seconds, and an automated client (the WhatsApp webhook to come) will hit it.

**Reproduction.** `scratchpad/review/r08_browser_own_page.py` (real headless
Chrome, the app's own origin, real limiter, fake engine; each submission
only after the previous one polled COMPLETE). At 020e26f, from
http://127.0.0.1 and from http://localhost alike:
`text -> 202 COMPLETE`, `link -> 429 You already have a check running...`,
`image -> 202 COMPLETE`, `media -> 429 You already have a check running...`.
At 55d3de0 the same race hit a different pair.

**Suggested fix.** Release when the answer becomes visible, not after the
bookkeeping: call `release(subject)` right after `run_check` returns (before
`_settle_quota`, which needs no guard), or have run_check release before its
final save. Keep the `finally` as the backstop.

### R7. The test that ties the body cap to the message limit uses the wrong arithmetic (x6 a character; an emoji is x12)
*nice-to-have (no failure at today's settings) · 50dcf3b · `tests/test_spend_bounds.py` `test_the_small_cap_always_fits_a_maximum_length_message` · unchanged at 0951150*

**Scenario.** `len()` counts code points, and a \u-escaping client (Python's
`json.dumps` default) writes an astral character as a surrogate PAIR,
`\ud83d\ude00` - 12 bytes. Today the worst case, 5,000 emoji plus a
40-emoji language, is 60,508 B and fits 64 KiB. But the guard asserts
`max_json_bytes >= max_input_chars * 6 + 1024`, so the day someone raises
`max_input_chars` (to 10,000, say) the test still passes while a 6,000-emoji
message - inside the limit - is refused by the middleware as "too long".

**Reproduction.** `scratchpad/review/r09_body_cap.py`: `emoji, max length,
\u-escaped (surrogates)  60508 B -> 422 (route)` (reaches the route today);
then `with max_input_chars=10000 the guard test says fits=True; a
6,000-emoji message (72012 B) -> 413 (middleware 413) That message is too
long.`

**Suggested fix.** Assert `max_json_bytes >= max_input_chars * 12 + 40 * 12
+ 1024`, or derive `max_json_bytes` from `max_input_chars` in config so they
cannot drift.

### R8. One printed key remains: `scripts/factcheck_probe.py` prints the Google API key on any HTTP error
*nice-to-have (an operator console, not the server or the bot; not one of the seven commits, but the question was "any remaining path") · `scripts/factcheck_probe.py:47` (`resp.raise_for_status()`, uncaught)*

**Scenario.** The probe (CLAUDE.md's free list) puts the key in the query
string, exactly as the provider does, but lets `raise_for_status()` escape:
any 400/403/429/5xx from Google - a revoked key, a quota day - ends in a
traceback whose last line is the full request URL, `...&key=<the key>`. The
app's provider avoids this on purpose (it logs type and status only), and
63f8049 fixed the same class for the bot token; this script was missed.

**Reproduction.** `scratchpad/review/r10_key_prints.py` (MockTransport 403,
dummy key): `httpx.HTTPStatusError: Client error '403 Forbidden' for url
'https://factchecktools.googleapis.com/v1alpha1/claims:search?query=5G+spreads+coronavirus&key=inval...'`,
`key shown : True`; the provider on the same 403 prints
`[factcheck] lookup failed: HTTP 403`, `key shown : False`.

A second, debug-only path to the same key: with `ANTHROPIC_LOG=info` (the
SDK's documented debug switch) the SDK configures root logging at import and
raises httpx's logger to INFO, and httpx then logs every request URL - so the
APP logs the Google key on every fact-check lookup, success included.
`scratchpad/review/r10b_anthropic_log.py`: `logged line : [... httpx:1740 -
INFO] HTTP Request: GET https://factchecktools.googleapis.com/v1alpha1/claims:search...`,
`key in log : True`. (The bot does not import anthropic - r11_bot_imports.py
- so its token URLs are not exposed this way.)

**Suggested fix.** Send the key as the `X-Goog-Api-Key` header (Google APIs
accept it) in both the probe and the provider, so no URL ever carries it -
that closes both paths; and catch `httpx.HTTPStatusError` in the probe,
printing only the status and Google's message.

### R9. One in flight per IPv4 ADDRESS is one in flight per carrier-NAT pool or office: unrelated people are told "you already have a check running"
*should-fix · 020e26f · `app/api/limits.py:79-91` (`_ip_subject`) with `max_in_flight_per_person = 1` · still true at 55d3de0 and at 0951150*

**Scenario.** A web visitor's "person" is their IPv4 address. Under carrier
NAT (most Indian mobile IPv4, Vi especially) and on any office or college
Wi-Fi, many people share one public address. While one of them has a check
running (1-3 minutes), every other person behind that address is refused
with "You already have a check running. Wait for its answer..." - a message
that is false for them and gives them nothing to do. 55d3de0 already reasons
this way for the daily allowance ("an IPv4 address is shared by many under
carrier NAT, so only a loose brake (20)"), but the in-flight limit is still 1
for an IPv4 subject.

**Reproduction.** `scratchpad/review/r12_subject_shapes.py` part G:
`person A: granted   person B, same address, meanwhile: 429 You already have a check running.`

**Suggested fix.** Make the in-flight limit per subject kind, like
`person_daily_limits`: 1 for tg/tgchat/wa/dev/ip6, a few (e.g. 3) for `ip`.

### R10. The bot's right to name a person rests on "this request looks local" - it fails open behind a header-less local proxy, and fails silently if the bot ever moves
*nice-to-have (neither shape is today's) · 020e26f · `app/api/local.py` `is_this_machine`, used by `limits.subject_of` · still true at 55d3de0 and at 0951150*

**Scenario.** (a) Behind a local reverse proxy in nginx's default shape
(Host rewritten to 127.0.0.1:8000, no X-Forwarded-For - the audit's F10
shape), every visitor is "this machine", so any visitor can send
`X-Verifier-Subject: tg:<anything>` and get a fresh bucket per request,
escaping the hourly limit, the in-flight limit and (at 55d3de0) the per-person
daily allowance. (b) If the bot runs anywhere but beside the app (another
container, a cloud host - shape C), the header is ignored without a word and
every Telegram user becomes the bot's address: one check at a time for all
of Telegram, refused as "you already have a check running".

**Reproduction.** `scratchpad/review/r12_subject_shapes.py`: E1 `20
submissions (hourly limit 10): 20 granted`; E2 `subjects: ip:10.0.0.5 /
ip:10.0.0.5`, `user 111: granted   user 222 (while 111 runs): 429 You
already have a check running.`

**Suggested fix.** Authenticate the bot, do not infer it: a secret in .env
sent as a header (compared with `hmac.compare_digest`), honoured from
anywhere; and have the 202 echo the subject it counted, so the bot can log
loudly when its naming was not honoured.

### R11. A check that outlives the TTL makes the next one uncounted: its late release pops the NEXT check's entry
*nice-to-have (needs a check longer than in_flight_ttl_s = 900 s) · 020e26f · `app/api/limits.py:280-291` (`release` pops by position, not by identity) · still true at 55d3de0 and at 0951150*

**Scenario.** Check 1 hangs past 900 s, so the TTL prunes it and check 2 is
granted. When check 1 finally ends, `release()` pops the first stamp in the
list - check 2's - so the person is recorded as idle while check 2 runs, and
check 3 is granted: two checks at once, the thing the rule forbids. OPS-17
notes no wall-clock bound on a check (the SDK allows 600 s x 3 attempts).

**Reproduction.** `scratchpad/review/r12_subject_shapes.py` part F (the
`_now` seam): `t=0 first check: granted`, `t=901 second check: granted`,
`t=902 first ends -> third check: granted while the second still runs`,
`in flight now: {'ip:198.51.100.20': [1902.0]}` - one entry for two
running checks.

**Suggested fix.** Give each claim a token (its start stamp or a uuid)
returned by `reserve` and carried in `_Spend`; `release(subject, token)`
removes exactly that one and ignores a token already pruned.

### R12. After a bot restart, the new "already running" refusal promises an answer the bot has forgotten
*nice-to-have (a consequence of OPS-07, which stays the root fix) · 020e26f · `app/api/limits.py` `_BUSY`, shown verbatim by `scripts/telegram_bot.py` · still true at 55d3de0 and at 0951150*

**Scenario.** The bot keeps its undelivered job ids in memory (OPS-07). If
it restarts while a person's check runs, the person's next message is
submitted, refused by the new one-in-flight rule, and the bot relays
"Checking..." followed by "You already have a check running. Wait for its
answer, then send the next one." - in English, and about an answer that
will never arrive, because the restarted bot does not know the job id. The
person waits, then has to guess when to resend.

**Reproduction.** `scratchpad/review/r13_bot_restart_busy.py` (real uvicorn,
real AppClient + handle_message, the first check held open):
`[bot#1] bot says: 🔎 Checking…`, then after the "restart"
`[bot#2] bot says: 🔎 Checking…` and
`[bot#2] bot says: 😕 You already have a check running. Wait for its answer, then send the next one.`
- the first answer then completes and is delivered to nobody.

**Suggested fix.** Persist the bot's pending job ids (OPS-07). Cheaper and
complementary: for a BOT-named subject only (never an IP subject, where it
would hand one NAT neighbour another's message), return the running job's
id with the 429, so the bot can resume and deliver it instead of refusing.

### R13. Every anonymous group admin, and everyone posting "as a channel", is ONE Telegram person
*nice-to-have (groups and channels are a side use of the bot) · 020e26f · `scripts/telegram_bot.py` `subject_of_message` · still true at 55d3de0 and at 0951150*

**Scenario.** `subject_of_message` keys on `from.id`. Telegram fills `from`
with a shared placeholder for anonymous group admins (GroupAnonymousBot,
1087968824) and for messages sent on behalf of a channel (Channel_Bot,
136817688), and puts the real sender in `sender_chat`. So every anonymous
admin in every group shares one subject - one check in flight, one hourly
bucket and, at 55d3de0, one 5-a-day allowance - and one of them can use it
up for all the others; the same for every "post as channel" sender. The
other way round, each channel the bot is added to is a fresh subject, so a
person with several channels has several allowances.

**Reproduction.** `scratchpad/review/r14_tg_subjects.py`: `group A,
anonymous admin -> tg:1087968824`, `group B, a different anonymous admin ->
tg:1087968824`, `group C, someone posting as channel X -> tg:136817688`,
`group D, someone else posting as channel Y -> tg:136817688`.

**Suggested fix.** Prefer `sender_chat.id` when present
(`tgchat:<sender_chat.id>`), else `from.id`; consider counting channels per
owning user if allowances matter there.

### R14. (HEAD 0951150, outside the seven) "Repeats stay free" has no limit at all: one visitor can create job rows and in-memory streams without bound
*should-fix · 0951150 · `app/api/routes.py` `verify_text` (the cache-hit branch before `_quota`)*

**Scenario.** To keep repeats free, a cached text is now served before any
claim - so before the hourly limit, the in-flight rule and every other
per-person bound. Each repeat still writes a job row (kept 30 days) and
registers a JobStream (kept in memory 15 minutes after it finishes). The
audit's F4 counted on the hourly limit to bound the stream registry; for
cache hits nothing bounds it now. Any claim that was checked once (the
attacker's own, or any viral one) is enough.

**Reproduction.** `scratchpad/review/r18_cache_hit_flood.py`
(REVIEW_SNAP=0951150, TestClient, one visitor): `600 repeats from ONE
visitor in 43.7 s: 202 x600 (hourly limit is 10)`, `job rows: 601   streams
held in memory (kept 900 s after finishing): 601`.

**Suggested fix.** Keep repeats free of MONEY but not of limits: count a
cache hit against the per-person hourly limit (it is an abuse guard, not a
spend guard), or answer a repeat from the same person within the stream TTL
with the job id they already have instead of a new job.

### R15. release() - and at HEAD admit() - take the limiter's lock ON THE EVENT LOOP, while claims hold that lock across SQLite writes: a contended write now freezes the whole server
*should-fix · 020e26f (`release`), widened by 5f8e7db (`admit`, "safe to call on the event loop") · `app/api/limits.py` `release()` / `admit()` vs `reserve()` (`with _lock:` around `_daily.take`, and at HEAD `_budget.reserve`) · true at 020e26f and at 2f4d825*

**Scenario.** Claims run on the limiter's pool precisely because "on the
event loop, a claim waiting for another writer's lock froze every request
and every live stream" (measured earlier; limits.py says so). But the claim
holds `limits._lock` across its SQLite statements, which wait up to the
30 s busy timeout when another writer has the database (housekeeping's
DELETE, a burst of saves - R14's free flood makes those on demand). 020e26f
added `release()`, which takes the same lock and is called ON THE LOOP by
every route refusal and every finished background check; 5f8e7db added
`admit()`, also on the loop, for every link and media submission. Either
then blocks the event loop until the contended claim finishes: every page,
stream, poll and the bot stop.

**Reproduction.** `scratchpad/review/r20_loop_lock.py` (real uvicorn; a second
connection holds the scratch DB's write lock for 8 s; visitor A's text claim
waits in the pool holding `_lock`; /health timed right after the trigger):

```
=== 020e26f   trigger=none     GET /health took  0.00 s
              trigger=release  GET /health took  6.97 s   (B's check ends -> release() on the loop)
=== 2f4d825   trigger=none     GET /health took  0.00 s
              trigger=release  GET /health took  6.97 s
              trigger=admit    GET /health took  7.00 s   (C submits a link -> admit() on the loop)
```

**Suggested fix.** Never hold `_lock` across I/O: do the in-memory
bookkeeping (hour, in flight, person) under `_lock`, and the database's own
conditional statements - already atomic - outside it, undoing the in-memory
part if the database refuses; or run `release()`/`admit()` on the pool too.
A test: hold the DB's write lock in another connection, start a claim, call
`release()` from the loop, assert the loop answers in well under a second.

## The fixes made for R1-R3 while this review ran (5f8e7db, 2f4d825), re-checked

- R1 fix (5f8e7db, two-phase admit/fund) holds for free work: five subjects'
  links whose free resolve takes 4 s and is then refused hold nothing -
  `during the resolves used_today=0 committed=$0.00 mode=full in_flight=5`,
  an unrelated visitor's text `-> (202, ...)`, the five get their 422, and
  afterwards `in_flight=0` (`scratchpad/review/r05c_lockout_fixcheck.py`,
  REVIEW_SNAP=2f4d825). When the resolves SUCCEED, funding happens at the paid
  step: 3 x 202, then "The service is busy right now - please try again in a
  few minutes" and the budget's "nearly used up" - the honest messages. But
  `admit()` runs on the event loop and takes `_lock`: see R15 (measured
  7.00 s freeze at 2f4d825).
- R2 fix (2f4d825): `https://www.facebook.com:1/share/...` -> `LinkError[unsupported]`,
  route `HTTP 422`, no connection (`r19_before_after_ca76538.py`).
- R3 fix (2f4d825): the share link + newline -> route `HTTP 422`; the bot now
  files that message as TEXT (its pinned rule; PROJECT_PLAN 11.24 records the
  product question); every unparseable hop Location is a LinkError, none
  uncaught, none requested (`r04_share_edges.py`, `r04b_share_newline_bot.py`).
  In this scratch run the bot's text check then failed only because the
  engine had dummy keys and no network.

## The fixes for R6-R15, re-checked (2026-10-16)

Run by the main session with the reviewer's own scripts and isolation
(`_rboot.py`): `REVIEW_SNAP=wt` is a copy of the working tree at each fix,
and `snap-2d3b5c8` the code before R15's fix.

- R15 (3bd7772), `r20_loop_lock.py`: /health while another connection holds
  the write lock for 8 s - at 2d3b5c8 `control 0.02 s`, `a check ends 7.02 s`,
  `a link arrives 7.02 s`; at 3bd7772 `0.02 / 0.00 / 0.02 s`.
- R14 (2d3b5c8), `r18_cache_hit_flood.py`: `600 repeats from ONE visitor in
  7.6 s: 202 x9, 429 x591 (hourly limit is 10)`, `job rows: 10   streams held
  in memory: 10` (were 601 and 601).
- R13 (2d3b5c8), `r14_tg_subjects.py`: each anonymous admin and each "post as
  channel" sender is its own `tgchat:<sender_chat.id>` (were all
  `tg:1087968824` / `tg:136817688`).
- R9 (2d3b5c8), `r12_subject_shapes.py` part G: `person A: granted   person
  B, same address, meanwhile: granted`.
- R11 (05418fa): r12's part F cannot show it any more - it calls
  `release(subject)` with no token, and its IPv4 visitor may run 3 at once
  since R9. `r12b_ttl_release_token.py` (an IPv6 visitor, one in flight,
  each claim's own token): the third check is refused while the second
  runs. **But the same scenario in the old call shape - no token - still
  granted the third**: the no-token release freed the OLDEST entry, R11
  surviving its own fix. Fixed in 2147412 (the token is required; a None
  token frees nothing); both shapes now refuse.
- R1 still holds after R15 restructured the claim (`r05c_lockout_fixcheck.py`):
  `during the resolves used_today=0 committed=$0.00 mode=full in_flight=5`,
  the unrelated visitor 202, afterwards `in_flight=0`.
- Release on every route exit: `r01b`'s counting stub takes ONE argument, so
  every row raised inside the stub itself (`TypeError: counting_release()
  takes 1 positional argument but 2 were given`) and read BAD - a harness
  that no longer tests anything. `r01c_release_paths_token.py` (the stub
  takes the token): nothing stuck on any of the 29 paths. Success paths call
  release() 2-3 times - the engine's early release (R6), then `_finish`'s
  backstop - and a repeat of the same token does nothing (pinned in
  tests/test_per_person.py).
- Cancellation: `r02` was written for 020e26f, when a link claimed BEFORE it
  resolved. At HEAD its C2 stub (a slow `reserve`) is never called - the
  link route admits, resolves, then funds - and C3 waits for a refund that
  a resolve-stage failure no longer makes. `r02b_cancel_paths_token.py` C1:
  `releases=1 used_today=1 in_flight={}  next check: granted`. The
  fund-stage cancellation the harness can no longer reach is now a test
  (f4f00b1), shown failing against two mutants.

Found while re-checking, each reproduced and fixed test-first:
- 4f6be5c - R15's rule broken a second way: a cancelled claim's rollback
  ran ON the event loop (`MainThread`) when the claim had already finished
  in the pool at the instant its caller was cancelled, because
  `add_done_callback` then runs the callback inline.
- 56c3990 - the C3 edge under "Checked and found sound": `release()` now
  sits in a `finally`.
- dc3ebd4 - the test suite itself ran with the five real keys from .env
  loaded; 8 link and voice tests passed only because a real Sarvam key was
  there. Dummy keys are now set before the app is imported; 982 pass on a
  copy with no .env.

## Checked and found sound

- 020e26f, release on every route exit (r01_release_paths.py, 28 paths): text/image/media/link success, every 4xx/5xx refusal, a failed `_new_job`, OCR raising, and a background job raising in run_check, `_settle_quota`, ASR, `_check`, `fail_job` or gather - each released exactly once, `_in_flight` empty after. Over-length and small-talk refusals claim nothing and release nothing. Re-run at 55d3de0 (its `owns_release` change): all 28 still exactly once; r02 identical. Re-run at 0951150 (`_finish` replaced `_check`/`_settle_quota`; r01b_release_paths_head.py, 29 paths incl. the new claim-free cache-hit branch and a `settle` that raises): all exactly once.
- 020e26f, cancellation (r02_cancel_paths.py): a route cancelled during the link resolve releases once and refunds; a claim cancelled while still in the pool is refunded and released once by `_rollback`. One edge, moot in practice: a SECOND cancellation landing on `_quota`'s shielded refund skips `release()` (`C3 ... releases=0 ... next check: 429 You already have a check running`), because the release follows the shielded await instead of sitting in a `finally`. Neither uvicorn nor Starlette cancels a plain JSON handler on disconnect, so only shutdown (asyncio.run's final cancel-all) can do this, and the in-memory table dies with the process. Moving `release` into a `finally` would make it unconditional. (Done 2026-10-16, 56c3990, reproduced first.)
- 020e26f, one subject cannot hold two checks: five concurrent links from one /64 -> 1 runs, 4 x 429 "already running" (r05 part 1).
- ca76538, the SSRF fence on hops (r04_share_edges.py part A, 19 Locations): protocol-relative, off-allowlist, http downgrade, 127.0.0.1, [::1], userinfo `@`, backslash-userinfo, homoglyph and punycode hosts, javascript:/data: - none was ever requested; uppercase host and relative paths resolve correctly; /login and /login.php land as "gated"; the hop count is bounded at 3.
- 1080d2d, header handling on real uvicorn (r07_cross_site.py, raw sockets): our page with Sec-Fetch-Site same-origin -> 202; our page with Origin only -> 202; no Origin and no Sec-Fetch-Site (bot/curl) -> 202; cross-site, UPPER-CASE header names, an unknown Sec-Fetch-Site value, `Origin: null`, Origin without a Host header, same host on another port -> 403 with nothing paid; IPv6 `[::1]:8000` Host/Origin match -> 202; `//api/v1/verify/image` cross-site -> 405 (not routed, nothing paid). Duplicate Origin (ours first) passes, but no browser can send two.
- e4a9822 (r10_key_prints.py part C): repr, str, model_dump and model_dump_json of Settings show no key. `dict(settings)` and `vars(settings)` do (plain str, by design) - nothing in app/ or scripts/ calls either; no code clones Settings through a dump, so `exclude=True` drops no key anywhere it is needed.
- 63f8049, the rest of the bot and app print paths: every remaining `{exc}` print in app/ and the bot is for a call whose URL carries no secret (the app on 127.0.0.1, Sarvam and Anthropic keys travel in headers); Telegram paths print the type name or Telegram's own response body; the factcheck provider prints type and status only (r10 part B). The bot process configures no logging and does not import anthropic (r11_bot_imports.py), so httpx's INFO request lines, which would carry the token URL, are dropped there (the app process is another matter - R8).
- 9a737bd: `_TG_DOWNLOAD_LIMIT = 20 * 1024 * 1024` with `>` matches the Bot API's 20 MiB getFile rule; a too_big message takes no lock-held download, no "Checking...", no slot; photos cannot exceed it; documents are "unsupported" as before. (Left as the commit says: a big file whose `file_size` Telegram omitted still ends in "try again later"; mapping getFile's "file is too big" description to `_TOO_BIG_REPLY` would close that too.)
- 50dcf3b never refuses a legitimate request at today's settings (r09_body_cap.py): a max-length Hindi message \u-escaped (25,154 B) or raw UTF-8 (13,082 B), a max-length every-character-escaped ASCII one (30,011 B) and the worst case, 5,000 emoji + a 40-emoji language as surrogate pairs (60,508 B), all reach the route. The page's own requests are raw UTF-8 and small; the bot's text is <= 4,096 UTF-16 units; link URLs are <= 2,048. Uploads keep 25 MB by path (r08: image and media through the real page).
- 50dcf3b's streaming half on real uvicorn (r16_chunked_json.py): a CHUNKED 100 KB JSON body (no Content-Length) -> 413 "That message is too long", not a 500; a 300 KB image upload -> 202.
- 50dcf3b, the triage that still runs before any limit (r15_triage_cost.py): on max-length adversarial input (one repeated letter, alternation, Devanagari + virama, emoji, ZWJ runs, punctuation, digits) it takes 0.8-1.4 ms a call - the freeze is gone.
- 1080d2d does not break the app's own page in a real browser (r08_browser_own_page.py, headless Chrome, throwaway profile): JSON text and link, FormData image and media with a language field, from http://127.0.0.1 and http://localhost - every request reached the API (202 or the limiter's own 429; never 403).
- 1080d2d does not break the bot: no Origin and no Sec-Fetch-Site passes (r07); its AppClient sends neither.
- 1080d2d, coverage: every POST that can spend is under `/api/v1/verify/` (text, image, media, link); the dashboard routes are GET-only; FastAPI does no method override; Starlette routes by `scope["path"]`, the same field the middleware reads (but see the root_path note if one is ever set).
