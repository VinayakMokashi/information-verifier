# Keeping it on the home Windows PC behind a tunnel

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: 0 of 1 verifier(s) finished; the rest are still running or died (usage limit / network) - treat the unverified parts as unverified.** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

Running the app on the owner's Windows 11 Home PC and publishing it through a Cloudflare NAMED tunnel is technically sound and almost free. The domain is the only fixed cost: a .com at Cloudflare Registrar is $10.46/yr today and becomes about $11.17/yr after Verisign's 1 Nov 2026 increase. .in cannot be bought at Cloudflare. It has to come from an Indian registrar, with NIXI e-KYC (Aadhaar/PAN), and then be pointed at Cloudflare's nameservers. On non-Enterprise plans Cloudflare's proxy read timeout is now 125 s, not 100 s, and cannot be changed. That timeout counts silence on the connection, so the app's 15 s SSE heartbeats keep streams alive. The request body limit on Free is 100 MB, well above the 25 MB upload cap. text/event-stream is not on Cloudflare's compressible list. The free plan's edge controls are thin: 5 custom rules with no regex, and 1 rate-limit rule (10 s window, 10 s block, keyed on IP only), so the app's own SQLite daily cap and per-IP limiter stay the real guard. Bot Fight Mode should stay OFF. It "may challenge API or mobile app traffic", and WAF skip rules cannot exempt anything from it, which would endanger a future WhatsApp (Meta) webhook. Quick tunnels (trycloudflare) do NOT support SSE according to Cloudflare's own page (updated 30 Sep 2026). They also cap requests at 200 in flight, have no uptime guarantee, and get a new URL on every restart. The current share_demo.ps1 works only because the page falls back to polling. ngrok Free gives one stable assigned dev domain, but browser HTML traffic gets an interstitial page, and quotas are 1 GB and 20k requests a month. Hobbyist, $10/mo, removes the interstitial. Tailscale Funnel is free, but it is beta, *.ts.net only, and has undisclosed bandwidth limits. A domain-free Cloudflare route (Workers VPC plus workers.dev) exists, free during its beta, but nothing confirms it works without a zone or with SSE. The biggest risk of hosting at home is availability, not cost. Microsoft's docs say devices with no signed-in user are restarted after updates. Home users can pause updates for at most about 5 weeks (an unlimited pause is Insider-only in 2026). Laptops rarely have a "restore on AC power loss" setting. So every process must auto-start at boot without a login, and a check in flight during a reboot is lost.

## Findings

### F1. A Cloudflare named tunnel on a public hostname needs a domain on Cloudflare DNS. .com at Cloudflare Registrar costs $10.46/yr now and about $11.17/yr after Verisign's increase on 1 Nov 2026. .in is NOT available at Cloudflare Registrar.
*Confidence: high — **decision-critical***

Cloudflare's TLD policy page lists .com (Verisign) and .xyz (XYZ) as supported. It does not list .in or .co.in, either as supported or as upcoming. Verisign's .com wholesale fee goes from $10.26 to $10.97 on 1 Nov 2026 (DomainIncite, 27 Apr 2026). Cloudflare passes the registry price through at cost, so $10.46 (= $10.26 + $0.20 ICANN fee, per the domainoffer.net tracker, 15 Oct 2026) should become about $11.17; that figure is derived, not quoted by Cloudflare. .xyz at Cloudflare is $12.30 for the first year and $11.20 to renew (same third-party tracker). Registering a .com before 1 Nov locks the first year at $10.46. A .in has to be bought at an Indian or NIXI-accredited registrar and pointed at Cloudflare's nameservers. The NIXI wholesale tariff is ₹500/yr for .in and ₹400/yr for .co.in (registry.in/tariff, no effective date shown); retail adds 18% GST and the registrar's margin.

Sources: https://www.cloudflare.com/tld-policies/ · https://domainincite.com/?p=31668 · https://domainoffer.net/tld/xyz/cloudflare · https://www.cloudflare.com/application-services/products/registrar/buy-com-domains/ · https://registry.in/tariff · https://developers.cloudflare.com/registrar/top-level-domains/

### F2. .IN domains now need registrant KYC/e-KYC. Indian individuals verify with Aadhaar, PAN or a passport. Registrar notices date the rule to 5 Dec 2025, with IP capture at registration from 27 Jan 2026 and e-KYC plus email checks by March 2026.
*Confidence: medium*

These details are secondhand, from registrar notices (domainindia, hamarahosting, Enom, Domgate's 14 Oct 2025 notice); the NIXI advisory itself was not read. registry.in links an 'eKYC Portal' and a 'KYC is mandatory' page. Sources disagree on whether renewals and contact changes also trigger KYC; Enom says new registrations only. A 7-day verification window and a DigiLocker-only process appear in one blog only and are unverified. For an Indian individual this is a hurdle, not a blocker, but it makes .in slower than a Cloudflare .com.

Sources: https://registry.in/tariff · https://www.domainindia.com/support/kb/mandatory-kyc-for-in-domains · https://support.enom.com/support/solutions/articles/201000120141-nixi-in-domains-compliance-registrant-verification-process · https://portal.domgate.com/announcements/127/GuidelinesNational-Internet-Exchange-of-India-NIXI.html

### F3. On non-Enterprise plans Cloudflare's proxy read timeout is 125 s (it was 100 s) and cannot be changed. The proxy write timeout is 30 s. The free plan accepts request bodies up to 100 MB.
*Confidence: high — **decision-critical***

The connection-limits page (updated 23 Jul 2026) lists Proxy Read Timeout 125 s (error 524, configurable only on Enterprise), Proxy Write Timeout 30 s, Proxy Idle Timeout 900 s, and 400 s client keep-alive. The error-524 page (updated 23 Jul 2026) also gives 125 s, raisable to 6,000 s on Enterprise only. The error-413 page (updated 28 Sep 2026) gives 100 MB for Free and Pro and 200 MB for Business; the app's 25 MB upload cap fits. The app's POSTs return a job_id at once and the 7-300 s work runs in the background, so a 524 cannot hit a submit. Cloudflare's docs do not say whether streamed bytes reset the timer. Third-party write-ups say it measures silence between bytes, so 15 s SSE heartbeats are well inside it. text/event-stream is not on Cloudflare's default compressible list (compression page, 17 Apr 2026). No Cloudflare doc confirms or denies response buffering for SSE; one third-party report suggests cloudflared --protocol http2 if QUIC misbehaves on long streams. Verify with one free real test after setup.

Sources: https://developers.cloudflare.com/fundamentals/reference/connection-limits/ · https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-5xx-errors/error-524/ · https://developers.cloudflare.com/support/troubleshooting/http-status-codes/4xx-client-error/error-413/ · https://developers.cloudflare.com/speed/optimization/content/compression/ · https://levelup.gitconnected.com/the-125-second-silence-why-your-ai-stream-dies-behind-cloudflare-40f776d9e055

### F4. Cloudflare Free gives 5 WAF custom rules (no regex) and 1 rate-limiting rule: a 10 s counting period, a 10 s mitigation timeout, counted per IP only, matching on path and verified-bot fields only. Turnstile is free with up to 20 widgets and 10 hostnames each.
*Confidence: high*

From the custom-rules page (updated 25 Aug 2026), the rate-limiting-rules page (updated 25 Aug 2026) and the Turnstile plans page (updated 14 Aug 2026). The rate-limit rule cannot throttle and cannot use custom counting expressions. The docs do not say whether IPv6 is grouped by /64, so assume per-address, which a mobile client in India on IPv6 can rotate. Edge rate limiting therefore helps only against bursts. The daily cap (5 a day, SQLite) and the app's per-IP limiter remain the real spending guard, and Turnstile on the submit form is the free bot gate. Turnstile does not need the domain to be on Cloudflare.

Sources: https://developers.cloudflare.com/waf/custom-rules/ · https://developers.cloudflare.com/waf/rate-limiting-rules/ · https://developers.cloudflare.com/turnstile/plans/

### F5. Bot Fight Mode (Free) cannot be bypassed with WAF Skip, Bypass or Allow rules or with Page Rules, and Cloudflare says it 'may challenge API or mobile app traffic'. Turning it on would put a future WhatsApp/Meta webhook at risk, so leave it OFF.
*Confidence: high — **decision-critical***

From the Bot Fight Mode page (updated 3 Aug 2026). It runs outside the Ruleset Engine, so skip rules have no effect. The only documented exemption is an IP Access rule that matches first, which is impractical for Meta's changing webhook IP ranges. It covers the whole domain, with no per-endpoint scoping, and it forces JavaScript Detections on. The Telegram bot is unaffected if it calls the app on localhost, as it does today.

Sources: https://developers.cloudflare.com/bots/get-started/bot-fight-mode/

### F6. Cloudflare Quick Tunnels (trycloudflare.com) do NOT support Server-Sent Events. They also cap each tunnel at 200 in-flight requests (excess get 429), have no uptime guarantee, and get a random URL on each restart. They are unfit for a public site or a WhatsApp webhook.
*Confidence: high — **decision-critical***

From Cloudflare's Quick Tunnels page (updated 30 Sep 2026). scripts/share_demo.ps1 uses a quick tunnel. Live streaming works there only because static/index.html falls back to polling /reports when the EventSource fails (es.onerror leads to poll(), lines 483-530). The poll gives up after about 4 minutes (line 262), while a reel check can take up to 300 s, so very long checks could give up early through a quick tunnel. That last point is an inference from the code; it was not run.

Sources: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/ · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/static/index.html · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/share_demo.ps1

### F7. ngrok Free (after the June 2026 pricing change): one stable assigned dev domain (*.ngrok-free.app), 1 GB of transfer and 20,000 HTTP requests a month, up to 3 endpoints, a one-time $5 credit, and a browser interstitial on HTML traffic. Hobbyist at $10/mo removes the interstitial. A custom domain needs Pay-as-you-go at $20/mo.
*Confidence: high — **decision-critical***

From the free-plan-limits doc (undated) and the pricing page (current). The interstitial affects only browser HTML traffic. It can be skipped with an ngrok-skip-browser-warning header or a non-standard User-Agent, and it does not affect API or programmatic calls, so a Meta webhook POST should pass. First-time web visitors still see it, which is bad for a public site. Since 29 Jun 2026 custom domains cost $0.01 per hour, charged only for hours with traffic (ngrok blog, 13 Jul 2026). The $5 credit cannot pay for data transfer. For tens of checks a day, 20k requests a month is enough only if SSE heartbeats do not count as requests (a stream is one request).

Sources: https://ngrok.com/docs/pricing-limits/free-plan-limits/ · https://ngrok.com/pricing · https://ngrok.com/blog/pricing-june-2026

### F8. Windows Update restarts devices that have no signed-in user. Active hours can span at most 18 hours. Windows 11 Home can pause updates for at most about 5 weeks; an unlimited pause is Insider-only in 2026. A 24/7 home server will therefore reboot unattended now and then.
*Confidence: medium — **decision-critical***

Microsoft Learn waas-restart (ms.date 26 Sep 2025): 'Devices that don't have locally signed-in users, or active RDP sessions, are restarted.' The 18-hour active-hours maximum and the NoAutoRebootWithLoggedOnUsers registry policy are documented there, but Microsoft warns that policy 'doesn't work exactly as per description'. Whether these policy keys take effect on Home was not verified. Third-party reports from 2026 (Notebookcheck, Neowin, DigitalCitizen) say Insider builds can renew a 35-day pause indefinitely and drop forced restarts. That has not reached general release, and support.microsoft.com was not read directly. Consequence: uvicorn, the bot and cloudflared must start at boot with no login. Any check in flight during a reboot is lost, and the daily-cap slot it already took stays used unless the app refunds it.

Sources: https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart · https://www.notebookcheck.net/Windows-11-lets-you-pause-updates-indefinitely-ends-forced-restarts-for-Insiders.1283476.0.html · https://www.digitalcitizen.life/windows-11-finally-lets-you-pause-updates-indefinitely/

### F9. Tailscale Funnel is free on the Personal plan but still beta. It is limited to *.ts.net names (no custom domain is documented), ports 443, 8443 and 10000, and 'non-configurable bandwidth limits' whose numbers are not published.
*Confidence: high*

From the Funnel KB page (last validated 20 Jan 2026). TLS ends on the device (the relays cannot read the traffic). Public DNS can take up to 10 minutes. It needs v1.38.3 or later, MagicDNS, HTTPS certificates and a funnel node attribute. There is no edge WAF, rate limiting or Turnstile integration, and no timeout figures are published. It does give a stable HTTPS URL that a WhatsApp webhook could use, but the beta label and unknown bandwidth make it a fallback, not the primary.

Sources: https://tailscale.com/kb/1223/funnel

### F10. Cloudflare Workers VPC (beta, free on all Workers plans during the beta) lets a Worker reach a service behind a tunnel. In principle that is a domain-free route via workers.dev, but no doc confirms it works without a zone or with SSE or 25 MB uploads.
*Confidence: medium*

From the Workers VPC overview and get-started pages (updated 12 Oct 2026) and the pricing page. The tunnel is created from the Workers VPC dashboard with a token and no domain step; the Worker calls env.VPC_SERVICE.fetch(). The documented workflow uses npm/wrangler, and Node is not installed locally; the dashboard editor may be enough, but that is unverified. Standard Workers request and CPU limits apply, plus the beta's change risk. Treat it as an experiment, not the plan.

Sources: https://developers.cloudflare.com/workers-vpc/ · https://developers.cloudflare.com/workers-vpc/get-started/ · https://developers.cloudflare.com/workers-vpc/reference/pricing/

### F11. Running 24/7: cloudflared installs as a Windows service. The Python processes need Task Scheduler ('At startup', 'Run whether user is logged on or not', restart on failure) or a service wrapper such as WinSW or NSSM. Electricity and upload bandwidth are minor costs.
*Confidence: medium*

Cloudflare's Windows service doc (updated 11 Sep 2026) shows `cloudflared.exe service install` with the config in C:\Windows\System32\config\systemprofile\.cloudflared (a locally managed tunnel). The dashboard's token install (`cloudflared.exe service install <token>`) is simpler but was not re-read here. Task Scheduler is available on Home. NSSM's last stable release is old (2.24, 2014, from memory); WinSW is the maintained alternative (not re-verified). Run uvicorn with one worker, and give the service account access to .env, the SQLite file and ffmpeg on PATH. Power, estimated rather than sourced: an idle desktop draws about 30-60 W, i.e. 22-44 kWh a month, about ₹150-350 a month at ₹7-8/kWh. A laptop with its lid closed draws about 8-15 W, about ₹40-90 a month. Disable sleep and hibernate, and set lid-close to 'do nothing'. Desktops usually have a BIOS 'Restore on AC power loss' setting; most consumer laptops do not, though a laptop's battery rides through short power cuts while the router still dies. Bandwidth: pages and SSE text are tiny. User uploads (up to 25 MB) and yt-dlp reel downloads use the home DOWNLINK. About 1-5 Mbps of upload is ample for tens of checks a day.

Sources: https://developers.cloudflare.com/tunnel/advanced/local-management/as-a-service/windows/ · https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart

### F12. Security exposure: through a tunnel, no inbound port is opened on the router. Only the tunnelled origin (127.0.0.1:8000) is reachable, but every route on it, including /dashboard, becomes publicly reachable unless it is fenced.
*Confidence: medium*

Residual risks: (a) /dashboard is described as 'this machine only'. Through cloudflared every request arrives from 127.0.0.1, so a check based on the client address would treat the whole internet as local. Verify how dashboard.py decides 'local', and also block /dashboard with a free WAF custom rule or leave it out of the tunnel's ingress. (b) The same applies to the per-IP limiter: behind the tunnel it must key on CF-Connecting-IP, and it must only trust that header when the request came through cloudflared. (c) yt-dlp and ffmpeg parse attacker-chosen media on the owner's personal PC, so a parser bug lands on a machine that also holds personal files and the .env keys. Run them as a low-privilege account and keep yt-dlp updated. (d) The SSRF fences were already verified by a colleague (3 extractors only, platform-supplied caption URLs). Points (a) and (b) are inferences from the architecture and were not tested here.

Sources: C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/CLAUDE.md

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| Cloudflare named tunnel + .com bought at Cloudflare Registrar (Free plan) | About $0.87/mo (₹75), i.e. $10.46 for the first year if bought before 1 Nov 2026, then about $11.17/yr. The tunnel and Free plan cost $0. Electricity about ₹40-350/mo depending on laptop or desktop. | Best fit for a public site plus a WhatsApp webhook: a stable HTTPS URL on its own domain, SSE works, uploads up to 100 MB, 125 s read timeout with heartbeats, Turnstile and 5 WAF rules free. | Stable URL that WhatsApp/Meta can use as a webhook; No inbound port is opened; TLS and DDoS absorption happen at Cloudflare's edge; 100 MB body limit is far above the 25 MB cap; 125 s timeout and 15 s heartbeats are fine for SSE; cloudflared runs as a Windows service and reconnects on its own; Free WAF custom rules can fence /dashboard; Turnstile is free | Requires a domain; .in is impossible at Cloudflare Registrar; Only 1 free rate-limit rule (10 s window, IP only), so the app's own limits stay essential; Bot Fight Mode must stay off (it cannot be scoped and may block webhooks); Availability is only as good as the home PC, its power and its ISP |
| Cloudflare named tunnel + .in from an Indian registrar (nameservers pointed at Cloudflare) | About ₹50-80/mo: NIXI wholesale is ₹500/yr plus 18% GST plus the registrar's margin; first-year promotions vary (retail prices not verified). The tunnel costs $0. | The same technical fit as the .com option, with an Indian identity for the brand. | Indian-looking domain, paid in rupees by Indian card; Same Cloudflare features as the .com option | NIXI KYC/e-KYC (Aadhaar/PAN), with conflicting reports on whether renewals re-trigger it; Two vendors: the registrar for the domain, Cloudflare for DNS; Registrar renewal markups are not at cost |
| Cloudflare Workers VPC fronted by a workers.dev Worker (no domain) | $0 during the beta (standard Workers Free limits apply) | Experimental. It could avoid buying a domain, but zone-free operation, SSE pass-through and 25 MB uploads are all unconfirmed. | Possibly zero cost and no domain; Tunnel created from the dashboard with a token | Beta: 'Features and APIs may change'; Documented workflow needs wrangler/Node (not installed locally); Nothing documented on SSE or large bodies through env.VPC_SERVICE.fetch; workers.dev subdomains are a common phishing host and may carry low trust for a fact-check brand |
| Tailscale Funnel (*.ts.net) | $0 (Personal plan) | A workable free fallback with a stable HTTPS URL. Weak as a public site: beta, undisclosed bandwidth limits, no edge security controls. | Free, stable *.ts.net name, no domain needed; TLS ends on the device; Runs unattended as a Windows service | Beta; Non-configurable, undisclosed bandwidth limits; Ports 443, 8443 and 10000 only; no custom domain documented; No WAF, rate limiting or bot controls at the edge |
| ngrok Free (assigned dev domain) | $0 (1 GB transfer and 20k requests a month; one-time $5 credit) | Good for developing and testing the WhatsApp webhook: a stable dev domain, and the interstitial does not hit API calls. Poor for the public web page, where every new browser visitor sees the interstitial. | One stable assigned domain without buying one; Interstitial skipped for programmatic and webhook traffic; Free endpoints have no session timeout | Browser interstitial on HTML for first-time visitors (cookie lasts 7 days); 1 GB a month of transfer; uploads and reel media count against it; 20k HTTP requests a month; Custom domain only on Pay-as-you-go at $20/mo |
| ngrok Hobbyist | $10/mo (less with annual billing) | No interstitial and an ngrok-branded domain, but it costs more than a whole year of a Cloudflare .com. | No interstitial; No DNS or domain management | $120/yr against about $11/yr for a Cloudflare domain; No bring-your-own domain on this tier |
| cloudflared Quick Tunnel (trycloudflare.com) | $0 | Ad-hoc demos only, as in today's share_demo.ps1. Not for a public site or any webhook. | No account, no domain, one command | No SSE support (the page falls back to polling); Random URL on every restart, so it cannot be registered as a webhook; 200 in-flight request cap; no uptime guarantee |

## Recommendation (the researcher's)

If the app stays on the home PC, use a Cloudflare NAMED tunnel with a .com bought at Cloudflare Registrar. Buy it before 1 Nov 2026 to get $10.46 for the first year; after that it is about $11.17/yr. That gives a stable HTTPS URL for both the website and the WhatsApp webhook, at under ₹100 a month in total.

Setup:
- Install cloudflared as a Windows service.
- Run uvicorn (one worker) and the Telegram bot from Task Scheduler ('At startup', 'Run whether user is logged on or not', restart on failure), or under WinSW.
- Turn off sleep and hibernate, set lid-close to 'do nothing', and enable BIOS restore-on-AC-loss if the machine has it.
- Set active hours to 18 h. Expect occasional unattended update reboots.
- Keep Bot Fight Mode OFF and put Turnstile on the submit form.
- Use one WAF custom rule to block /dashboard publicly.
- Make the per-IP limiter read CF-Connecting-IP (trusted only from cloudflared).
- Keep relying on the SQLite daily cap; Cloudflare's single free rate-limit rule is only a burst guard.
- Before calling it done, run one free check through the tunnel against the demo server (serve_demo.py) to confirm live SSE arrives unbuffered. If QUIC misbehaves, try --protocol http2.

Fallbacks:
- If no domain is wanted yet, ngrok Free's assigned dev domain is a fine zero-cost way to build the WhatsApp webhook, since the interstitial does not touch API calls. Tailscale Funnel is the free stable-URL fallback for the site.
- Do not use quick tunnels for anything public: they do not support SSE, and the URL changes on every restart.
- Choose .in only if the Indian brand matters enough to take on NIXI e-KYC and a second vendor.

The deciding weakness of home hosting is uptime (Windows Update restarts, power cuts, ISP), not cost. Weigh that against the cloud-VM branch of this evaluation.

## Unknowns

- Whether streamed bytes or SSE heartbeats reset Cloudflare's 125 s proxy read timeout is not stated in Cloudflare's docs; only third-party sources say so. One free test through the tunnel would settle it.
- Whether Cloudflare buffers text/event-stream through a named tunnel. No primary doc answers this; it is widely reported to stream, but that was not verified here.
- Whether the free rate-limit rule groups IPv6 by /64 is undocumented.
- Whether a Workers VPC tunnel works without any Cloudflare zone, and whether it passes SSE and 25 MB bodies.
- The exact .IN e-KYC scope (renewals and contact changes too?) and today's retail .in prices at Indian registrars. The NIXI advisory itself was not read.
- Whether the Windows Update restart policies (NoAutoRebootWithLoggedOnUsers, active-hours registry keys) are honoured on Windows 11 Home, and when the unlimited pause leaves Insider builds; support.microsoft.com's pause article was not read directly.
- Whether Cloudflare Registrar accepts the owner's Indian card for a USD charge, and whether auto-renew works under RBI e-mandate rules.
- Tailscale Funnel's actual bandwidth or throughput cap and any request timeouts are unpublished.
- Whether ngrok's 20k request/month quota counts SSE heartbeats; they should be one long request, but this is unverified.
- How app/api/dashboard.py decides 'local only'. Behind cloudflared every request comes from 127.0.0.1, so this must be checked before going public.
- The electricity figures are estimates from typical idle draw at ₹7-8/kWh, not measured on the owner's machine.

