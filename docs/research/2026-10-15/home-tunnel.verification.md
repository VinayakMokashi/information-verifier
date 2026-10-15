# Verification: Keeping it on the home Windows PC behind a tunnel

status: complete (2026-10-15; 25 web calls, $0 spent)

Verdict index (details below, in the order they were reached):
- Decision-critical: F1 confirmed (dollar figures derived, not quoted by Cloudflare) ·
  F3 confirmed (125 s / 30 s / 100 MB; edge buffering of SSE still unknown) · F5 confirmed ·
  F6 confirmed (two small code corrections) · F7 confirmed · F8 corrected (the restart facts
  hold; "unlimited pause is Insider-only" is probably out of date and stays uncertain).
- Others: F9 confirmed · F10 confirmed as stated · F12 corrected (both fences already exist in
  code) · F2, F4, F11 not re-checked.
- New: NEW-1 (cloudflared flushes text/event-stream, from its source code) · NEW-2 (Cloudflare
  requires 3DS on every Indian-bank transaction and does not list RuPay or UPI, which puts the
  "buy at Cloudflare Registrar" step and its auto-renewal at risk).
- Biggest omission: home hosting's residential IP, which keeps the reel/Shorts feature working
  (see ytdlp-cloud-ips.md).

Verifier: adversarial verification agent, started 2026-10-15. Target: `home-tunnel.md` (same folder).
Method: each decision-critical finding (and every price / limit / timeout / plan claim a
recommendation rests on) is attacked with fresh PRIMARY sources (developers.cloudflare.com,
cloudflare.com, tailscale.com/kb, ngrok.com, registry.in, learn.microsoft.com, support.microsoft.com).
Verdicts: confirmed / corrected / refuted / uncertain. Uncertain is preferred over confirming on
secondary reports. Each verdict is appended the moment it is reached, so a killed run keeps
everything up to that point. No money spent; no paid check run; no git.

## Verdicts

### F12 (security exposure behind the tunnel) - CORRECTED (checked in the repo, $0, 2026-10-15)

Claim: through cloudflared every request arrives from 127.0.0.1, so /dashboard and the per-IP
limiter would treat the whole internet as local unless fenced; the limiter "must key on
CF-Connecting-IP".

Corrected statement: both risks are already handled by the code as it stands, provided uvicorn
keeps its default proxy handling.
- (a) /dashboard is NOT exposed by a tunnel. `_local_only()` (app/api/dashboard.py lines 48-59)
  returns 404 for any request that carries X-Forwarded-For, Forwarded, X-Real-IP,
  CF-Connecting-IP, True-Client-IP or X-Forwarded-Host, or whose single Host header is not
  127.0.0.1 / localhost / [::1]. The module docstring (lines 10-16) says this was built for
  share_demo.ps1's tunnel. A WAF rule is therefore defence in depth, not a requirement. If one is
  added, it must also cover `/api/v1/admin/spend` (the JSON the dashboard reads, same file line
  73), which the researcher's "block /dashboard" bullet misses. A free alternative that spends no
  WAF rule: a cloudflared ingress rule with `path:` matching `^/(dashboard|api/v1/admin/)` and
  `service: http_status:404`.
- (b) The limiter already sees the visitor's IP. Installed uvicorn is 0.51.0; its Config defaults
  are `proxy_headers=True` and `forwarded_allow_ips = env FORWARDED_ALLOW_IPS or "127.0.0.1"`
  (.venv/Lib/site-packages/uvicorn/config.py lines 219, 354-356, 525-526), and
  ProxyHeadersMiddleware takes the right-most untrusted X-Forwarded-For entry
  (middleware/proxy_headers.py lines 169-187). start.ps1 line 60 runs `python -m uvicorn
  app.main:app` with no flags, so the defaults apply, and `_client_of()` (app/api/limits.py line
  119) reads `request.client.host`, which uvicorn has already rewritten. "Make the limiter read
  CF-Connecting-IP" is redundant; the real rule is "do not launch uvicorn with
  --no-proxy-headers or a widened --forwarded-allow-ips". Caveat (not tested here): this relies
  on Cloudflare appending the connecting IP as the right-most X-Forwarded-For entry, as its
  request-header docs describe. A free end-to-end check through a quick tunnel (send a spoofed
  X-Forwarded-For and log request.client) would settle it.
- (c) yt-dlp/ffmpeg parsing attacker-chosen media on a personal PC that also holds .env:
  agreed, and it is the strongest residual home-hosting risk in this finding. Not tested.
- Also confirmed in code: the Telegram bot calls the app at `http://127.0.0.1:8000/api/v1`
  (scripts/telegram_bot.py line 34), and SSE heartbeats are 15 s (app/api/stream.py line 29,
  ": ping" at line 181).

Evidence: repo files above, read 2026-10-15.

### F3 (proxy read timeout 125 s, write 30 s, 100 MB body) - CONFIRMED (timeout part); body limit and buffering in the addendum below

Claim: on non-Enterprise plans the proxy read timeout is 125 s (was 100 s), not configurable;
write timeout 30 s; idle 900 s; client keep-alive 400 s.
Evidence: Cloudflare "Connection limits" (developers.cloudflare.com/fundamentals/reference/connection-limits/,
"Last updated Jul 23, 2026"), fetched 2026-10-15: "Proxy Read Timeout | 125 | 524 | Yes, for
Enterprise zones"; "Proxy Write Timeout | 30 | 524 | No"; "Proxy Idle Timeout | 900 | 520 | No";
"Connection Keep-Alive HTTP/1.1 | 400 | TCP connection closed | No". All as the researcher said.
The page does NOT say what the read timeout measures (time to first byte vs. silence between
reads), so "the timer counts silence" stays a third-party claim, as the researcher already
flagged. It does not affect the decision: the app's SSE sends ": ping" every 15 s
(app/api/stream.py line 29), far inside either reading, and submits return a job_id at once.

### F5 (Bot Fight Mode cannot be skipped; may challenge API/mobile traffic; keep it OFF) - CONFIRMED

Evidence: Cloudflare "Bot Fight Mode" (developers.cloudflare.com/bots/get-started/bot-fight-mode/,
"Last updated Aug 3, 2026"), fetched 2026-10-15: "they may challenge API or mobile app traffic";
"You cannot bypass or skip Bot Fight Mode using WAF custom rules or Page Rules"; it "will not
trigger if an IP Access rule matches the request first"; "Protect entire domains without endpoint
restrictions"; JavaScript Detections "is automatically enabled and cannot be disabled" for Bot
Fight Mode customers. Small precision: the page says "WAF custom rules or Page Rules" (it does
not separately name Bypass/Allow actions or Configuration Rules), and Super Bot Fight Mode (Pro
and up) does support Skip rules. The page does not state the default state, so the owner should
CHECK it is off after adding the zone rather than assume it. Keeping it off for a Meta webhook is
sound advice.

### F6 (quick tunnels: no SSE, 200 in-flight, no uptime guarantee, new hostname each time) - CONFIRMED (Cloudflare part); code part CONFIRMED with two small corrections

Evidence: Cloudflare "Quick Tunnels" (developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/,
"Last updated Sep 30, 2026"), fetched 2026-10-15: "Quick Tunnels do not support Server-Sent
Events (SSE)."; "Each Quick Tunnel supports up to 200 in-flight requests. Additional requests
return a 429 response."; "Quick Tunnels have no uptime guarantee."; "The hostname changes each
time you create a Quick Tunnel."; "Quick Tunnels are for testing and development."; "You do not
need a Cloudflare account or domain."
Code check (static/index.html, read 2026-10-15): the fallback is real - follow() closes the
EventSource on error (line 521) or after a deadline (line 504) and track() then always calls
poll(). Corrections: (1) the constants are at line 263, `POLL_MS = 2500, POLL_MAX = 96`, i.e. a
240 s poll budget; (2) giving up is not a loss - the job id stays in the URL hash and the
give-up text tells the user to refresh, which resumes the SAME job (lines 474-482). Also note
the "300 s" in the finding is `max_media_seconds = 300` (app/config.py line 71), a cap on the
MEDIA DURATION, not a processing-time bound; no job timeout was found in app/config.py or
app/engine/job.py, so "a check can take up to 300 s" is unsourced either way.
Note: the page does not say HOW SSE fails on a quick tunnel (error vs. buffered until the end);
both paths end in poll() here, so the page works either way.

### F1 (named tunnel needs a domain on Cloudflare; .com $10.46 -> ~$11.17 on 1 Nov 2026; no .in at Cloudflare) - CONFIRMED in substance; the exact dollar figures are derived, not quoted by Cloudflare

- Domain needed: CONFIRMED. Cloudflare "DNS records" for tunnels (developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/dns/,
  "Last updated Apr 17, 2026"): "The cfargotunnel.com subdomain only proxies traffic for DNS
  records in the same Cloudflare account." So a named tunnel's public hostname needs a zone in
  the owner's own Cloudflare account; the page offers no domain-free alternative. The only
  Cloudflare route documented as needing no domain is the quick tunnel ("You do not need a
  Cloudflare account or domain", trycloudflare page, 30 Sep 2026), which F6 rules out.
- .in / .co.in not at Cloudflare Registrar: CONFIRMED. cloudflare.com/tld-policies/ (fetched
  2026-10-15, no date on page) has no ".in" and no ".co.in" entry; it lists "com" (Verisign) and
  "xyz" (XYZ). (developers.cloudflare.com/registrar/top-level-domains/, updated May 15, 2026,
  only says "over 400" TLDs and defers to that list.)
- At-cost pricing: CONFIRMED in words. Cloudflare's .com page (cloudflare.com/application-services/products/registrar/buy-com-domains/):
  "Cloudflare passes the registry's exact price to you"; "You pay what we pay, with no markups
  or hidden fees added by Cloudflare." It shows NO dollar figure and does not mention the ICANN
  fee, so "$10.46 today" and "$11.17 after" remain derived (wholesale + $0.20 ICANN fee, the
  researcher's own arithmetic plus a third-party tracker). Treat them as "about $10.5 now, about
  $11.2 after 1 Nov"; the decision does not turn on cents.
- Verisign wholesale $10.26 -> $10.97 on 1 Nov 2026: CONFIRMED, with a sourcing caveat. A search
  restricted to verisign.com/icann.org (2026-10-15) surfaced Verisign's own "Verisign Reports
  First Quarter 2026 Results" (23 Apr 2026) as stating the .com fee rises from $10.26 to $10.97
  on 1 Nov 2026; registrar notices (Openprovider, Realtime Register, OSIR) agree. Both direct
  fetches of the Verisign release (investor.verisign.com static PDF and HTML release) returned
  HTTP 403, so the sentence itself was not read verbatim by this verifier.
- Missed nuance the recommendation could use: under the .com registry agreement (ICANN decision
  paper on Amendment 3, 2020, as summarised by the same search), registrars get >= 6 months'
  notice and a registrant may register or renew for up to 10 years at the CURRENT price before
  the increase. So "buy before 1 Nov" can lock the old price for several years, not just the
  first, IF Cloudflare's checkout offers multi-year terms (not verified here). Saving is about
  $0.71 a year, so this is a footnote, not a reason to rush.
- NIXI ".in wholesale Rs 500/yr, .co.in Rs 400/yr": NOT re-checked (budget kept for
  decision-critical items); the .in option is not the recommendation. Treat as unverified.

### F10 (Workers VPC + workers.dev as a domain-free route) - CONFIRMED as stated (the researcher's own "unconfirmed" caveats stand)

Evidence: Workers VPC overview (developers.cloudflare.com/workers-vpc/, "Last updated Oct 12,
2026"): "Workers VPC is currently in beta"; "While in beta, Workers VPC is available for free to
all Workers plans"; "VPC Services support HTTP and TCP". Get-started page (same date):
prerequisites are a Cloudflare account and "Install Node.js"; the tunnel is created in the
Workers VPC dashboard's Tunnels tab and cloudflared is installed with the dashboard's token; the
Worker itself is scaffolded with `npm create cloudflare@latest`, bound in wrangler.jsonc and
deployed with `npx wrangler deploy`. Neither page mentions a domain, a zone, workers.dev, body
size, streaming, SSE or timeouts. So "no domain needed" is plausible but undocumented, and the
documented path needs Node (not installed on this PC). Correctly labelled an experiment.

### F7 (ngrok Free / Hobbyist / Pay-as-you-go) - CONFIRMED (one detail unverified)

Evidence: ngrok.com/pricing (fetched 2026-10-15, current): Free "$0", "Up to 1GB data
transfer", "Up to 20k HTTP/S requests", "Up to 3 online endpoints", "Assigned dev domain for
public endpoints", "Interstitial page on HTTP/S endpoints", "$5 of one-time included usage".
Hobbyist "$10" monthly ("Save $24 with annual billing", i.e. about $8/mo), "ngrok-branded
domains", "No Interstitial page". Pay-as-you-go "$20 monthly + additional usage", "Bring your
own domain for public endpoints" at "$0.01 per active hour". ngrok free-plan-limits doc
(ngrok.com/docs/pricing-limits/free-plan-limits/, undated, fetched 2026-10-15): 1 GB/month,
20,000 requests/month, development domains: 1, "Free endpoints have no timeout"; the
interstitial is "in front of all HTML browser traffic on the free tier" and "does not impact
users serving APIs or accessing ngrok endpoints programmatically"; skipped by the
`ngrok-skip-browser-warning` header or a non-standard User-Agent; a 7-day cookie after "Visit".
Unverified: the "29 Jun 2026" start date of per-hour custom-domain pricing and "the $5 credit
cannot pay for data transfer" (the blog post was not read; the pricing page names no date).
Usage note the researcher missed: if SSE fails and the page falls back to polling, one check can
make up to 96 GETs of /reports (static/index.html line 263) - at the 5/day cap about 14,400 a
month in the worst case, inside 20k but not "tiny". Normal SSE operation is a handful of
requests per check.

### F8 (Windows Update restarts unattended; 18 h active hours; Home pause max ~5 weeks, unlimited pause Insider-only) - CORRECTED (the "Insider-only" part is probably out of date; the restart facts are confirmed)

- "Devices that don't have locally signed-in users, or active RDP sessions, are restarted":
  CONFIRMED verbatim. Microsoft Learn "Manage device restarts after updates"
  (learn.microsoft.com/en-us/windows/deployment/update/waas-restart, ms.date 2025-09-26,
  updated_at 2025-10-02), fetched 2026-10-15. Context matters: the sentence is a note on the
  "No auto-restart with logged on users" policy, i.e. that policy cannot protect a machine
  nobody is signed into - which is exactly the recommended run-without-login setup.
- Active hours max 18 h: CONFIRMED ("Later versions support max active hours length of 18
  hours"; default 8 AM-5 PM). NoAutoRebootWithLoggedOnUsers "doesn't work exactly as per
  description": CONFIRMED verbatim. The page does not say which editions honour these registry
  policies (Home is not mentioned), so that unknown stands.
- "Unlimited pause is Insider-only in 2026": CORRECTED to UNCERTAIN, leaning wrong. A fresh
  search (2026-10-15) found press reports (Windows Central, Digital Trends, ProPakistani 15 Jul
  2026) that the renewable 35-day pause (re-pause by hand, one block at a time) reached regular
  Windows 11 24H2/25H2 with the 14 Jul 2026 Patch Tuesday update KB5101650, as a gradual
  rollout. Microsoft's own KB5101650 page (support.microsoft.com/en-us/help/5101650: OS builds
  26200.8875 / 26100.8875, "all editions") does not mention the pause in the fetched text, so
  the GA claim is not confirmed by a primary source. Either way each pause is still capped at
  35 days, and Microsoft-side "no more forced restarts" is reported for Insiders only.
- Local facts read for free from this PC's registry (2026-10-15): Windows 11 Home Single
  Language (EditionID CoreSingleLanguage), 25H2, build 26200.9457 (newer than KB5101650's
  .8875); active hours are already set to 18:00-11:00 (17 h); and updates are PAUSED until
  2026-10-25T15:47:16Z. Two consequences the research did not state: (1) as configured, update
  restarts fall between 11:00 and 18:00, i.e. Indian daytime, when a public service is busiest -
  for hosting, set active hours to about 07:00-01:00 so restarts fall in 01:00-07:00 IST; (2)
  the pause ends on 25 Oct, after which pending updates install and restart. Also from
  KB5101650: "Windows 11, version 24H2 Home and Pro editions will reach end of updates on
  October 13, 2026" - this PC is on 25H2, so it is still supported, but a 24H2 machine would not
  be.
- The consequence the researcher drew (every process must start at boot without a login; a
  check in flight during a reboot is lost; its daily-cap slot stays used unless refunded) is
  sound and unchanged by the correction.

### F3 addendum (100 MB body limit; SSE buffering) - body limit CONFIRMED; buffering stays UNCERTAIN

- Body limit: CONFIRMED. Cloudflare "Error 413" (developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/,
  "Last updated Sep 28, 2026"): Max upload size Free "100 MB", Pro "100 MB", Business "200 MB",
  Enterprise "Up to 5 GB". The app's 25 MB cap (app/config.py line 70) fits on Free.
- Buffering: the URL developers.cloudflare.com/network/response-buffering/ ("Last updated Apr
  23, 2026") now shows only the general Network settings list - nothing on buffering, SSE or
  text/event-stream. No Cloudflare doc read here says whether the edge buffers SSE through a
  NAMED tunnel, so the researcher's unknown stands, and the recommendation's planned free test
  (serve_demo.py through the tunnel) is the right way to settle it.

### F9 (Tailscale Funnel: free, beta, *.ts.net only, ports 443/8443/10000, undisclosed bandwidth limits) - CONFIRMED (price detail not re-fetched)

Evidence: Tailscale KB "Tailscale Funnel" (tailscale.com/kb/1223/funnel, "Last validated Jan
20, 2026"), fetched 2026-10-15: "Tailscale Funnel is currently in beta."; "available for all
plans"; "Funnel can only listen on ports 443, 8443, and 10000."; "Funnel can only use DNS names
in your tailnet's domain." (no custom domain documented); "Traffic sent over a Funnel is subject
to non-configurable bandwidth limits." (no numbers); TLS terminates on the device; "Public DNS
records can take up to 10 minutes"; requires "Tailscale v1.38.3 or later", MagicDNS, HTTPS
certificates and "A funnel node attribute in your tailnet policy file". The KB says "all plans",
not "free"; "free" follows from the Personal plan being free, which was not re-fetched. The KB
says nothing about Windows or unattended running ("Funnel only works on platforms that can run
the Tailscale CLI"), so the option table's "Runs unattended as a Windows service" is unsourced.

### NEW-1 (resolves part of an Unknown): cloudflared itself flushes SSE immediately - primary source is cloudflared's code

cloudflared master, connection/connection.go (raw.githubusercontent.com/cloudflare/cloudflared/master/connection/connection.go,
fetched 2026-10-15): `shouldFlush(headers)` returns true when Content-Length is absent, when
Transfer-Encoding contains "chunked", or when Content-Type starts with one of
`flushableContentTypes = []string{sseContentType, grpcContentType, sseJsonContentType}`, where
`sseContentType = "text/event-stream"`. So the connector on the PC does not hold SSE back. What
the Cloudflare EDGE does with a named-tunnel SSE response is still not documented (see F3
addendum); the planned free serve_demo.py test through the tunnel remains the proof. This is the
master branch, not a pinned release.

### NEW-2 (resolves an Unknown, and it bears on the recommendation): paying Cloudflare from India

- Cloudflare Billing "Resolve a payment failure" (developers.cloudflare.com/billing/troubleshoot/troubleshoot-failed-payments/,
  "Last updated May 29, 2026"): "For customers of Indian banks, 3DS is mandatory for all
  transactions according to the Reserve Bank of India (RBI) mandate."; accepted methods are
  "credit and debit cards (Visa, Mastercard, American Express, Discover), PayPal", "Apple Pay,
  Google Pay, and Stripe Link" - RuPay and UPI are NOT listed; "If the failed payment was for a
  renewal, Cloudflare retries automatically five times over five days."
- Cloudflare Registrar FAQ (developers.cloudflare.com/registrar/faq/, "Last updated Aug 3,
  2026"): "sells domains at cost: you pay the registry and ICANN list price with no markup";
  "A domain cannot have more than 10 years on the term"; auto-renew is attempted about 30 days
  before expiry and "retries three more times before you must renew manually" (this disagrees
  with the billing page's "five times over five days"); a 40-day grace period for most TLDs;
  "all domains on Cloudflare Registrar use Cloudflare nameservers"; "Cloudflare Registrar only
  uses the primary payment method".
- Community threads (community.cloudflare.com, Billing/Registrar, roughly 2021 to mid-2025,
  SECONDARY): many reports of Indian credit/debit cards, and PayPal funded by them, being
  declined for Registrar purchases and especially renewals since RBI's Oct 2021 recurring-payment
  rules; outcomes vary by issuing bank.
- Reading: with 3DS mandatory on every Indian-bank transaction, an off-session auto-renewal is
  likely to fail, so plan on renewing by hand in the dashboard (completing the OTP) inside the
  30-day window, or renewing several years at once (term cap 10 years). Whether the FIRST
  purchase goes through depends on the owner's card (a Visa/Mastercard/Amex enabled for
  international e-commerce); this verifier did not and could not test it without paying.

### F2 (.IN KYC/e-KYC) - NOT RE-CHECKED (left as the researcher's own "medium, secondhand")

Budget went to decision-critical items; the .in route is not the recommendation. The NIXI
advisory was still not read by anyone, so treat the dates and the renewal scope as unverified.

### F4 (Cloudflare Free: 5 custom rules, 1 rate-limit rule 10 s/10 s, IP only; Turnstile free) - NOT RE-CHECKED

No recommendation turns on these exact numbers: the app's own SQLite daily cap and per-IP limiter
are the real guard either way (and F12 shows the limiter already keys on the visitor's IP). If a
rule is spent on the admin paths, note F12: it must cover `/api/v1/admin/spend` too, and a
cloudflared ingress rule can do the same job without using a WAF rule.

### F11 (24/7 on Windows: cloudflared service, Task Scheduler/WinSW, power, bandwidth) - NOT RE-CHECKED against the web; two local corrections

- Not re-fetched: Cloudflare's Windows-service page, NSSM/WinSW release status (the researcher
  marked these "from memory / not re-verified"), and the power figures (estimates, unsourced).
- From this PC (registry, 2026-10-15): it is Windows 11 Home Single Language 25H2. Active hours
  are already 18:00-11:00, which puts update restarts in Indian daytime - see F8.
- Unverified caution the finding omits: Task Scheduler's "Run whether user is logged on or not"
  stores the account's password; on a PC signed in with a Microsoft account or set to
  passwordless (Windows Hello only) this commonly fails or needs a password set. A dedicated
  LOCAL standard account (which F12(c) wants anyway, for yt-dlp/ffmpeg) avoids both problems.

## Recommendation check

Does "Cloudflare NAMED tunnel + a .com at Cloudflare Registrar" follow from the evidence?
Mostly yes on the tunnel, but the domain purchase and some setup bullets need correcting.

1. The tunnel choice follows from verified evidence. A named tunnel's hostname needs a zone in
   the owner's own Cloudflare account (F1). Quick tunnels have no SSE, no uptime guarantee and a
   new hostname each time (F6). ngrok Free shows an interstitial to every new browser visitor
   (F7). Funnel is beta with unpublished bandwidth limits (F9). Workers VPC is beta and needs
   Node (F10). Of these, only a named tunnel gives a stable URL on the owner's own domain, with
   a documented 100 MB body limit and a 125 s read timeout on Free (F3). cloudflared's own code
   flushes text/event-stream (NEW-1).
2. Buying the domain AT Cloudflare does not follow as firmly, for an Indian payer. Cloudflare's
   billing doc makes 3DS mandatory on every Indian-bank transaction, lists no RuPay and no UPI,
   and community threads report Indian cards declined, especially on renewals (NEW-2). Better
   wording: try Cloudflare Registrar with a Visa, Mastercard or Amex card enabled for
   international e-commerce. If it is declined, buy the .com at any registrar that takes Indian
   payment and point its nameservers at Cloudflare. The tunnel, SSE, limits and WAF are then
   identical; only the registrar's margin is added. Either way, expect to renew by hand (or
   renew several years at once; the cap is 10 years). If the domain lapses, the site and the
   WhatsApp webhook go down together.
3. Two setup bullets are already done in code (F12). /dashboard already returns 404 for anything
   carrying a proxy header or a non-local Host. The limiter already gets the visitor's IP
   through uvicorn's default proxy handling. Replace both bullets with: keep uvicorn's default
   proxy handling (never --no-proxy-headers, never a widened FORWARDED_ALLOW_IPS). Optionally,
   404 both `/dashboard` and `/api/v1/admin/` at the cloudflared ingress.
4. "Set active hours to 18 h" is right but leaves out the direction. This PC's current
   18:00-11:00 window puts restarts in Indian daytime. Use about 07:00-01:00 instead (F8).
5. The cost line "under Rs 100 a month in total" contradicts the researcher's own table. The
   domain is about Rs 75/month and electricity Rs 40-350/month by their own estimate, so the
   total is roughly Rs 115-425/month, plus an unverified card forex markup. That is still
   cheaper than any paid tunnel or VM, so the conclusion survives; the sentence does not.
6. "Buy before 1 Nov 2026" is a footnote, not a deadline. The confirmed wholesale rise is $0.71
   a year (F1), which should not hurry a hosting decision.
7. The options table claims "SSE works" for the named tunnel while the Unknowns call edge
   buffering unverified. NEW-1 settles the connector side only. Keep the planned free
   serve_demo.py test through the tunnel as the gate before calling it done.
8. The closing framing ("the deciding weakness is uptime, not cost") is fair but one-sided. It
   leaves out home hosting's deciding STRENGTH, the residential IP (Missed 1). That tilts the
   comparison against the cloud-VM branch.

## Missed

1. The residential IP. The sibling research (ytdlp-cloud-ips.md, F1 and F6, same folder) found
   that YouTube regularly blocks datacenter IPs at the metadata request the app depends on.
   Reels and Shorts still resolve from this home connection (re-measured 2026-10-15). Hosting
   at home keeps a core feature working for $0; a cloud host needs a residential proxy or home
   egress. home-tunnel.md never mentions this.
2. Paying from India (NEW-2), and the missing option ".com at another registrar + Cloudflare
   nameservers" (the options table only offers .com-at-Cloudflare or .in-at-an-Indian-registrar).
   Also the manual-renewal chore: a 40-day grace period, and Cloudflare's two pages disagree on
   how many times a failed renewal is retried.
3. The admin JSON endpoint `/api/v1/admin/spend` is missing from the proposed fence. A
   cloudflared ingress `path` rule can fence it without using one of the 5 WAF rules (F12).
4. This PC's actual state (read 2026-10-15): updates paused until 2026-10-25, and active hours
   18:00-11:00. KB5101650 says 24H2 Home and Pro reach end of updates on 13 Oct 2026; this PC is
   25H2, so it is fine, but any other machine considered for hosting must be checked.
5. Unverified, worth checking: running at boot without a login through Task Scheduler stores a
   password, which tends to break on Microsoft-account or passwordless sign-ins. A dedicated
   local standard account fixes that and also gives yt-dlp and ffmpeg the low-privilege account
   F12(c) asks for.
6. Not examined by anyone: Cloudflare edge features other than Bot Fight Mode that might
   challenge a Meta webhook (for example Browser Integrity Check or AI-bot blocking). After
   wiring the webhook, check the zone's Security Events for challenges on its path.
7. Not surveyed, unverified: other zero-domain tunnels (zrok, Pinggy, localhost.run) and free
   domain names that can be delegated to Cloudflare. They are low-trust for a fact-check brand,
   so this is unlikely to change the recommendation.
8. "A check can take up to 300 s" (F3, F6) is unsourced. 300 s is the media-duration cap
   (`max_media_seconds`), and no job timeout exists in the code read. The page's polling budget
   is 240 s after SSE ends (another 240 s with SSE), and a give-up resumes on refresh (F6).

