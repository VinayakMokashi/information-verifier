# Verification of limits-budget.md

status: complete (2026-10-15)

Verifier: adversarial verification agent, started 2026-10-15. Target:
`docs/research/2026-10-15/limits-budget.md` ("Budget, per-person limits and a
bot shield for strangers"). Method: try to REFUTE each decision-critical
finding, and every price, quota, rate limit or arithmetic a recommendation
rests on, against primary sources fetched fresh on 2026-10-15. Verdicts:
confirmed / corrected / refuted / uncertain (uncertain is preferred to
confirming on secondary reports). Verdicts are appended as they are reached,
so a partial file is still usable. $0 spent; no paid API was called.

## Verdict index

| Finding | Verdict | One-line correction or note |
|---|---|---|
| F1 Anthropic spend caps / user limits / prepaid credits | confirmed | Reloads are "plus applicable taxes"; auto-reload default undocumented |
| F2 Sonnet 5 rate limits, cache reads, Evaluation tier | confirmed | Evaluation tier's spend cap is unpublished too |
| F3 Turnstile Free plan, 300 s single-use token | confirmed | "No Cloudflare proxy needed" is now confirmed (2026-08-14) |
| F4 Meta terms §4.7 text (2026-09-23) | confirmed | The terms name no fee, only "certain countries" |
| F4b AI-Provider markets | corrected | Live only in Brazil; Italy and EU/EEA ended 2026-05-12; India absent |
| F5 WhatsApp per-message pricing | confirmed | ₹0.115 India auth rate uncertain (secondary only) |
| F6 India 77.68% / Jio 94.47% IPv6, CGNAT paper | confirmed | Airtel is 87.9-90.0% (Oct 2026), not ~90.5%; a /64 is per connection |
| F7 $0.066/check; $1/$2/$5 = 15/30/75 | confirmed | Range is +36-47%, not 35-45%; the $0.26 reel and (c)'s shift are assumptions |
| F8 SMS OTP "costs about as much as a check" | corrected | True only for Firebase (~$0.07, unverified); MSG91 is ~5% of a check |
| F9 Sarvam prepaid, 60/100/4,000 req/min | confirmed | ₹500 is ~16.7 h of audio, not ~14 |
| F10 Fact Check API quota | uncertain | Not re-checked (not decision-critical) |
| L0 error mapping | corrected | Credit exhaustion (and 402) will hit first; map it too |

## Verdicts

### F1. Anthropic spend caps, user-set limits, prepaid credits - CONFIRMED (one addition)

- Verdict: **confirmed**. Every checkable detail matches the primary pages.
- Evidence (platform.claude.com/docs/en/api/rate-limits, fetched 2026-10-15; no
  page date shown): "Each of the Start, Build, and Scale tiers carries a monthly
  spend cap": Start $500, Build $1,000, Scale $200,000 (Custom: none). At the
  tier cap, "API usage pauses until 00:00 UTC on the first day of the next month,
  unless you request a higher limit sooner"; it returns HTTP 429 `rate_limit_error`
  with `error.details.error_code` = `enforced_spend_limit_reached` and "no
  `retry-after` header" ("Retrying, including the SDK's automatic retries, fails
  until access resumes"). A limit you set returns "HTTP 400 with error type
  `invalid_request_error`. The message begins `You have reached your specified
  API usage limits`, or `You have reached your specified workspace API usage
  limits`". "You can't set limits on the default Workspace." "You can set custom
  spend and rate limits per Workspace."
- Evidence (support.claude.com article 8977456, fetched 2026-10-15, "Updated in
  the last hour"): "billed through prepaid usage credits" (but "Some
  organizations are billed monthly in arrears"); "If you run out of credits, you
  can no longer call the API"; auto-reload has "When credit balance reaches" and
  "Bring credit balance back up to"; "Credits expire one year from the purchase
  date"; "All credit purchases are non-refundable"; "Failed requests aren't
  charged"; a request "on track to succeed" is "still charged" if the client
  disconnects. The article does NOT say whether auto-reload is on or off by
  default, so "turn auto-reload OFF" means "check it, do not assume".
- Addition the finding missed: the same article says reloads are charged "plus
  applicable taxes". See "Missed" (GST): the $ figures in this research are
  pre-tax.
- The "monthly only" point: the page defines spend limits as "a maximum monthly
  cost" and documents no daily spend limit, so the daily guard must be the
  app's own. Confirmed on that evidence.

### F2. Sonnet 5 rate limits, cache reads, Evaluation tier - CONFIRMED

- Verdict: **confirmed**.
- Evidence (platform.claude.com/docs/en/api/rate-limits, fetched 2026-10-15):
  Claude Sonnet 5 has its own bucket ("Claude Sonnet 5.5 and Claude Sonnet 5
  each have a separate rate limit"). Start tier 1,000 RPM / 2,000,000 ITPM /
  400,000 OTPM; Build 5,000 / 5,000,000 / 1,000,000; Scale 10,000 / 10,000,000
  / 2,000,000. "`cache_read_input_tokens` ... Do NOT count toward ITPM for most
  models"; only "Claude Haiku 3.5 ... also counts `cache_read_input_tokens`",
  and Haiku 3.5 is now "retired, except on Google Cloud". "New organizations
  and organizations with limited usage history may start in the Evaluation
  tier, with limits below the standard limits shown on this page" - no numbers
  are published, and the Evaluation tier is also absent from the spend-cap
  table. Acceleration limits ("if your organization has a sharp increase in
  usage") and the token bucket ("60 RPM might be enforced as 1 request per
  second") are both stated.
- Arithmetic check: 2,000,000 / 180,000 = 11.1 passes per minute. Confirmed.
- Note: workspace rate limits ("set per limiter type") are a free burn-RATE
  brake the recommendation does not use. See "Missed".

### F3. Cloudflare Turnstile Free plan and token rules - CONFIRMED; one unknown RESOLVED

- Verdict: **confirmed** (the Turnstile facts). The reCAPTCHA and hCaptcha
  prices were not re-checked: they are not decision-critical and the
  recommendation does not use them.
- Evidence (developers.cloudflare.com/turnstile/plans/, "Last updated: Aug 14,
  2026", fetched 2026-10-15): Free plan price "Free"; "Unlimited challenges
  (traffic or verification requests)": Yes; "Up to 20 widgets"; "10 hostnames
  per widget"; analytics "7 days maximum"; pre-clearance "Yes"; Ephemeral IDs
  "No" (Enterprise only).
- Evidence (.../turnstile/get-started/server-side-validation/, "Last updated:
  Sep 16, 2026"): POST https://challenges.cloudflare.com/turnstile/v0/siteverify,
  form or JSON; `secret` and `response` required, `remoteip` and
  `idempotency_key` ("A UUID you generate to safely retry validation requests")
  optional; tokens are valid for 300 s and "Tokens are single-use"; a replay is
  "rejected with the `timeout-or-duplicate` error code"; "Maximum length: 2048
  characters"; no siteverify rate limit is stated; "The client-side widget
  alone does not protect your forms".
- Unknown resolved: the plans page states "Turnstile can be used independently
  without requiring other Cloudflare services" (2026-08-14), so no Cloudflare
  proxy is required. That unknown can be closed.

### F7. Cost per check and what $1 / $2 / $5 a day buys - CONFIRMED arithmetic; three labels CORRECTED

- Verdict: **confirmed** for the base table. **Corrected** for the summary's
  "+35-45%" range and for the provenance of two sensitivity inputs.
- Recomputed independently (Python, 2026-10-15), mix 10% $0 / 30% $0.0084 /
  30% $0.055 / 20% $0.16 / 10% $0.15 (shares sum to 100%):

  | Scenario | $/check | $1/day | $1.50/day | $2/day | $5/day |
  |---|---|---|---|---|---|
  | Base mix | 0.06602 | 15.1 | 22.7 | 30.3 | 75.7 |
  | (a) all-fresh day (0/0/40/50/10) | 0.11700 | 8.5 | 12.8 | 17.1 | 42.7 |
  | (b) every check open-web at $0.17 | 0.17000 | 5.9 | 8.8 | 11.8 | 29.4 |
  | (b) every check a reel at $0.26 | 0.26000 | 3.8 | 5.8 | 7.7 | 19.2 |
  | (c) Hindi translation (10/45/25/10/10) | 0.04853 | 20.6 | 30.9 | 41.2 | 103.0 |
  | (d) degraded, open web costs $0.055 | 0.04502 | 22.2 | 33.3 | 44.4 | 111.1 |
  | (c)+(d) together | 0.03803 | 26.3 | 39.4 | 52.6 | 131.5 |

  Every figure the researcher gives matches to rounding ("about 8" is 8.5,
  rounded down). "$1.50/day = about 22 at the mix, about 13 on a bad day" =
  22.7 and 12.8: confirmed. "Varies 20x": $0.17 / $0.0084 = 20.2: confirmed.
- Correction 1 (summary line): translation raises checks per dollar by +36%
  and the degraded mode by **+47%**, so the range is "about 36-47%", not
  "35-45%". Both together: +74%.
- Correction 2 (provenance): the $0.26 reel in (b) is NOT a measurement. It is
  the pre-measurement estimate that PROJECT_PLAN §8 records as "The model said
  $0.16 and $0.26; reality came in 2-3x cheaper". Measured (§8): a 70 s reel,
  one pass, $0.082 + ₹0.58 ASR; the dearest text check measured, two passes,
  $0.1724 (295 s, pass 2 about $0.13 from 180k cache reads and ~16 filter
  rounds). (b) is fine as a pessimistic bound, but it should be labelled as one.
- Correction 3 (provenance): (c)'s shift from 30% to 45% shortcut share is an
  assumption. What was measured (§11 item 20, 2026-10-15) is that Google
  fact-check MATCHES go from 3/12 to 7/12 with a HAND translation, and "a match
  still needs the model's trusted="yes" to be kept". The production step is
  "one tiny call, or a cheap model" (§11 item 20), so it has its own small
  per-check cost, which (c) leaves out. The direction holds; the size is unproven.
- Useful split the finding did not show: at the base mix, open-web checks are
  20% of checks but **48.5% of the dollars**, reels 22.7%, covered 25.0%, and
  the shortcut 3.8%. Degrading the open-web pass is the single biggest lever.
- Reservation sizes (text $0.20, link $0.30): the $0.20 is only ~16% above the
  dearest measured text check ($0.1724), and nothing in the search budget
  bounds cache-read "filter rounds", so it is a margin, not a bound. That is
  fine because the check settles at `answer.usage` and the monthly console
  limit is the true backstop. But the doc should not call it "worst case".

### F4. Meta WhatsApp terms §4.7 (AI Providers) - text CONFIRMED (markets list: see F4b below)

- Verdict on the terms text: **confirmed**.
- Evidence (facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform,
  fetched 2026-10-15, "Last Modified: September 23, 2026"): §4.7 "Providers and
  developers of artificial intelligence or machine learning technologies,
  including but not limited to large language models ... are strictly
  prohibited from accessing or using the WhatsApp Business Platform, whether
  directly or indirectly, for the purposes of providing, delivering, offering,
  selling, or otherwise making available such technologies when such
  technologies are the primary (rather than incidental or ancillary)
  functionality being made available for use, as determined by Meta in its sole
  discretion." The exception reads that such technologies "may be made
  available to businesses in certain countries as set forth here", linking to
  developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers.
  "You may retain an AI Provider as your Solution Provider", but WhatsApp
  Business Platform Data may not be used "to create, develop, train, or improve
  any machine learning or artificial intelligence systems", except to
  "fine-tune an AI Model that is for your exclusive use". India is not named
  anywhere in the section.
- Small correction: the TERMS text names no fee. It says only "certain
  countries". The fee comes from the linked page being a pricing page (F4b).

### F6 (part 1). Cloudflare CGNAT paper - CONFIRMED

- Verdict: **confirmed**.
- Evidence (blog.cloudflare.com/detecting-cgn-to-reduce-collateral-damage/,
  datePublished 2025-10-29, fetched 2026-10-15): "a single IPv4 address may
  represent hundreds or even thousands of users"; "large portions of Africa and
  South Asia appear with the highest user-to-IP ratios"; "CGNAT IPs are subject
  to rate limiting three times more often than non-CGNAT IPs"; the mean bot
  score is lower for CGNAT (7%) than non-CGNAT (13.1%), with near-identical
  medians, read as "mostly human". No India-specific figure, and nothing on
  per-/64 limiting. All as the researcher said.

### F4b. AI-Provider markets (the paid exception) - CORRECTED (only Brazil is live)

- Verdict: **corrected**. The dates match, but the headline "covers only listed
  markets (Italy, Brazil, EU/EEA)" overstates the present. On 2026-10-15 the
  exception is live **only in Brazil**.
- Corrected statement: per Meta's AI-Providers page ("updated as of May 12,
  2026"), AI Providers may use the platform in **Brazil (+55)** from 2026-03-11
  with no end date. Italy "applied" from 2026-02-16 **until May 12, 2026**, and
  29 EU/EEA countries from 2026-03-11 **until May 12, 2026**, both in the past
  tense. India is absent. Where the exception applies, AI Providers are "only
  permitted to offer general-purpose AI assistants", and they pay per-message
  "AI Provider rates for non-template messages" (rates in a linked CSV, amounts
  not on the page), while other businesses' non-template messages in the window
  are free.
- Evidence: developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers
  (fetched 2026-10-15).
- Effect on the recommendation: none on the direction. Being an AI Provider in
  India means being barred outright, with no paid route. The go/no-go risk is
  real, and the researcher's call for a written read (BSP or Meta) before
  building the WhatsApp bot follows. Confidence "medium" is right: whether a
  narrow LLM-backed fact-check service is "AI as the primary functionality" is
  Meta's call ("in its sole discretion"), and no source settles it.

### F5. WhatsApp per-message pricing and the free service window - CONFIRMED; ₹0.115 UNCERTAIN

- Verdict: **confirmed** for the rules; **uncertain** for the ₹0.115 India
  authentication rate (still secondary-only; Meta keeps amounts in rate-card
  files this fetch could not read).
- Evidence (developers.facebook.com/docs/whatsapp/pricing/, fetched
  2026-10-15, no page date): "Effective July 1, 2025, Meta charges on a
  per-message basis"; "All non-template messages are free within an open
  customer service window"; "Utility templates delivered within an open
  customer service window are free". The page lists NO 2026-10-01 change to
  that rule. Its 2026-10-01 items are regional utility and authentication rate
  changes for specific markets, not India, so the Zoho claim stays
  unconfirmed. India rate events: 2026-01-01 "Higher marketing rate";
  2026-04-01 "Higher authentication-international rate". INR billing
  "launched on January 1, 2026"; WABAs "migrated to INR by December 31, 2026";
  "as of January 1, 2027 Meta will no longer deliver the messages of non-INR
  WABAs of eligible customers".
- Not decision-critical: replies inside the 24 h window are free either way,
  and F4 gates the whole WhatsApp channel anyway.

### F6 (part 2). India / Jio IPv6 shares - CONFIRMED (Airtel: see part 3)

- Verdict: **confirmed**, to the second decimal.
- Evidence: data1.labs.apnic.net/v6stats/v6economy/IN.json (tail, fetched
  2026-10-15): 2026-10-11 capable_pc 77.6821, preferred_pc 75.2271, seen
  3,331,105 (2026-10-10: 77.06 / 74.51; 2026-10-09: 76.80 / 74.56).
  stats.labs.apnic.net/cgi-bin/json-table-v6.pl?x=IN55836 (tail, fetched
  2026-10-15): Jio 2026-10-14 capable 94.4654, preferred 91.1936, seen
  1,328,676 (2026-10-13: 96.17 / 93.16; 2026-10-12: 95.93 / 92.98). The Jio
  series moves 1-2 points a day, so read the figures as "about 94-96%".
- Code note confirmed: `app/api/limits.py` `_client_of()` returns
  `request.client.host` (line 118-119), and no file in the repo sets
  `forwarded_allow_ips` or `proxy_headers`, so uvicorn's defaults apply as the
  researcher described.

### F9. Sarvam prepaid credits and rate limits - CONFIRMED; one arithmetic slip CORRECTED

- Verdict: **confirmed** (all the facts); **corrected** (the hours figure).
- Evidence (docs.sarvam.ai/api-reference-docs/ratelimits, fetched 2026-10-15,
  no date shown): STT REST 60 req/min (Starter, "Pay as you go"), 100 (Pro,
  ₹10,000), 4,000 (Business, ₹50,000); "Rate limits are measured per account,
  not per API key"; over the limit returns 429 `rate_limit_exceeded_error`; "A
  `503 Service Unavailable` can also occur under high backend load"; "₹100
  worth of free credits"; "Credits are universal and never expire"; "If your
  credits are exhausted, API requests will return errors". No spend alerts or
  controls are mentioned.
- Correction: at the stated ₹0.58 per 70 s (PROJECT_PLAN §8: ₹30/hour, billed
  per second), ₹500 buys **about 16.7 hours** of audio, not "about 14". About
  14.2 hours would be right only if 18% GST is also deducted from the balance,
  and the finding does not say so. ₹300 is about 10 hours. Immaterial to the
  recommendation.
- The chunking premise holds: `app/providers/media.py` documents "The sync
  Sarvam endpoint takes <=30 s of audio per request", so a 300 s clip is about
  10 requests.

### F8. SMS OTP prices - CORRECTED (the "costs about as much as a check" claim is half wrong)

- Verdict: **corrected**.
- Firebase India price: **uncertain**. Google's Identity Platform pricing page
  did not render its per-country table for this verifier either (fetched
  2026-10-15), so $0.07 per SMS to India is still secondary-only. What the
  Google/Firebase search results do support: SMS is billed per message sent;
  a linked Cloud Billing account has been required since September 2024; a
  3,000/day ceiling applies without the Identity Platform upgrade; India must be
  allowed explicitly in "SMS regions" (all regions are closed by default); and
  Firebase Phone Number Verification's country table does not include India
  (firebase.google.com/docs/phone-number-verification/pricing, search result
  2026-10-15).
- Arithmetic correction (independent of any source): at the researcher's own
  MSG91 figure of ₹0.15-0.25 per OTP (about $0.0017-0.0028 at ~₹88/$), an OTP
  costs **about 3-4% of an average check** ($0.066), not "about as much as a
  check". Only the Firebase figure (if right) is ~1.06x a check. So the
  sentence "each OTP costs about as much as a check" holds only for Firebase.
- Does "do not use SMS OTP" still follow? Yes, but for different reasons than
  the stated one: DLT entity, sender-ID and template registration paperwork for
  an individual (the finding's own "30-50%" note), SMS-pumping fraud exposure
  (every send is billed, including ones never entered), and the fact that the
  bots already give a phone-verified identity for free. The MSG91 price itself
  is not the obstacle. (The MSG91 range is still from secondary sources; see
  the line added below if a primary is reached.)

- F8 addendum (MSG91 primary, via search of msg91.com/in/pricing/otp, 2026-10-15,
  pages undated): OTP SMS **₹0.25 each at a 5,000-OTP pack**, falling to ₹0.22
  (15,000), ₹0.20 (27,000), ₹0.19 and ₹0.18 (8,55,556); **18% GST on top**;
  failed sends are billable. So the realistic small-buyer price is about ₹0.295
  with GST (about $0.0034), roughly **5% of an average check**, with a ~₹1,250
  (+GST) minimum pack. The researcher's lower bound of ₹0.15 is not on MSG91's
  own page (₹0.18 is its floor). This strengthens the correction above.

### L0 error mapping (recommendation input) - CORRECTED: a third "paused" error is missing

- Verdict: **corrected**. The two spend-limit errors are mapped correctly
  (F1), but the recommended settings make a DIFFERENT error the likely first
  one. A $10-20 prepaid balance with auto-reload off runs out long before a $45
  monthly limit is reached (at $1.50/day, $15 lasts about 10 days).
- Evidence (platform.claude.com/docs/en/api/errors, fetched 2026-10-15): the
  page lists "402 - `billing_error`: There's an issue with your billing or
  payment information", and a 400 for "a spend limit you set". It does NOT
  document the response for an exhausted credit balance. The support article
  says only "If you run out of credits, you can no longer call the API". The
  historical message ("Your credit balance is too low to access the Anthropic
  API", a 400 `invalid_request_error`) is from memory and **unverified** here.
- Corrected advice: treat 400 spend-limit, 429 `enforced_spend_limit_reached`,
  402 `billing_error`, and any 400 whose message mentions the credit balance
  as one "service paused" state: refund the slot, show "back later", and alert
  the owner. Do not let the SDK's automatic retries ("twice by default")
  re-send them. The docs say the spend-cap 429 "keeps failing until access
  resumes". Get the real credit-exhausted response with a free test rather
  than guess it: an API key in an empty workspace is not one (credits are
  org-wide), so this needs one deliberate observation the next time the
  balance runs low.

### Taxes on the budget (not in the research) - UNCERTAIN, flagged

- Verdict: **uncertain**. Every $ figure in the research is list price before
  tax, and so is the app's spend ledger.
- Evidence: Anthropic's own payment article says reload charges are "plus
  applicable taxes" (support.claude.com 8977456, 2026-10-15). Press reports
  (freepressjournal.in, techstory.in, outlookbusiness.com, found 2026-10-15;
  secondary) say Anthropic introduced rupee pricing with GST built in for
  Claude **subscriptions** on 2026-07-13. Before that, Indian buyers paid "an
  18% tax layered over the converted sum" plus a 2-3% card conversion fee.
  Nothing found says how **Console API credits** bought from India are taxed.
- Consequence: the real rupee outflow may be up to about 18-21% above the
  ledger's dollar total. At $1.50/day that is about $1.77-1.82 actually paid.
  The owner can see it on the first Console invoice for free. Sarvam's and
  MSG91's prices are likewise before 18% GST.

### F6 (part 3). Airtel IPv6 share, and "publish an AAAA record" - CORRECTED (small)

- Verdict: **corrected**. Airtel is a little lower than stated, and Cloudflare
  already does the AAAA step if the site sits behind it.
- Evidence (stats.labs.apnic.net/cgi-bin/json-table-v6.pl?x=IN45609, tail,
  fetched 2026-10-15; the series DOES run to October, so the researcher's
  "2026-04-03 latest row" was a truncated read): Airtel AS45609 2026-10-14
  capable **87.90%**, preferred 86.31%, seen 758,368 (2026-10-13: 89.91 /
  88.34; 2026-10-12: 89.97 / 88.56; 2025-11-26: 90.60 / 89.63).
- Corrected statement: "Jio about 94-96% and Airtel about 88-90% IPv6-capable
  (APNIC, 12-14 Oct 2026)". The recommendation's "Jio and Airtel (91-94%
  IPv6)" should read "88-96%". The conclusion (per-/64 keys reach most mobile
  users) is unchanged.
- Evidence (developers.cloudflare.com/network/ipv6-compatibility/, "Last
  updated: Aug 25, 2026"): "By default, IPv6 compatibility is turned on" for
  "all domains and subdomains covered by proxied DNS records"; "Cloudflare auto
  generates AAAA DNS records"; only Enterprise can turn it off. So if the site
  is served through Cloudflare (Tunnel or proxied DNS), L3's "publish an AAAA
  record" already holds and needs only checking. On a non-Cloudflare host it is
  real work (the host needs IPv6).

### F6 (part 4). "A 3GPP handset gets its own /64" - CONFIRMED, with a caveat that matters for L3

- Verdict: **confirmed** that the prefix is unique. The caveat is
  **uncertain**.
- Evidence (RFC 6459, rfc-editor.org, fetched 2026-10-15): §5.2 "The
  GGSN/PDN-GW guarantees that the /64 prefix is unique for the UE"; §4.2 "Each
  PDN connection has its own IP address/prefix".
- Caveat: §5.2 also says "The lifetime of the /64 prefix is bound to the
  lifetime of the layer-2 connection". So a /64 identifies a CONNECTION, not a
  handset. Whether an airplane-mode toggle gets a different /64 from Jio or
  Airtel is operator behaviour the RFC does not fix. If it does, a per-/64 limit
  is about as resettable as a cookie. One free test with one phone settles it.
  §5.3: a hotspot shares the phone's /64 by ND proxy, so a household on one
  hotspot is one key. The fixed-broadband /56-vs-/64 point was not checked
  (the researcher flagged it too).

### F10. Google Fact Check Tools API quota - NOT RE-CHECKED (stays uncertain)

- Verdict: **uncertain**, unchanged. It is low-confidence, not
  decision-critical, and the owner can read it for free in Cloud Console >
  Fact Check Tools > Quotas. It was skipped to stay inside the web-call budget.

## Recommendation check

Overall: **the layered scheme follows from the evidence.** Every external
backstop it names exists and behaves as described: F1-F3 confirmed on primary
pages, nearly word for word. The case for a dollar budget follows from the
measured 20x spread in per-check cost. No correction reverses a
recommendation. The corrections change a number, swap a rationale, or add a
missing step:

- **L0 (external backstops): follows, with additions.**
  - (a) Under L0's own settings (a $10-20 balance, auto-reload off, a $45
    monthly limit), the **credit balance runs out first**. Map that error and
    402 `billing_error` to the "paused" state too, not just the two spend-limit
    errors.
  - (b) "Turn auto-reload OFF" should be "confirm it is off". The default is
    undocumented.
  - (c) 30x the daily budget is $1.50 short of a 31-day month at full daily
    spend, and Anthropic's month resets at 00:00 UTC on the 1st (05:30 IST),
    not at the app's midnight. Use 31x, or accept that the 31st may stop early.
  - (d) The prepaid balance belongs to the organization (inference: credits
    are bought on the org's Billing page). A drained public workspace
    therefore also stops the owner's own keys. Workspace limits protect other
    workspaces from overuse, not from an empty balance.
- **L1 (dollar budget): follows, with one wording fix and two code gaps.**
  - Wording: a count cap DOES bound spend, at count x dearest check (5 x
    $0.1724 = $0.86/day at today's cap). It just wastes most of a budget sized
    that way. The argument for dollars is efficiency.
  - Starting point: $1.50/day is about $45/month, about ₹4,000/month before
    tax (at ~₹88/$). That is roughly 4.5x today's average spend (5 x $0.066 =
    $0.33/day). The owner should see that figure, not only "22 checks a day".
  - The 40% / 15% thresholds are reasoned, not evidenced (the researcher says
    so).
  - Code gap 1: `cache_key()` in `app/engine/job.py` includes the global
    `settings.web_tier_enabled` but no per-request mode, and `run_check` caches
    every answer that has sections. A budget-degraded answer ("no vetted source
    covered this", pass 2 skipped) would be cached and served to tomorrow's
    full-budget askers until its TTL. Put the mode in the key, or do not cache
    degraded answers. This is invariant 6's staleness problem in a new form.
  - Code gap 2: "at 0, keep serving exact repeats free" needs a cache peek
    BEFORE the budget gate. Today `_quota` claims first (`app/api/routes.py`)
    and the cache is read inside `run_check`, so a repeat is refused at the cap.
- **L2 (per-person quotas): follows, as a speed bump.**
  - Every per-person key is resettable: a cookie costs one Turnstile solve,
    and a /64 possibly one airplane-mode toggle (F6 part 4). The global dollar
    budget stays the only hard bound, as the researcher says.
  - Capacity: at $1.50/day and 3 checks per cookie, a day serves about 7
    people at the base mix, about 4 on a fresh-rumour day.
- **L3 (network brakes): follows.**
  - Correct Airtel to 88-90%.
  - The AAAA record is automatic behind Cloudflare (F6 part 3).
  - 20/day per IPv4 is ~90% of a whole $1.50 day at the base mix, so it brakes
    nothing the global budget does not. It is harmless.
- **L4 (Turnstile): follows** (F3).
  - Add a fake for siteverify (invariant 9: no test may reach
    challenges.cloudflare.com). Cloudflare documents dummy test keys, and
    "production secret keys will reject dummy tokens".
- **Translation: the direction follows; the size does not.**
  - "+35-45%" is +36% on an ASSUMED 30%->45% shortcut shift.
  - What was measured is Google matches 3/12 -> 7/12 with a hand translation,
    and a match still needs trusted="yes".
  - The translation call has its own small cost. Build it, then measure it.
- **No SMS OTP: the conclusion follows; the stated reason does not.**
  - MSG91 is ~5% of a check with GST, not "about as much as a check".
  - The real reasons: DLT paperwork for an individual, SMS-pumping exposure
    (every send billed), and the bots already give a free phone-verified
    identity.
- **WhatsApp go/no-go: follows, and is stronger than stated.**
  - The paid AI-Provider exception is live only in Brazil today, and only for
    "general-purpose AI assistants".
  - India has no route at all if Meta deems the bot AI-primary.

## Missed

1. **Taxes.** Anthropic charges "plus applicable taxes". Whether 18% GST lands
   on Console credits bought from India is unconfirmed (rupee pricing with GST
   included is reported only for subscriptions, 2026-07-13). Sarvam and MSG91
   prices are before 18% GST. The spend ledger records list price, so real
   outflow may be up to ~18-21% above it. The first invoice settles it for free.
2. **The credit-exhausted error** (see L0 a). It is the most likely first stop,
   and its exact response is not on the errors page. Observe it once rather
   than guess.
3. **Workspace RATE limits** (documented: "custom spend and rate limits per
   Workspace", per limiter type) cost nothing and bound how FAST a runaway loop
   can burn. It is a partial brake: cache reads and search fees are not
   counted.
4. **Cloudflare's free edge rate-limit rule**
   (developers.cloudflare.com/waf/rate-limiting-rules/, updated 2026-08-25):
   Free = 1 rule, counting by "IP" only, 10 s period and 10 s mitigation. It is
   a flood brake in front of the origin, not a daily quota, and it is not
   /64-aware.
5. **A /64 is per connection** (RFC 6459 §5.2). Test airplane-mode
   re-prefixing on one Jio and one Airtel phone before trusting per-/64 keys.
6. **Degraded answers poisoning the answer cache**, and **the cache peek before
   the gate** (L1 code gaps; evidence in `app/engine/job.py` and
   `app/api/routes.py`).
7. **Inputs missing from the mix and the reservation table.** Screenshots add a
   Sonnet 5 vision OCR call (`settings.vision_model`; the "Opus" in the
   `routes.py` comment is stale). Voice notes add Sarvam ASR. Only text and
   link/reel reservations are given.
8. **SDK retries.** The Anthropic SDK retries 429s "twice by default", and the
   spend-cap 429 "keeps failing until access resumes". Skip retries when
   `error_code` is `enforced_spend_limit_reached`. It costs latency, not money.
9. **What strangers will see.** About 7 people a day at $1.50. Once a link
   spreads, "back at midnight IST" becomes the usual experience by mid-morning.
   Showing the day's remaining budget, or holding a share back for the bot, is
   a product decision the research does not raise.
10. **The Evaluation tier's spend cap** is unpublished too, not only its rate
    limits (the cap table lists Start / Build / Scale only). Read the real tier
    on platform.claude.com/usage/limits.
11. **Telegram ids** (from memory, not re-checked this session): Telegram also
    accepts anonymous Fragment (+888) numbers with no SIM, so "phone-verified"
    is "nearly always". The risk is low because those numbers are expensive.

Web calls used: 24 of ~25 (WebFetch/WebSearch). Money spent: $0.
