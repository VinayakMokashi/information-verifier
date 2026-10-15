# Does reel/Shorts link resolution survive a datacenter IP?

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: independently verified (verdicts inline).** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

If the app moves to a datacenter host and keeps fetching links anonymously with yt-dlp, the link feature becomes unreliable. YouTube is the most exposed, because its bot check sits on the player/metadata request itself. On a flagged IP, the metadata-only resolve_link() fails before any caption or audio request happens. This is not limited to stream downloads.

yt-dlp maintainers said in 2026 that YouTube "regularly blocks or restrict[s] datacenter IPs", and that PO tokens "are not a solution if your IP is already blocked". Instagram documents much stricter anonymous limits for cloud, VPN and proxy IPs. Facebook enforces a per-IP anonymous view limit. Neither has hard 2026 datacenter measurements, so expect intermittent failure on both rather than a guaranteed block.

The app would also misreport every one of these blocks to users as "That post needs a login to view" (checked offline against `_classified`).

None of these fix it:
- a PO-token plugin
- keeping yt-dlp updated
- IPv6 rotation

Throwaway-account cookies swap the problem for an explicit ban risk on all three platforms.

The cheapest reliable fix is to send only link traffic (resolve, subtitle fetch and capped audio, through one exit per check) out of a residential IP. There are two ways:
- **Home PC:** $0, but it only works while the PC is on.
- **Pay-as-you-go residential proxy:** traffic never expires; about $0.15–1 a month at the current 5/day cap. A one-off $5 (DataImpulse) or $7.35 (IPRoyal) top-up lasts months.

Measured today from the home connection, a resolve costs 0.25–0.34 MB, and YouTube, Instagram and Facebook `/watch` links still resolve anonymously.

A separate bug, independent of hosting: the app's extractor allowlist uses yt-dlp's full-match semantics. As a result, Facebook `/reel/<id>`, `share/r/` and `fb.watch` links fail in the app today ("That link could not be read."). link_probe.py doesn't use the allowlist, so it reported share links as working.

## Findings

### F1. YouTube's bot check ('Sign in to confirm you're not a bot') is applied at the player/metadata request, so on a flagged datacenter IP the app's metadata-only resolve fails outright. Captions and audio are never reached; this is not limited to stream downloads. yt-dlp maintainers stated in January and March 2026 that YouTube regularly blocks or restricts datacenter IPs.
*Confidence: high — **decision-critical***

Mechanism:
- The error comes back in the player API response's playabilityStatus (LOGIN_REQUIRED).
- That same request supplies the caption-track list and the stream URLs, and the yt-dlp extractor raises it via raise_no_formats (installed 2026.08.19, extractor/youtube/_video.py:4063-4076).
- So extract_info(download=False) in resolve_link() fails before subtitle_text() or download_link_audio() can run.

Evidence:
- #16221 (2026-03-12, VPS, nightly 2026.03.11): the user was extracting metadata and got 'android_vr player response playability status: LOGIN_REQUIRED' at the first stage.
- #15573 (2026-01-15, VPS whose stream URL embeds a 54.90.x.x address), MEMBER DTrombett: 'YouTube regularly blocks or restrict datacenter IPs'. CONTRIBUTOR ruben1PvP: 'This has been a thing for more than a year now.'
- #16147 (2026-03-06), DTrombett: with 'a suspicious IP (e.g. a server, VPN, proxy, etc) YouTube is likely to ban you, there's nothing we can do'.
- The pinned known-issues thread #3766 (last updated 2026-08-27) lists #10128 as intractable: 'Your IP has been blocked by YouTube while you are logged out… The safer solution is to use a different IP.'

It is per-IP and changes over time, not universal:
- #15573: regular videos still worked on that AWS-range VPS (with cookies).
- #17376 (2026-08-06, user report): 'a cleaner GCP IP works more often', but still intermittently LOGIN_REQUIRED or HTTP 403.

On less-flagged IPs, a second tier of failure is googlevideo 403s on the audio download (#17376, #15573).

No 2025-2026 provider-specific reports were found for DigitalOcean or Fly. Oracle, Hetzner and Railway reports are only secondary or third-party.

Sources: https://github.com/yt-dlp/yt-dlp/issues/3766 · https://github.com/yt-dlp/yt-dlp/issues/10128 · https://github.com/yt-dlp/yt-dlp/issues/16221 · https://github.com/yt-dlp/yt-dlp/issues/15573 · https://github.com/yt-dlp/yt-dlp/issues/16147 · https://github.com/yt-dlp/yt-dlp/issues/17376 · https://dev.to/osovsky/i-was-building-a-cloud-video-service-youtube-turned-me-into-an-ip-trafficker-1l9o

**Verifier: confirmed.** Corrected: YouTube's bot check is applied at the player/metadata request, so the app's metadata-only resolve_link fails before captions or audio are ever requested.
> Installed yt-dlp 2026.08.19, extractor/youtube/_video.py:4063-4076: a playability reason containing 'sign in' goes to self.raise_no_formats(reason, expected=True). common.py:1265-1272 raises ExtractorError unless ignore_no_formats_error or wait_for_video is set, and the app's _base_opts() sets neither, so extract_info(download=False) raises. #16221 (created 2026-03-12, nightly 2026.03.11, on a VPS while extracting metadata) shows 'android_vr player response playability status: LOGIN_REQUIRED' followed by 'Sign in to confirm you're not a bot'. #15573 (2026-01-15): DTrombett [MEMBER] wrote 'YouTube regularly blocks or restrict datacenter IPs', and ruben1PvP [CONTRIBUTOR] wrote 'This has been a thing for more than a year now'. The issue body contains a '/ip/54.90.116.137/' URL. #16147: DTrombett [MEMBER], 2026-03-06, 'suspicious IP (e.g. a server, VPN, proxy, etc) YouTube is likely to ban you'. Known-issues #3766 was updated 2026-08-27. Under #10128 it says: 'The safer solution is to use a different IP' and a PO token provider 'will not help if your IP is already blocked'. One nuance: #15573 is about a 403 on download with --cookies, not the metadata stage. The metadata-stage evidence is #16221.

### F2. PO tokens (including the bgutil-ytdlp-pot-provider plugin) do not get a blocked datacenter IP past YouTube's bot check. PO tokens are currently required only for stream (GVS) requests and some subtitle (Subs) requests, never for the metadata request the app depends on.
*Confidence: high — **decision-critical***

- MEMBER bashonly, #16773 (2026-05-21, a datacenter IP with bgutil 0.8.1): 'PO tokens are **not** a solution if your IP is already blocked. They *may* work as a preventative measure.'
- Known-issues #3766 (2026-08-27): a PO token provider 'will not help if your IP is already blocked.'
- bgutil README (v2.0.2): 'a PO Token does not bypass IP-based login restrictions.' If the bot check persists, which it calls 'common on datacenter IPs', you 'additionally need to pass cookies' (bgutil #37). It requires yt-dlp ≥2025.05.22 plus Node ≥22 or Deno ≥2.0, or Docker.
- PO Token Guide wiki (edited 2026-07-12): 'Currently, only GVS and Subs require PO Tokens for some clients.' The web client needs them for Subs and GVS; tv, android_vr and web_embedded need none.
- Installed yt-dlp 2026.08.19 defaults to ('visionos','web'), or ('visionos',) alone when no JS runtime is present, as on this PC (_video.py:143-145).
- The plugin itself broke in August 2026: in #17368, bashonly said 'This is an issue with the PO token provider… Disable the plugin and use default player clients'.

Sources: https://github.com/yt-dlp/yt-dlp/issues/16773 · https://github.com/yt-dlp/yt-dlp/issues/3766 · https://github.com/Brainicism/bgutil-ytdlp-pot-provider · https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide · https://github.com/yt-dlp/yt-dlp/issues/17368

**Verifier: confirmed.** Corrected: PO tokens, including bgutil, do not unblock an IP that is already blocked. Currently only GVS and Subs need PO tokens.
> #16773 (created 2026-05-21, titled 'All player clients fail on datacenter IP despite bgutil PO Token'): bashonly [MEMBER], 2026-05-21, said 'PO tokens are **not** a solution if your IP is already blocked. They *may* work as a preventative measure.' The bgutil README, line 168, has the exact quote: 'a PO Token does not bypass IP-based login restrictions. If you still get "Sign in to confirm you're not a bot" after a token was generated (common on datacenter IPs), you additionally need to pass cookies; see #37.' It also requires 'yt-dlp 2025.05.22 or above' and 'Node.js (>= 22) or Deno (>= 2.0.0)'. The latest bgutil release is 2.0.2, published 2026-10-07. The PO-Token-Guide wiki (edited Jul 12, 2026) says: 'Currently, only GVS and Subs require PO Tokens for some clients.' #17368: bashonly, 2026-08-05, 'This is an issue with the PO token provider' (bgutil #242). The local _video.py:143-145 has _DEFAULT_CLIENTS=('visionos','web') and _DEFAULT_JSLESS_CLIENTS=('visionos',), and this PC has no deno or node on PATH.

### F3. Anonymous Instagram access from cloud IPs faces much stricter per-IP limits than from home IPs. Expect intermittent 'redirected to the login page / rate-limit reached or login required' failures rather than a guaranteed block. No 2025-2026 primary measurement from a datacenter was found.
*Confidence: medium — **decision-critical***

- Instaloader troubleshooting docs (site shows v4.15.4, released 2026-10-12): services offering 'promiscuous IP addresses, such as cloud, VPN and public proxy services, might be subject to significantly stricter limits for anonymous access', while logged-in access 'do[es] not seem to be affected'.
- yt-dlp 2026.08.19's own Instagram extractor (instagram.py:505-510) raises 'The webpage request was redirected to the login page. You have exceeded the rate-limit for accessing posts anonymously'.
- MEMBER bashonly (#17074, 2026-06-28): 'Impersonation is required now for Instagram support w/o cookies.' The 2026.07.04 release reworked the extractor (#17075).
- Without curl_cffi, 2026.08.19 skips the GraphQL call and falls back to scraping /p/<id>. Measured 2026-10-15 from the residential IP, two public reels still resolved this way (the venv has no curl_cffi).
- Counter-evidence: a cobalt maintainer (#1463, 2025-11-20) blamed a self-hosted instance's Instagram failure on 'IP reputation', yet that reporter said videos and carousels worked from GCP.
- Inference: shared PaaS outbound IPs (Render, Railway, Fly) pool the anonymous allowance with other tenants.

Sources: https://instaloader.github.io/troubleshooting.html · https://github.com/yt-dlp/yt-dlp/issues/17074 · https://github.com/yt-dlp/yt-dlp/releases/tag/2026.07.04 · https://github.com/imputnet/cobalt/issues/1463 · https://github.com/yt-dlp/yt-dlp/issues/16402

**Verifier: confirmed.** Corrected: Anonymous Instagram access from cloud IPs faces stricter per-IP limits than from home IPs, so expect intermittent failures rather than a guaranteed block. The strongest source is long-standing Instaloader documentation, not a 2026 measurement.
> The Instaloader troubleshooting page (site at v4.15.4; the GitHub release is dated 2026-10-12) says: 'There have been observations that services, that in their nature offer promiscuous IP addresses, such as cloud, VPN and public proxy services, might be subject to significantly stricter limits for anonymous access. However, logged-in accesses do not seem to be affected.' The wording is old ('observations'). The site version is current, but this is not dated 2025-2026 evidence. Local instagram.py:506-510 raises 'redirected to the login page. You have exceeded the rate-limit for accessing posts anonymously', and every request is gated on _can_impersonate. #17074: bashonly, 2026-06-28, 'Impersonation is required now for Instagram support w/o cookies', and again on 2026-06-29: 'The site blocks anonymous API requests that do not have a browser fingerprint'. That makes curl_cffi effectively mandatory on any server. curl_cffi is confirmed absent from the venv. Medium confidence is right. I did not re-check cobalt #1463.

### F4. Logged-in cookies from a throwaway account carry an explicit, documented ban risk on all three platforms, and need ongoing manual upkeep. They are a stopgap, not a reliable fix.
*Confidence: high — **decision-critical***

YouTube:
- yt-dlp wiki Extractors page (edited 2025-06-11): 'By using your account with yt-dlp, you run the risk of it being banned (temporarily or permanently).'
- Known-issues #3766 (2026-08-27): passing logged-in cookies 'may get your account blocked. The safer solution is to use a different IP.'
- #16147 (2026-03-06): cookies of 'a newly registered Google account' were used, 'but the account was quickly banned by Google'. That was after roughly 600 downloads a day, far heavier than this app.
- Cookie-specific breakage: #16212 (2026-03-11) caused 'The page needs to be reloaded' failures, while removing cookies helped.
- With cookies, yt-dlp switches to authed clients (web_embedded, tv_downgraded, web; _video.py:145), which need a JS runtime and PO tokens for web.

Instagram: bashonly, #17074 (2026-06-29): 'there is the risk that your account will be flagged or banned.'

Facebook: bashonly, #16621 (2026-05-03): 'Facebook is perfectly happy to ban your account if it detects third party tool usage. I think it would be better to just download at a more reasonable pace and abide by their anonymous access rate-limit.'

A headless server cannot use --cookies-from-browser, so cookies must be re-exported by hand.

Sources: https://github.com/yt-dlp/yt-dlp/wiki/Extractors · https://github.com/yt-dlp/yt-dlp/issues/3766 · https://github.com/yt-dlp/yt-dlp/issues/16147 · https://github.com/yt-dlp/yt-dlp/issues/16212 · https://github.com/yt-dlp/yt-dlp/issues/17074 · https://github.com/yt-dlp/yt-dlp/issues/16621

**Verifier: confirmed.** Corrected: Cookies from throwaway accounts carry an explicit, documented ban risk on YouTube, Instagram and Facebook and need manual upkeep. They are a stopgap only. Correction to the detail: the #16147 user was blocked after about 600 downloads in total, while doing hundreds a day. The issue does not say 600 a day.
> yt-dlp wiki Extractors.md, line 13: 'By using your account with yt-dlp, you run the risk of it being banned (temporarily or permanently).' Known-issues #3766 (updated 2026-08-27) says passing cookies 'may get your account blocked'. #16147 issue body: 'download hundreds of audio files per day. My download requests were rejected after about 600 downloads… I used the cookies of a newly registered Google account, but the account was quickly banned by Google.' #17074: bashonly, 2026-06-29, 'there is the risk that your account will be flagged or banned'. #16621: bashonly, 2026-05-03, 'Facebook is perfectly happy to ban your account if it detects third party tool usage… abide by their anonymous access rate-limit'. I did not re-check #16212.

### F5. Residential proxy pay-as-you-go prices on 2026-10-15, with Bright Data now closed to individuals. At the measured ~1 MB per link check, proxying only link traffic costs about $0.001–0.007 per check, i.e. about $0.15–1.10/month at the 5/day cap.
*Confidence: high — **decision-critical***

Current pricing pages:
- Decodo: pay-as-you-go $4/GB + VAT, bought 1 GB at a time. Smallest subscription is 3 GB for $11.25 + VAT ($3.75/GB). 3-day, 100 MB trial that auto-activates a plan unless cancelled.
- IPRoyal: pay-as-you-go $7.35/GB (1 GB), $6.25 (2 GB), $5.51 (10 GB); 'Never expiring traffic'.
- DataImpulse: $1/GB; 'Intro' $5 for 5 GB for new users; 'Traffic never expires'.
- Webshare: rotating residential 1 GB for $3.50/month (subscription, shown as 50% off $7.00).
- Bright Data: pay-as-you-go shown as $4/GB, discounted from $8 (the page also shows code RESIGB50 for 50% off for 3 months).

Bright Data's network-access policy: 'KYC approval is required for all Residential network access' for zones created after 2026-07-07. Applications must come from 'registered businesses with a company domain', and personal projects are not approved. So it is not usable by this owner.

Target restrictions:
- Decodo blocks a 'Streaming' category by default, unlockable only after ID verification on rotating residential subscriptions. YouTube is not named.
- IPRoyal limits unverified accounts.
- DataImpulse's blocklist (as of December 2023) does not name YouTube, Instagram or Facebook.

Bandwidth, measured 2026-10-15 with a free metadata-only script (counts TLS bytes):
- YouTube Shorts resolve: 337,503 B.
- Instagram reels: 263,836 B and 287,671 B.
- Facebook /watch: 246,538 B.
- YouTube best audio: 212,714 B for a 14 s Short, about 1 MB per 70 s.
- Instagram audio: 0.42 MB per 70 s (project measurement).

Worst case per check is already bounded by the 25 MB download cap: about $0.03–0.18.

Sources: https://decodo.com/proxies/residential-proxies/pricing · https://help.decodo.com/docs/residential-proxy-restricted-targets · https://iproyal.com/pricing/residential-proxies/ · https://dataimpulse.com/ · https://docs.dataimpulse.com/blocked-websites · https://www.webshare.io/residential-proxy · https://brightdata.com/pricing/proxy-network/residential-proxies · https://docs.brightdata.com/products/residential/network-access · C:\Users\VINAYA~1\AppData\Local\Temp\claude\c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier\4b88200f-d561-4246-b38d-1eac8cf3cade\scratchpad\measure_resolve_bytes.py

**Verifier: corrected.** Corrected: The vendor prices are correct as of 2026-10-15:
- DataImpulse: $1/GB, an 'Intro' offer of $5 for 5 GB 'For New Users', and 'Traffic never expires'.
- IPRoyal pay-as-you-go: $7.35/GB at 1 GB, $6.25 at 2 GB, $5.51 at 10 GB; 'Never expiring traffic'; pays by Visa, Mastercard, Amex, Discover, PayPal, Alipay or crypto.
- Decodo: $4/GB + VAT, bought 1 GB at a time; smallest subscription 3 GB for $11.25 + VAT; 100 MB, 3-day trial that auto-activates a plan. The page does not say whether pay-as-you-go traffic expires.
- Bright Data: new Residential zones created after July 7, 2026 need KYC; access is for registered companies only; personal-email accounts and 'Personal projects… are not approved'.

The monthly figure is wrong. '$0.15–1.10/month at the 5/day cap' is a bound only for checks that get past resolve. In the current code a failed resolve REFUNDS the daily slot (routes.py _quota, used by verify_link). Every blocked, private or bad link therefore costs ~0.25–0.34 MB of proxy traffic without counting against the cap; only the in-memory per-IP rate limiter bounds it. A server with Deno would also pull YouTube player JS (1–3 MB, unmeasured) on every cold cache. The proxy needs its own byte budget; the 5/day cap does not bound it.
> Fetched today:
- dataimpulse.com: '$1 per GB without a subscription', an 'Intro… For New Users' tier of $5 for 5 GB, 'Traffic never expires'.
- iproyal.com/pricing/residential-proxies: the 1/2/10 GB tiers as above, payment methods listed, 'Your traffic is available until you decide to use it'.
- decodo.com pricing: '$ 4+ VAT', 'purchase only one GB at a time', 3 GB at $3.75/GB ($11.25 + VAT), 100 MB for 3 days, then the chosen plan 'will activate automatically'.
- docs.brightdata.com network-access: 'For new Residential zones created after July 7, 2026, KYC approval is required', 'granted only to registered companies', 'Personal projects… are not approved'.

Repo, app/api/routes.py:
- verify_link runs resolve_link inside `async with _quota(request)`.
- _quota (lines 81-113) calls give_back() on any exception when nothing was started.
- verify_link's docstring says a bad link is 'refunded: nothing was spent'.

I did not re-check Webshare.

### F6. Routing only link traffic through the home PC's residential connection costs $0 and keeps the exact IP class measured working since 2026-07-28 (re-measured 2026-10-15). The one hard rule is that resolve and download must leave through the same IP.
*Confidence: high — **decision-critical***

- Tailscale's free Personal plan: 'Up to 6 users', 'Unlimited user devices', '50 tagged resources included' (exit nodes count as tagged resources).
- Userspace networking (doc last validated 2025-11-12) runs tailscaled as a local SOCKS5/HTTP proxy where /dev/net/tun is unavailable. The doc is silent on exit nodes in that mode.
- Routing the whole VM through a home exit node would also send Anthropic, Telegram and WhatsApp traffic through home, and cut the VM off when the PC is down. So use a per-app proxy instead: yt-dlp's `proxy` option plus an httpx proxy for subtitle_text.
- Alternative needing no tunnel at all: an outbound long-poll 'link agent' on the PC, the same pattern as the Telegram bot.
- Same-exit rule: googlevideo URLs are bound to the IP that resolved them (#15573's manifest URL embeds '/ip/54.90.116.137/'). The yt-dlp FAQ, as quoted by a secondary source, says the media fetch must come from the same address. Never resolve on one IP and download on another.
- Availability equals PC plus home internet uptime.

Sources: https://tailscale.com/pricing · https://tailscale.com/kb/1112/userspace-networking · https://github.com/yt-dlp/yt-dlp/issues/15573

**Verifier: confirmed.** Corrected: Routing only the link traffic through the home PC costs $0 on Tailscale's free Personal plan. The resolve and the download must leave through the same IP.
> tailscale.com/pricing (undated, © 2026): Personal is 'Free forever', 'Up to 6 users', 'Unlimited user devices', '50 tagged resources included' (extra ones $1/month each). Tagged resources are defined as 'Resources like exit nodes, etc.'. Same-exit rule: the #15573 issue body contains a googlevideo URL carrying '/ip/54.90.116.137/', so stream URLs are bound to the IP that resolved them. PROJECT_PLAN.md §0a dates the link feature 'BUILT (2026-07-28)' and live-verified from home that day. I did not re-check the userspace-networking page, which only affects PaaS hosts without /dev/net/tun.

### F7. IPv6 rotation within a /64 is losing effectiveness against YouTube in 2026, and typical PaaS hosts don't give you a /64 to rotate.
*Confidence: medium*

- Invidious #5998 (2026-08-29): an operator using IPv6-only plus a random address per video within the /64 first got about 30 videos before a roughly 1-hour block. Six months later it was 'back to about 10 videos and blocks remain for several hours'; the operator suspected YouTube blocks 'entire /64's'. A maintainer replied only that PO-token generation work is ongoing.
- Tunelio, a vendor blog (published 2026-07-16, updated 2026-09-07): 'IPv6 was worse: YouTube scores a whole /64 as one unit'. It advises forcing IPv4 and claims 'roughly one in four fresh exit IPs hit the bot wall on first contact' in August 2026 (fleet type unspecified).
- No 2025-2026 evidence found either way for Instagram or Facebook.

Sources: https://github.com/iv-org/invidious/issues/5998 · https://tunelio.dev/blog/yt-dlp-sign-in-to-confirm-not-a-bot/

### F8. Keeping yt-dlp current is necessary but does not fix IP blocks. A cloud image also needs a JavaScript runtime (Deno) and curl_cffi, and this PC's venv has neither today.
*Confidence: high*

- yt-dlp 2025.11.12, 'Important changes': 'An external JavaScript runtime is now required for full YouTube support' (#15012).
- Locally, yt-dlp warns 'YouTube extraction without a JS runtime has been deprecated' and uses only the visionos client. It still resolved a Short on 2026-10-15.
- Instagram: 'Impersonation is required now for Instagram support w/o cookies' (bashonly, 2026-06-28). The extractor rework shipped in 2026.07.04. The venv lacks curl_cffi, and its post-page fallback still worked from home on 2026-10-15.
- Facebook: 'Cannot parse data' is reported on 2026.08.19 (#17720, opened 2026-09-23; one user says title and format lookup alone fail; a contributor posted a patch on 2026-10-01).
- Stable releases in 2026: 01-29, 01-31, 02-04, 02-21, 03-03, 03-13, 03-17, 06-09, 07-04, 08-19. None since 2026-08-19, so fixes sometimes exist only in nightly or master.
- Image recipe: pip `yt-dlp[default,curl-cffi]` (gamer191, 2025-08-17) plus Deno.

Sources: https://github.com/yt-dlp/yt-dlp/releases/tag/2025.11.12 · https://github.com/yt-dlp/yt-dlp/issues/15012 · https://github.com/yt-dlp/yt-dlp/issues/17074 · https://github.com/yt-dlp/yt-dlp/releases/tag/2026.07.04 · https://github.com/yt-dlp/yt-dlp/issues/17720 · https://github.com/yt-dlp/yt-dlp/issues/13831 · https://github.com/yt-dlp/yt-dlp/releases

### F9. Hosting-independent bug: the app's extractor allowlist ['Instagram','Youtube','Facebook'] is matched by yt-dlp with re.fullmatch, so Facebook /reel/<id>, facebook.com/share/r/… and fb.watch links fail in the app today with 'That link could not be read.'
*Confidence: high*

How yt-dlp matches the allowlist (installed source):
- YoutubeDL.py:934-939 calls orderedSet_from_options(..., use_regex=True).
- utils/_utils.py:5340 uses `re.compile(val, re.I).fullmatch` against extractor names.

Result:
- 'Facebook' admits only 'facebook', not 'facebook:reel'.
- share/r/ and fb.watch links have no dedicated extractor at all and need the generic one (redirect-following), which is deliberately excluded.
- Checked offline 2026-10-15: app.providers.links.resolve_link() returned kind='other' for facebook.com/reel/1195289147628387, facebook.com/share/r/1Tssj7bVav/ and an fb.watch/ URL, with zero network bytes.
- /watch?v=, /<page>/videos/<id>, YouTube (shorts, watch, youtu.be) and Instagram /reel/, /reels/, /p/ are admitted.

Why it went unnoticed:
- The comment at app/providers/links.py:67-71 ('anchored at the start, so "Youtube" also admits YoutubeTab') is wrong.
- scripts/link_probe.py:147-155 builds its own options WITHOUT allowed_extractors. So the 2026-09-22 'share links work' verification (commit c8ac29a) tested a path the app cannot take.

Direction for a fix (untested):
- Add 'facebook:reel' to the allowlist.
- Expand share/fb.watch links with a bounded, hop-by-hop redirect follower that checks every hop with allowed_link_host(), instead of enabling 'generic'.
- Make link_probe.py import _base_opts().

Sources: C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/providers/links.py · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/link_probe.py · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/.venv/Lib/site-packages/yt_dlp/YoutubeDL.py · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/.venv/Lib/site-packages/yt_dlp/utils/_utils.py

### F10. On a blocked cloud IP, the app would tell users that public posts are login-gated. This hides the outage from users and from the owner.
*Confidence: high*

Checked offline with app.providers.links._classified():
- YouTube's bot-check message contains 'cookies', so kind='gated': 'That post needs a login to view, so it can't be checked. Only public posts work.'
- Instagram's 'redirected to the login page… exceeded the rate-limit for accessing posts anonymously' and 'rate-limit reached or login required' also map to 'gated'.
- Facebook's 'Cannot parse data' after the anonymous view limit maps to the 'removed or login-only' message.
- Only YouTube's 'This content isn't available, try again later' maps to 'network'.

The raw message is printed server-side only.

Suggested change: a distinct kind (e.g. 'blocked') when the message contains 'not a bot', 'exceeded the rate-limit' or 'rate-limit reached', plus a dashboard counter or alert, so a degraded exit IP gets noticed.

Sources: C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/providers/links.py

### F11. The app's caption choice (manual, YouTube '-orig', Facebook '_FB') already avoids YouTube's subtitle 429 problem. The official YouTube API cannot replace scraped captions for third-party videos, though it can supply title and description from any IP.
*Confidence: high*

Subtitles:
- Open issue #13831 (bold in known issues). bashonly, 2026-01-06: 'Manual subtitles and original language automatic captions are not affected by this HTTP Error 429 issue. Only subtitles/captions that have been automatically translated into another language are affected.'

Official YouTube Data API v3:
- captions.download 'requires the user to have permission to edit the video' (OAuth; 200 units; page updated 2026-09-15).
- videos.list costs '1 unit', returns snippet.title and snippet.description, and needs only an API key for public data.
- Default quota is 10,000 units/day (getting-started page updated 2026-09-14).

This gives a ToS-clean, IP-independent partial fallback for YouTube text, with no captions and no audio.

Sources: https://github.com/yt-dlp/yt-dlp/issues/13831 · https://developers.google.com/youtube/v3/docs/captions/download · https://developers.google.com/youtube/v3/docs/videos/list · https://developers.google.com/youtube/v3/getting-started

### F12. Facebook enforces a per-IP anonymous view limit and then forces login. Its extractor also breaks often regardless of IP. No 2025-2026 datacenter-specific Facebook evidence was found.
*Confidence: medium*

- MEMBER bashonly, #16621 (2026-05-03, a residential user who failed 20 of 140 reels): 'you have probably exceeded the rate-limit for anonymous access. Facebook only lets you view so many posts before they force you to log in.'
- #16482 (2026-04): login-gated reels surface only as the generic 'Cannot parse data', because Facebook itself shows 'a technical error'.
- Older but still-open #15161 (2025-11): some videos need `--impersonate`.
- Expect Facebook on cloud IPs to be no better than Instagram. This is an inference, not a measurement.

Sources: https://github.com/yt-dlp/yt-dlp/issues/16621 · https://github.com/yt-dlp/yt-dlp/issues/16482 · https://github.com/yt-dlp/yt-dlp/issues/15161 · https://github.com/yt-dlp/yt-dlp/issues/17720

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| Move as-is: anonymous yt-dlp from the cloud host's own IP | $0 extra | Not acceptable for a core feature. YouTube links are likely to fail outright on a flagged IP; Instagram and Facebook degrade under per-IP anonymous limits; every failure shows users 'needs a login'. | No code change; Some datacenter IPs work some of the time (#15573 regular videos on an AWS-range VPS; #17376 'cleaner GCP IP works more often'; cobalt #1463 Instagram videos from GCP) | Per-IP and changes over time; maintainers: YouTube 'regularly blocks or restrict datacenter IPs' (2026-01-15); The bot wall blocks the metadata request, so captions and audio are lost too; Shared PaaS outbound IPs (Render/Railway/Fly) pool reputation with other tenants (inference); Misclassified as 'gated', so the outage is invisible |
| PO-token provider plugin (bgutil-ytdlp-pot-provider 2.0.2) | $0 in fees; one extra always-on Node ≥22 / Deno ≥2 process (or a Docker container) | Optional preventive measure for YouTube downloads only; does not solve the cloud problem | Free; the PO Token Guide says a yt-dlp maintainer maintains it; May lower the chance of an IP getting flagged ('may work as a preventative measure', bashonly 2026-05-21) | 'PO tokens are not a solution if your IP is already blocked' (#16773); README: 'does not bypass IP-based login restrictions'; YouTube only; no help for Instagram or Facebook; The app's metadata path needs no PO token (only GVS and Subs do), so it doesn't touch the failing request; Broke in August 2026 (#17368: 'Disable the plugin and use default player clients'); one more component to keep updated |
| Cookies from throwaway accounts (YouTube / Instagram / Facebook) | $0 in fees; recurring manual time to re-export cookies | Emergency stopgap only | Often restores YouTube on a flagged IP (bgutil README); Logged-in Instagram access is not subject to the anonymous cloud-IP limits (instaloader docs) | Documented ban risk on all three platforms (yt-dlp wiki; #3766; Instagram 2026-06-29; Facebook 2026-05-03); a fresh Google account was 'quickly banned' (#16147); Cookie-specific breakage (#16212, March 2026); switches YouTube to authed clients that need Deno and PO tokens; No cookies-from-browser on a headless server, so manual exports; Ties a privacy-sensitive service to an account identity |
| Pay-as-you-go residential proxy for link traffic only (one sticky session per check, 2–3 retries on fresh sessions) | About $0.15–1.10/month at the 5/day cap (≤150 link checks × ~1 MB). One-off top-ups: DataImpulse $5 for 5 GB (never expires); IPRoyal $7.35 for 1 GB (never expires); Decodo $4 + VAT per GB. Worst case ≤$0.03–0.18 per check (25 MB cap). | Cheapest reliable fix if link checks must work 24/7 | Residential exits avoid datacenter scoring; covers YouTube, Instagram and Facebook; One configuration point: yt-dlp `proxy` in _base_opts() plus an httpx proxy in subtitle_text(); Bandwidth is tiny (measured 0.25–0.34 MB per resolve); A Decodo residential SOCKS5 proxy fixed YouTube from a datacenter server (dev.to, March 2026) | Bright Data closed to individuals for new residential zones since 2026-07-07 (KYC, businesses only); Decodo's 'Streaming' category is locked until ID verification (YouTube not named); IPRoyal restricts unverified accounts; Some exits are challenged anyway (vendor claim: about 1 in 4 fresh exits, August 2026), so retries are needed; Resolve and download must share the exit IP (IP-bound googlevideo URLs); A new paid seam: under CLAUDE.md it needs a fake in scripts/fake_stages.py, its credential neutralized where it is read, and a GB budget; Whether these vendors accept Indian cards is unverified |
| Route link resolution through the home PC (per-app proxy over Tailscale, or an outbound long-poll 'link agent') | $0 (Tailscale Personal plan free: 6 users, unlimited user devices); about 1 MB of home bandwidth per link check | Free fix when the PC is usually on; best as primary with the paid proxy as fallback | Keeps the exact residential IP class that has worked since 2026-07-28 (re-measured 2026-10-15); No vendor, KYC or per-GB bill; Tailscale traverses CGNAT; the long-poll design exposes nothing at home and reuses the Telegram bot's pattern; Same exit for resolve and download by construction | Availability equals PC plus home internet uptime; links fail when it's off (needs a clear user message); Do not use a whole-VM exit node: it would route all traffic through home; On PaaS without /dev/net/tun, userspace mode is needed, and exit-node behavior there is undocumented; More moving parts than a single proxy URL |
| IPv6 rotation within a /64 | $0 extra on a VPS that routes a /64 (e.g. Hetzner-style); not available on typical PaaS | Not reliable in 2026 | No per-GB cost | An Invidious operator (2026-08-29) dropped from about 30 to about 10 videos before multi-hour blocks and suspects /64-wide blocks; Vendor blog (2026-09-07): 'YouTube scores a whole /64 as one unit'; No evidence for Instagram or Facebook; needs extra tooling |
| Keep yt-dlp current, and ship Deno plus curl_cffi in the image | $0 (maintenance time: stable releases roughly monthly, latest 2026.08.19; occasionally nightly) | Mandatory for every option; not a fix for IP blocks | Needed for YouTube JS challenges (since 2025.11.12) and Instagram's impersonated path (2026.07.04 rework); Facebook parser fixes land frequently (patch posted 2026-10-01 for #17720) | Does not change IP reputation; Fixes sometimes sit in nightly or master for weeks; every upgrade needs a re-probe (using the app's own options) |
| Official-API text fallback (YouTube Data API videos.list; Instagram oEmbed) | $0 (YouTube: 1 unit per call of a 10,000-unit/day default quota; API key only) | Partial fallback only: lets a blocked check still read the post's text | Works from any IP and is ToS-clean; YouTube title and description (snippet) need only an API key; Instagram oEmbed supports Reels, 1,000 requests/hour | captions.download requires edit permission on the video, so no third-party captions; no audio; Instagram oEmbed access requirements and whether it returns caption text are unverified; Facebook not covered; Adds a Google API key and a second code path |

## Recommendation (the researcher's)

If the app moves to a cloud host, don't let it fetch links anonymously from the cloud IP. YouTube is the most likely to break completely, because the bot wall blocks the metadata request itself. Instagram and Facebook will fail intermittently under per-IP anonymous limits. Users would be told that public posts need a login.

These don't fix it:
- a PO-token plugin
- updating yt-dlp
- IPv6 rotation

Throwaway-account cookies replace the problem with a documented account-ban risk.

The cheapest reliable fix is to send only link traffic out of a residential IP. That means the yt-dlp resolve, the subtitle fetch and the capped audio download, all through one exit per check, because googlevideo URLs are tied to the IP that resolved them.

**If link checks must work 24/7:** use a pay-as-you-go residential proxy with never-expiring traffic and sticky sessions, retrying up to 2–3 fresh sessions.
- DataImpulse: a one-off $5 for 5 GB.
- IPRoyal: $7.35 for 1 GB.
- Skip Bright Data, which no longer approves individuals.
- Ask Decodo whether YouTube falls in its locked "Streaming" category.

At the 5-checks/day cap that is about $0.15–1 a month, with the worst case bounded by the existing 25 MB cap.

**If links may pause while the PC is off:** route through the home PC for $0. Use either a per-app proxy over Tailscale, or an outbound long-poll link agent like the Telegram bot. Keep the proxy as the fallback.

Whichever you choose:
1. Ship Deno and curl_cffi in the image and keep yt-dlp current.
2. Add a distinct "the platform blocked this server" error kind and counter instead of today's "needs a login".
3. Treat the proxy as a paid seam: a fake in scripts/fake_stages.py, its credential neutralized where it is read, and a GB budget.
4. Before cutover, run the free metadata probe from the candidate host once a day for a week. Make link_probe.py use the app's own _base_opts() first, because today it skips the extractor allowlist and over-reports success.

Separately, fix the allowlist now, whatever you decide about hosting. Facebook /reel/, share/r/ and fb.watch links currently fail in the app.

## Unknowns

- Whether the specific candidate host's IP (including Indian regions such as AWS ap-south-1 or Oracle Mumbai/Hyderabad) is currently flagged by YouTube, Instagram or Facebook. Blocks are per-IP and change over time; only a probe from that host, repeated over days, can tell.
- Whether yt-dlp 2026.08.19's no-JS-runtime default client (visionos) is any more or less tolerated on datacenter IPs than android_vr or web. The only 2026 VPS log seen (#16221) used android_vr.
- There is no 2025-2026 primary measurement of anonymous Instagram or Facebook extraction from a datacenter IP, only documentation (instaloader), extractor error text and anecdotes, including a counter-example where Instagram videos worked from GCP.
- Whether residential proxy vendors put YouTube, Instagram or Facebook behind KYC or category blocks. Decodo's 'Streaming' category doesn't name YouTube; IPRoyal publishes no list for unverified accounts. Also unknown: whether Decodo's pay-as-you-go traffic expires, and whether each vendor accepts Indian cards for USD one-off top-ups.
- The real YouTube success rate through residential exits: the only figure is a vendor's self-reported 'about 1 in 4 fresh exits challenged on first contact' (August 2026, fleet type unspecified).
- Whether Tailscale's userspace-networking SOCKS5/HTTP proxy can send traffic out through an exit node. The doc (validated 2025-11-12) is silent, and this matters only for PaaS hosts without /dev/net/tun.
- Whether setting ignore_no_formats_error would still let yt-dlp return the title or description from the watch page on a bot-checked IP. The code path raises through raise_no_formats, but this is untested.
- Instagram oEmbed (Graph API v25.0) access requirements (Meta app or App Review), and whether its response still carries the caption text.
- How Facebook share/r/ and fb.watch links redirect for logged-out clients today. A safe fix to the allowlist bug depends on this; it was not tested here.
- Per-check bandwidth with Deno installed on a server: the web client also downloads YouTube's player JS (about 1–3 MB) whenever the cache is cold or the player rotates. This was not measured, since the local venv has no JS runtime.

## Verifier on the recommendation

The recommendation mostly follows from the evidence. Each of its supporting claims holds against primary 2026 sources:\n- Do not fetch anonymously from a cloud IP.\n- PO tokens, updating yt-dlp and IPv6 rotation do not unblock an IP.\n- Cookies carry ban risk.\n- A residential exit is the reliable fix, with the same exit for resolve and download.\n\nFive gaps or overstatements:\n1. The cost line '$0.15–1/month at the 5/day cap, worst case bounded by the 25 MB cap' does not hold for a proxy. Failed resolves refund the daily slot (routes.py _quota), so blocked or bad links send traffic through the proxy without counting against the cap. Before a proxy goes in, it needs its own byte or request budget, enforced before spending, as Invariant 5 requires.\n2. The question only matters for deployment shape C. Shape H (this PC behind the named Cloudflare tunnel, already one of the two options in HANDOFF.md) keeps the residential IP with zero changes. The recommendation should say so plainly: keep link resolution at home, or host at home.\n3. 'Fix the allowlist now' is already done in commit ca76538. What remains:\n   - restart any running server or bot\n   - probe a real /reel/ and share link once, free\n   - update the stale PROJECT_PLAN §0a text\n4. Any proxy must also cover the new expand_share_link httpx requests, not only yt-dlp and subtitle_text.\n5. Bright Data being closed to individuals is confirmed. The Indian-card unknown is partly resolved: IPRoyal accepts PayPal.

## Verifier: missed

- Failed or blocked link resolves REFUND the daily slot (app/api/routes.py _quota and verify_link), so a residential proxy's traffic is not bounded by the 5/day cap. Each refused resolve still moves ~0.25–0.34 MB, bounded only by the in-memory per-IP limiter. The proxy needs its own enforced byte budget before it can be a paid seam.
- The Facebook allowlist bug was fixed and committed (ca76538, 2026-10-15 21:58 +0530) by another session while this verification ran. A server or Telegram bot process started earlier keeps the old behaviour until restarted. PROJECT_PLAN.md §0a still claims 'fb.watch short links included' and '/reel/ allowlisted but untested'.
- The new expand_share_link makes its own direct httpx requests to facebook.com and fb.watch. Any proxy or home-exit design must route these too, alongside yt-dlp and subtitle_text, or share links will be expanded from the datacenter IP.
- Shape H (the home PC behind the named Cloudflare tunnel) avoids the whole problem at $0 with no code change. The report treats home routing only as an add-on to a cloud host.
- Instagram now effectively needs curl_cffi on any server. bashonly, 2026-06-29: 'The site blocks anonymous API requests that do not have a browser fingerprint.' The home PC's fallback without curl_cffi working is not evidence it will work from a cloud IP.
- On an ephemeral PaaS disk, yt-dlp's player-JS cache (needed once Deno is installed) is lost on every restart. That adds 1–3 MB of unmeasured, possibly proxied traffic per cold start.
- Not researched: whether the proxy vendors' acceptable-use terms allow YouTube, Instagram and Facebook targets for a public service, and the platforms' own terms on automated access through residential proxies.
- Environment discrepancy: Docker Desktop and the Google Cloud SDK are on this PC's PATH, although CLAUDE.md says Docker is not installed. This matters for the 'ship Deno + curl_cffi in an image' step and suggests GCP may be the candidate host.

