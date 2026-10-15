# Budget, per-person limits and a bot shield for strangers

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: 0 of 1 verifier(s) finished; the rest are still running or died (usage limit / network) - treat the unverified parts as unverified.** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

Strangers can use this paid service safely if three things are true. First, the money ceiling has to live outside the app as well as inside it: a dedicated Anthropic workspace with a monthly spend limit, prepaid credits with auto-reload off, and a small prepaid Sarvam balance. Second, the app's count cap should become a dollar budget: each check reserves its worst case, settles at what it actually cost, and runs a cheaper mode (no open-web pass) as the day's budget runs low. Third, per-person quotas should key on real identities: a signed device cookie that is only issued after Cloudflare Turnstile, Google Sign-In for more checks, the Telegram user id, and the WhatsApp phone number. IP limits stay, but only as a loose abuse brake.

Key facts checked on 2026-10-15:
- Turnstile is free with unlimited verifications (page updated 2026-08-14). Its token is single-use and valid for 300 s (page updated 2026-09-16).
- Anthropic's Start tier has a $500/month cap. Sonnet 5 limits there are 1,000 RPM, 2M ITPM and 400k OTPM, and cache reads do not count toward ITPM. So tens of checks a day cannot hit rate limits, unless the account is still in the lower, unpublished Evaluation tier.
- India is 77.7% IPv6-capable, and Jio is 94.5%. Per-/64 limits therefore work for most mobile users, but only if the site is reachable over IPv6.
- Meta's WhatsApp terms (§4.7, last modified 2026-09-23) bar LLM and general-purpose AI-assistant providers when AI is the primary functionality, and India is not one of the markets where they are allowed for a fee. Before building, the WhatsApp bot needs a policy read (or a BSP's opinion) that a narrow fact-check service is permitted.

At the given mix the average check costs about $0.066: $1/day buys about 15 checks, $2 about 30, $5 about 75. A day of all-fresh rumours (about $0.117 a check) halves that. Translating Hindi queries, or dropping the open-web pass when the budget is low, raises it by about 35-45%.

## Findings

### F1. Anthropic hard backstops: Start/Build/Scale tiers have monthly spend caps of $500 / $1,000 / $200,000. The owner can set a lower limit for the organization and for each workspace (but not for the default workspace). Billing is prepaid credits, with optional auto-reload.
*Confidence: high — **decision-critical***

platform.claude.com/docs/en/api/rate-limits (fetched 2026-10-15). Hitting the TIER cap: HTTP 429 rate_limit_error with error.details.error_code='enforced_spend_limit_reached' and no retry-after; usage stops until 00:00 UTC on the 1st of next month. Hitting a limit YOU set: HTTP 400 invalid_request_error, message starting 'You have reached your specified API usage limits' (or '...specified workspace API usage limits'). The app must map BOTH to a 'back tomorrow/back later' page and refund the slot, not show a generic error. Workspaces can also carry their own RPM/ITPM/OTPM limits. support.claude.com article 8977456 ('updated in the last hour', 2026-10-15): API usage is prepaid. When credits run out, the API stops working until topped up. Auto-reload has a trigger balance and a reload-to balance you choose. Purchased credits expire 1 year after purchase and are non-refundable. Failed requests are not charged, but a request already on track to succeed is charged even if the client disconnects. The console limits are MONTHLY only, so the daily guard has to be the app's own. Recommendation: put the public deployment's key in its own workspace with a monthly limit of about 30x the daily budget, turn auto-reload OFF, and keep about $10-20 of credit as the hard floor.

Sources: https://platform.claude.com/docs/en/api/rate-limits · https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-api-usage

### F2. Sonnet 5 rate limits are per-model buckets: Start tier 1,000 RPM / 2,000,000 ITPM / 400,000 OTPM, Build tier 5,000 / 5M / 1M. cache_read_input_tokens do NOT count toward ITPM for any model except Claude Haiku 3.5. New organizations may start in an 'Evaluation tier' whose limits are below these and are not published.
*Confidence: high — **decision-critical***

Only input_tokens (after the last cache breakpoint) plus cache_creation_input_tokens count. A burst is therefore bounded by uncached setup, about 8,000 tokens per pass. Even if every token of the 180k-cache-token open-web pass counted, 2M ITPM would allow about 11 such passes per minute. At tens of checks a day there is no realistic burst problem on Start tier. Two risks remain: (a) the unpublished Evaluation-tier limits for a young organization; (b) 'acceleration limits' on a sharp jump in usage. The limits are enforced as a token bucket, so short bursts can 429 below the per-minute number. A global in-flight cap of about 3 concurrent checks keeps this well clear. The owner should read the org's actual tier at platform.claude.com/usage/limits.

Sources: https://platform.claude.com/docs/en/api/rate-limits

### F3. Cloudflare Turnstile Free plan: $0, unlimited challenge and siteverify requests, up to 20 widgets per account, 10 hostnames per widget, 7-day analytics, pre-clearance included. A token is valid for 300 s and can be validated once; a replay or an expired token returns 'timeout-or-duplicate'.
*Confidence: high — **decision-critical***

Plans page last updated 2026-08-14. Server-side validation page last updated 2026-09-16: POST https://challenges.cloudflare.com/turnstile/v0/siteverify, form or JSON, with required secret and response and optional remoteip and idempotency_key (a UUID for safe retries). Tokens are at most 2,048 characters. No siteverify rate limit is stated. Neither fetched page says the site must be proxied by Cloudflare. That Turnstile works on any site without proxying is Cloudflare's long-standing positioning, but I did not re-fetch it this session. Mobile webviews (mobile-implementation docs, previews dated 2026-08-27): need JavaScript and DOM storage enabled, must reach challenges.cloudflare.com, and must allow about:blank and about:srcdoc. A user agent that changes mid-session fails the challenge. Implications: siteverify must run BEFORE limits.claim(), and a failed verification must never consume a slot. WhatsApp and Instagram in-app browsers are third-party webviews you cannot configure, so show an 'open in Chrome' fallback on failure. reCAPTCHA (now 'part of Google Cloud Fraud Defense', page updated 2026-10-13): Essentials is free for up to 10,000 assessments a month per organization but needs a Google Cloud billing instrument; Premium is an $8 flat fee for 10,001-100,000, then $1 per 1,000. hCaptcha: Basic is free, and passive mode is listed only on Pro at $139/month (or $99/month billed yearly); the pricing page is undated (©2025).

Sources: https://developers.cloudflare.com/turnstile/plans/ · https://developers.cloudflare.com/turnstile/get-started/server-side-validation/ · https://developers.cloudflare.com/turnstile/get-started/mobile-implementation · https://docs.cloud.google.com/recaptcha/docs/compare-tiers · https://www.hcaptcha.com/pricing

### F4. Meta's WhatsApp Business Platform terms §4.7 (page 'Last Modified: September 23, 2026') strictly prohibit 'providers and developers' of LLMs, generative-AI platforms and general-purpose AI assistants from using the platform when those technologies are the PRIMARY (not incidental or ancillary) functionality, and Meta decides what counts as primary. The paid exception for AI Providers covers only listed markets (Italy, Brazil, EU/EEA), and India (+91) is not listed.
*Confidence: medium — **decision-critical***

The AI-Providers pricing page (markets 'updated as of May 12, 2026') lists Italy from 2026-02-16 to 2026-05-12, Brazil from 2026-03-11 with no end date, and the EU/EEA countries from 2026-03-11 to 2026-05-12. India is absent. A WhatsApp claim-verifier bot whose replies are LLM-generated could be judged an AI-primary service. It is narrow, not general-purpose, but nothing found settles whether that is enough. The terms do allow a business to 'retain an AI Provider as your Solution Provider', provided WhatsApp data is not used to train or improve AI models (fine-tuning a model for the business's exclusive use is allowed). This is a go/no-go risk for the WhatsApp phase. The bot should be framed and built as a fact-check service, and a BSP's or Meta's confirmation is needed before investing in it.

Sources: https://www.facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform · https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers.md

### F5. WhatsApp has used per-message pricing since 2025-07-01. Non-template messages sent inside the 24-hour customer-service window opened by the user are free. The India authentication-template rate is about ₹0.115 (about $0.0014) per delivered message, per third-party 2026 rate summaries; Meta's own rate card was not readable.
*Confidence: medium*

Meta pricing docs: India's marketing rate went up on 2026-01-01 (to ₹0.8631 per secondary sources), and India's authentication-international rate went up on 2026-04-01. India can bill in INR from 2026-01-01; WABAs must migrate to INR by 2026-12-31, and from 2027-01-01 Meta stops delivering messages from non-INR WABAs for eligible Indian customers. A bot that only replies to user-initiated messages within 24 h pays Meta $0 per reply (BSP markups aside), so the check cost dominates. CONFLICT: a Zoho community post (updated 2026-10-05) says utility TEMPLATES sent inside the window became chargeable on 2026-10-01, while Meta's fetched page still says they are free. This does not affect plain non-template replies. The WhatsApp phone number serves as a free per-person quota key.

Sources: https://developers.facebook.com/docs/whatsapp/pricing/ · https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing.md · https://help.zoho.com/portal/en/community/topic/whatsapp-message-pricing-changes-effective-october-1-2026 · https://hyperleap.ai/whatsapp-pricing-calculator-india · https://montymobile.com/blogs/whatsapp-business-api-pricing-in-india-inr-rates-gst-and-the-2026-currency-migration-deadline

### F6. India is now mostly IPv6. APNIC measures India at 77.68% IPv6-capable and 75.23% preferred (2026-10-11), Reliance Jio AS55836 at 94.47% capable and 91.19% preferred (2026-10-14), and Airtel AS45609 at about 90.5% capable (2026-04-03, the latest row read). Per-IPv6-prefix limits therefore identify most mobile users, but only if the site is reachable over IPv6.
*Confidence: high — **decision-critical***

If the host or tunnel publishes no AAAA record, Jio and Airtel users reach the site over shared IPv4 via CGNAT or NAT64. Cloudflare's CGNAT paper (2025-10-29) says one CGNAT IPv4 address can represent 'hundreds or even thousands of users'. It puts South Asia among the regions with the highest user-to-IP ratios and reports that CGNAT IPs are rate-limited about 3x more often despite mostly-human bot scores. It gives no India-specific number. Granularity: a 3GPP mobile handset gets its own /64, while fixed broadband delegates /56 to /64 (operator-dependent; not verified this session). Key per-person IPv6 limits on the /64, add a looser aggregate per /56, and treat each IPv4 as shared. Vodafone Idea is unknown: AS55410 had only 189 samples, so it is not representative. CODE NOTE: limits.py keys on request.client.host. Behind cloudflared, uvicorn's default proxy handling trusts X-Forwarded-For only from 127.0.0.1. On a cloud host behind another proxy or load balancer, client.host becomes the proxy's IP, so all visitors share one bucket, unless forwarded_allow_ips is set to exactly that proxy. Trusting it broadly makes the header spoofable.

Sources: https://data1.labs.apnic.net/v6stats/v6economy/IN.json · https://stats.labs.apnic.net/cgi-bin/json-table-v6.pl?x=IN55836 · https://stats.labs.apnic.net/cgi-bin/json-table-v6.pl?x=IN45609 · https://blog.cloudflare.com/detecting-cgn-to-reduce-collateral-damage/

### F7. At the given mix (10% repeats at $0, 30% shortcut at $0.0084, 30% covered at $0.055, 20% open web at $0.16, 10% reels at $0.15) the expected cost is $0.066 per check: $1/day buys about 15 checks, $2 about 30, $5 about 75.
*Confidence: high — **decision-critical***

Arithmetic: 0.3×0.0084=0.00252, 0.3×0.055=0.0165, 0.2×0.16=0.032, 0.1×0.15=0.015, total $0.0660. Sensitivity: (a) An all-fresh-rumour day (0% repeats, 0% shortcut, 40% covered, 50% open web, 10% reels) costs $0.117 a check: $1 buys about 8, $2 about 17, $5 about 42. (b) The worst case of every check an open-web pass at $0.17 gives 5.9 / 11.8 / 29. Reels at $0.26 each give 3.8 / 7.7 / 19. (c) Translating Hindi queries, assuming the shortcut share rises from 30% to 45% and covered and open web fall to 25% and 10%, costs $0.0485 a check: 20.6 / 41 / 103. (d) The degraded mode (skip the open-web pass, so those checks cost about $0.055) at the base mix costs $0.045 a check: 22 / 44 / 111. Because the per-check cost varies 20x, a count cap does not bound spend. The guard should reserve a worst-case dollar estimate per input kind before spending (text about $0.20, link or reel about $0.30) and settle at answer.usage. ASR adds about ₹0.58 per 70 s, once per video.

Sources: computed from the task's measured costs; CLAUDE.md money rules

### F8. SMS OTP in India costs about as much as a check itself: Firebase Phone Auth is about $0.07 per SMS to India (Blaze plan, every send billed; secondary sources dated Aug 2026), and MSG91 is about ₹0.15-0.25 per OTP plus DLT registration. SMS OTP is a poor identity layer for a service whose average check costs $0.066.
*Confidence: medium*

Google's Identity Platform pricing page would not render, so the India row is unverified. Logto and Authgear list $0.07 for India. Phone auth has needed the Blaze (billing) plan since Sept 2024, and Logto reports a 3,000 SMS/day cap without Identity Platform. A May 2026 Firebase 'Phone Number Verification' (carrier-based, no OTP) is reported but priced separately and only on supported carriers; unverified. MSG91 costs about ₹0.15 (Botble docs, Message Central May 2026) to ₹0.18-0.25 (Authgear Aug 2026), plus DLT registration and sender-ID setup that can add 30-50% to the all-in cost. A WhatsApp authentication template is about ₹0.115 and needs a WABA. A user already on WhatsApp can simply use the bot, where the phone number is free identity. Telegram accounts are also phone-verified, so the Telegram user id is a strong free key.

Sources: https://www.authgear.com/post/best-otp-service-providers/ · https://blog.logto.io/firebase-authentication-pricing · https://www.messagecentral.com/blog/sms-otp-pricing-india · https://docs.botble.com/sms-gateways/drivers/msg91.html

### F9. Sarvam is prepaid: ₹100 free credit on signup, credits never expire, and requests error once credits are gone. Rate limits are per account: Speech-to-Text REST is 60 req/min on Starter (pay-as-you-go), 100 on Pro (₹10,000), 4,000 on Business (₹50,000).
*Confidence: medium*

docs.sarvam.ai/api-reference-docs/ratelimits (no date visible). Over the limit returns 429, and 503 can occur under load; retry with backoff. No spend alerts or controls are documented, so the prepaid balance itself is the backstop. Keep it small (for example ₹300-500; at about ₹0.58 per 70 s, ₹500 is about 14 hours of audio) and alert on low balance. The app's 300 s media cap and the per-video transcript cache already bound each check. At about 10 chunk requests per 5-minute clip, 60/min Starter allows about 6 long clips a minute, which is ample.

Sources: https://docs.sarvam.ai/api-reference-docs/ratelimits

### F10. Google Fact Check Tools API (claims:search) is free, but its default quota was not found in public docs. It is tied to the API key's Cloud project and visible on the project's Quotas page.
*Confidence: low*

The discovery doc shows quotaUser and per-key quota attribution, but no number. The owner can read it free in Cloud Console > APIs > Fact Check Tools > Quotas. At tens of checks a day this is almost certainly not binding, but if translation adds a second lookup per check, calls double.

Sources: https://flutter.googlesource.com/third_party/googleapis.dart/+/refs/heads/master/discovery/googleapis_beta/factchecktools__v1alpha1.json · https://developers.google.com/fact-check/tools/api/terms

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| Anonymous signed device cookie + Cloudflare Turnstile (web baseline) | $0 (Turnstile Free has unlimited verifications) | Every web visitor, including rural Hindi users on low-end Android. There is no account and no typing, and the challenge is usually invisible in managed mode. | Zero friction and zero cost; Each new cookie costs a solved Turnstile challenge, so clearing cookies or using incognito no longer gives free checks without effort; Gives a per-device key that works behind CGNAT, where IP keys fail; The server signs the cookie (HMAC); it stores no personal data | Cookies are trivially reset; a determined abuser can solve challenges repeatedly (or pay solving farms), so it needs the IPv6 /64 and global-budget layers too; Turnstile can fail inside WhatsApp and Instagram in-app webviews you cannot configure; needs an 'open in Chrome' fallback; Token is single-use and valid 300 s; siteverify must run server-side before claim() |
| Google Sign-In (optional 'more checks' tier) | $0 | Android users, who nearly all have a Google account for the Play Store. One tap. Good for repeat users who want more than the anonymous quota. | Free; a stable per-person key (Google 'sub') that survives cookie resets; Creating many Google accounts usually needs phone verification, so it is costlier to abuse than cookies; No SMS cost | Adds an OAuth dependency and a privacy notice; you store a user id, which the project currently avoids; Some users fear 'login'; it must stay optional; Does not work for Telegram or WhatsApp users, who have their own ids |
| Messaging-platform identity (Telegram user id / WhatsApp phone number) | $0 for identity. WhatsApp non-template replies inside the 24 h window are free; an authentication template is about ₹0.115 if ever needed. | The users already reaching the service through the bots. Both platforms phone-verify accounts, so this is the strongest free per-person key. | Free, strong, and no extra step for the user; Per-person limits must live in the bot anyway: all Telegram traffic reaches the API as one client | WhatsApp: Meta Terms §4.7 (2026-09-23) bars AI-primary providers, and India is not an allowed AI-Provider market, so a policy check is needed before building; Phone numbers are personal data; store only a salted hash with a daily counter |
| Email magic links | $0 on free tiers. Resend and Brevo have small daily free allowances; their pricing pages were not re-verified this session. | Poor fit for rural Hindi-speaking phone users, who rarely use email; acceptable for urban or desktop users. | Free at this volume; No third-party login | High friction: leave the app, open mail, come back; deliverability problems; Disposable-email services make it weak against abuse; Adds a mail provider and a sending domain to configure |
| Phone OTP by SMS (Firebase/Identity Platform, MSG91, 2Factor) | About $0.07 per SMS (Firebase, India, secondary sources) or about ₹0.15-0.25 per OTP (MSG91) plus DLT registration; each OTP costs about as much as a whole check ($0.066 average) | Not recommended at this scale. The verification would cost as much as the service it gates. | Strong per-person identity; Familiar to Indian users (OTP is everywhere) | Per-send cost on every attempt, including OTPs never entered; the sender can be SMS-pumped, which is itself an abuse vector; DLT registration and sender-ID approval paperwork for MSG91 and 2Factor; Firebase needs the Blaze billing plan |
| reCAPTCHA (Google Cloud Fraud Defense) as the shield instead of Turnstile | $0 up to 10,000 assessments a month (Essentials), but needs a Google Cloud billing instrument; Premium is $8 flat for 10,001-100,000 | Workable, but adds a billing-linked Google Cloud project for no gain over Turnstile at this volume | Mature, with good Android coverage; Score-based (invisible) | Needs a billing instrument even for the free tier; what happens past 10k/month on Essentials is not stated; Heavier privacy footprint |
| hCaptcha | Basic $0; passive (invisible) mode only on Pro at $139/month or $99/month billed yearly | A fallback if Turnstile proves unreliable in Indian in-app webviews | Free tier available; Privacy-focused | Free tier lists no passive mode, so visible image puzzles fall on low-literacy users; Pricing page undated (©2025) |

## Recommendation (the researcher's)

Use a layered scheme. Each layer bounds a different failure, and every number below is a setting the owner can change.

L0, external hard backstops, outside the app's control:
- Create a dedicated Anthropic workspace for the public key, with a monthly spend limit of about 30x the daily budget (for example $45 for $1.50/day).
- Keep prepaid credits with auto-reload OFF and a balance of about $10-20. Credits expire after 1 year and are non-refundable, so buy small.
- Map both the 400 'specified ... usage limits' error and the 429 'enforced_spend_limit_reached' error to a calm 'back later' page, and refund the slot.
- Keep a small prepaid Sarvam balance of about ₹300-500, since Sarvam documents no spend controls.

L1, a global daily DOLLAR budget in SQLite, India's day. It replaces the count cap of 5:
- Before spending, reserve a worst-case estimate (text $0.20, link or reel $0.30) with the same conditional UPSERT, then settle to answer.usage when the check finishes.
- Start at $1.50/day, about 22 checks at the given mix and about 13 on a bad day.
- Degrade as it drains. Below 40% remaining, skip the open-web pass: answer from pass 1, or say plainly that no vetted fact-checker covered the claim (tier none, invariant 2). Below 15%, serve only cache hits and the $0.0084 fact-check shortcut. At 0, show 'back at midnight IST', and keep serving exact repeats free.

L2, per-person quotas:
- Web: 3 paid checks a day per signed device cookie, issued only after a Turnstile pass. Signing in with Google raises it to 10.
- Telegram: 5 a day per user id, enforced in the bot.
- WhatsApp: 5 a day per hashed phone number, enforced in the bot.
- No single identity may take more than 25% of the day's dollars.
- At most 1 check in flight per identity, and at most 3 globally, queued rather than refused. This also closes the hole where concurrent refunded link resolves hold every slot.

L3, network abuse brakes only (never the main per-person key):
- 5 a day per IPv6 /64, 15 a day per /56, and 20 a day per IPv4 address, because IPv4 is shared CGNAT.
- Publish an AAAA record (IPv6) so Jio and Airtel users (91-94% IPv6) get per-device /64s.
- Read the client IP only from the trusted proxy: set uvicorn forwarded_allow_ips to exactly the proxy, or use CF-Connecting-IP only when the request really comes from Cloudflare.

L4, Turnstile in managed mode on every paid web submission:
- Run siteverify (remoteip plus idempotency_key) before limits.claim().
- A failed verification never costs a slot.
- In WhatsApp and Instagram webviews, offer 'open in Chrome' on failure.

Also ship the Hindi-to-English translation for fact-check lookups. It moves traffic to the $0.0084 path and is worth about 35-45% more checks per dollar.

Do not use SMS OTP: each OTP costs about as much as a check. Before building the WhatsApp bot, get a written read of Meta Terms §4.7 on AI-primary services in India.

## Unknowns

- Whether Meta would treat an LLM-backed fact-check bot as an 'AI Provider' whose AI is its primary functionality (Terms §4.7). India is not an allowed AI-Provider market, and no source settles narrow-purpose services.
- Anthropic 'Evaluation tier' limits for new or young organizations are unpublished; the owner should read platform.claude.com/usage/limits for the real tier.
- The Google Fact Check Tools API default daily quota; check Cloud Console > Quotas.
- The official Firebase/Identity Platform SMS price for India; the page did not render, and $0.07 comes from secondary sources.
- Meta's official India authentication rate; ₹0.115 comes from third-party summaries. Also whether utility templates inside the window became chargeable on 2026-10-01 (Zoho says yes, Meta's page still says free).
- Vodafone Idea IPv6 share: the AS checked (AS55410) had too few samples. Airtel's latest row read is 2026-04-03, not October.
- India-specific CGNAT users-per-IPv4; Cloudflare gives only 'hundreds or even thousands' and regional ratios.
- Real-world Turnstile failure rate in WhatsApp and Instagram in-app webviews on low-end Android; needs a field test with a few real phones.
- Whether Turnstile's 'no Cloudflare proxy required' is still stated in 2026 docs; it is long-standing, but not re-fetched this session.
- How established free AI-tool sites set their budgets (dollar caps, degrading to cheaper models): not researched in this pass because of the call budget. The L1 degrade design is reasoned from this project's own cost tiers, not copied from a cited practice.
- Resend and Brevo free-tier email limits were not re-verified this session.

