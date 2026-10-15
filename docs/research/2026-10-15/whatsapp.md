# Starting a WhatsApp bot on Meta's Cloud API — research, 2026-10-15

status: complete

Verification: one research agent, 35 web calls, no money spent. **No independent verifier has
checked this file yet.** Decision-critical findings are marked; each finding names its sources
and their dates. The working log this was distilled from is in the session scratchpad
(`rerun/whatsapp_worklog_backup.md`).

Scope: everything an individual in India (no registered company) needs to START a reply-only
fact-check tipline on Meta's WhatsApp Business Platform (Cloud API): people forward a message,
voice note, screenshot or reel link; the bot replies with a verdict and sources.

## Summary

- **The afternoon part is free and needs no company.** A Facebook account, a Meta developer
  account, a Meta app with the WhatsApp use case, a business portfolio and a WhatsApp Business
  Account (WABA) can all be created today. Meta's test number can then message up to
  5 allowlisted phones, which is enough to build and test the whole webhook flow (W1–W2).
- **Going public needs three things, and Meta verification is not one of them:** a dedicated
  number that is not on WhatsApp, a public privacy-policy URL so the app can go Live, and a
  card in Billing Hub. Messaging limits count only deliveries outside the 24-hour window,
  so replies to people who wrote first never use up the 250 starting limit. App Review is only
  for apps that serve other businesses (W3, W5, W7, W8, W11).
- **Business verification** needs documents for a registered business. An individual gets
  there by registering a sole proprietorship on Udyam, which is free, and using exactly that
  name. Verification is useful later (20 numbers instead of 2, an easier display-name review,
  credibility), but the bot can launch without it (W6).
- **Cost:** from 2026-10-01 Meta charges for in-window replies ("service" messages). India's
  rate is **INR 0.1150 per message** (Meta's own INR rate card). Each business number gets
  **1,000 free service messages a month**. So 100 or 1,000 one-message replies a month cost
  INR 0. If every check sends two messages, 1,000 checks cost INR 115 + GST. The LLM bill is
  about 100 times larger than Meta's fee (W9–W12).
- **The real risk is policy, not money or paperwork.** Section 4.7 of Meta's Terms
  (last modified 2026-09-23) "strictly" prohibits AI Providers "when such technologies are the
  primary (rather than incidental or ancillary) functionality", and Meta decides "in its sole
  discretion". Meta allows paid AI-provider access only where the law forces it to: EU/EEA and
  Italy (now free there) and Brazil. India has no such carve-out, and no CCI case was found.
  On the other side:
  - Meta says businesses that use AI to serve their customers are not affected.
  - Meta's pricing docs expect third-party AI to write service messages.
  - The Quint launched a Meedan-built "conversational AI-driven bot" on WhatsApp in India on
    2026-05-04.

  **Assessment: probably permissible as a single-purpose verification service that offers a
  human escalation path. It is not risk-free, and only Meta can retire the risk** (W14–W21).
- **Recommended route: Meta Cloud API directly.** BSPs (Twilio, Gupshup, AiSensy, Interakt,
  WATI) add fees, but they do not add eligibility. They ask for the same documents and are bound
  by the same section 4.7.

## Findings

### Account chain and setup

**W1 — The account chain, in an afternoon, free.**
Prerequisites:
- A Facebook account (or a managed Meta account).
- Meta developer registration.
- A phone that has WhatsApp, to receive the test messages.

Steps:
1. Create a Meta app with the use case "Connect with customers through WhatsApp", and pick or
   create a business portfolio.
2. Click "Start using the API" and connect the app to a new or existing WABA.
3. Generate a temporary access token, pick the test "From" number, enter a "To" number and send
   the test template.
4. Reply from the phone to open the conversation, then optionally set up a test webhook.

The temporary token "expires quickly and is not suitable for development purposes". Use a
System User token instead (W7). Section 2.2 of the Terms says: "To use the WhatsApp Business
Platform, you must have a business portfolio with Meta Business Suite". The Terms do not bar an
individual from creating one.
Sources: developers.facebook.com/documentation/business-messaging/whatsapp/get-started.md
(fetched 2026-10-15, undated); Meta Terms (last modified 2026-09-23). Confidence: high.

**W2 — The free test number reaches at most 5 recipients.**
- Recipients are added under WhatsApp > API Setup > "Manage phone number list", and each one is
  verified with a code sent over WhatsApp.
- Only those numbers can exchange messages with the test number.
- Templates made on the test number do not carry over to a real number.

Sources: a WebSearch on 2026-10-15 that summarised Meta's Get Started guide ("caps the test
recipient list at five"), a wati.io blog post and a help.wanotifier.com article. The .md page
fetched today did not state the cap. Confidence: medium-high. Confirm it in the API Setup panel.

### Number, name, limits, verification

**W3 — A real number must be dedicated: it cannot stay on the WhatsApp app. [DECISION-CRITICAL]**
- The number must be owned by you, include a country and area code, and be able to receive an
  SMS or a voice call for the code. For fixed lines Meta rates voice OTP "Standard" and SMS OTP
  "Not Recommended". Short codes are not supported.
- "Numbers already in use with WhatsApp cannot be registered unless they are deleted first".
  Once registered, a number "cannot be used with WhatsApp Messenger". A banned number must first
  be unbanned through an appeal.
- Adding the number in the dashboard does **not** register it. You must also call the register
  endpoint, and "You must set a two-step verification PIN when registering a business phone
  number."
- "New business portfolios are initially capped at two registered business phone numbers".
  The cap rises to 20 automatically once the business is verified or reaches the 2,000 limit.
- The number must show status "connected" to send or receive. Display-name details are
  required at registration.

A coexistence onboarding that keeps the WhatsApp Business app on the same number exists through
a Solution Provider's Embedded Signup. That page does not cover it, and it was not verified here.
Source: developers.facebook.com/documentation/business-messaging/whatsapp/business-phone-numbers/phone-numbers.md
(fetched 2026-10-15). Confidence: high.

**W4 — Display-name review is triggered when the messaging limit rises.**
- "When you reach a higher messaging limit, your business phone number's display name
  automatically undergoes verification based on the display name guidelines".
- Possible states: APPROVED, AVAILABLE_WITHOUT_REVIEW, PENDING_REVIEW, DECLINED, EXPIRED and
  NONE. A declined name can be edited or appealed through Developer Support.
- The name can change at most 10 times per 30 days. After an approved change, the number must be
  re-registered within 14 days.

The naming rules are in a Help Center article ("Display name guidelines for the WhatsApp Business
Platform"), which was not read. In practice, the name should match the business and the website
shown in the portfolio.
Source: developers.facebook.com/documentation/business-messaging/whatsapp/display-names.md
(fetched 2026-10-15). Confidence: high on the page; the guidelines were not read.

**W5 — Messaging limits count only deliveries OUTSIDE a customer-service window. [DECISION-CRITICAL]**
- The limit is the "maximum number of unique WhatsApp user phone numbers your business can
  deliver messages to" in a "moving 24-hour period". Only deliveries outside a customer-service
  window count.
- "Newly created business portfolios have a messaging limit of 250". The tiers are 2,000,
  10,000, 100,000 and unlimited.
- To reach 2,000: verify the business, have a partner verify it, or send 2,000 out-of-window
  messages to unique numbers in 30 days using high-quality templates. Above that, the limit rises
  automatically (within 6 hours) when quality is high and at least half the limit was used in the
  last 7 days.
- The limit is set per business portfolio and shared by all its numbers.

**A reply-only tipline answers inside the window, so it never consumes this limit.**
Source: developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits.md
(fetched 2026-10-15). Confidence: high.

**W6 — Business verification: for registered businesses. An individual registers as a sole
proprietor first, and launch does not need it. [DECISION-CRITICAL]**

Documents for India, from vendor docs that reproduce Meta's per-country list (Meta's Help Center
could not be fetched):
- business bank statement
- business licence
- certificate of incorporation
- GST registration
- PAN card
- shop and establishment certificate
- Udyog Aadhaar or Udyam (MSME) registration
- utility bill

Rules:
- The business must be registered with local authorities and have an official phone number or
  mailing address.
- The business name and address entered in Meta must match the document **exactly**.
- Not accepted: invoices, purchase orders, self-filled forms, tax returns, website printouts, and
  personal ID such as Aadhaar or a passport. An admin's ID may be requested separately.
- A rejected check can be resubmitted.

Typical time: "within seven business days" (Gallabox) or "several days" (WATI).

Route for an individual: register a sole proprietorship on the Udyam portal (free and online,
with Aadhaar and PAN) under the business name you will use. GST is not needed for a free service
below the threshold, though some BSPs insist on it. A public website showing the business name
helps. A bare personal PAN is weak evidence.

Not required to launch: replies do not use the limit (W5), and App Review does not need it (W7).
Some BSP docs (Exotel) say every API business must verify, but that is their policy and not
Meta's documented rule.

Sources: a WebSearch on 2026-10-15 covering the support.wati.io article 11463208, the
docs.gallabox.com verification page, two support.myoperator.com articles (2025-09-20), the
richautomate.in 2026 GST guide, zoko.io ("whatsapp business api no gst number") and
support.chatarchitect.com (a mirror of Meta's "About business verification").
Confidence: medium. The sources are secondary but consistent. Meta shows its live list in
Security Center when verification starts.

**W7 — No App Review for your own business. Use a long-lived System User token. [DECISION-CRITICAL]**

App Review:
- "if you are using the API for yourself as a Direct Developer, you do not need Advanced access
  or app review". Standard Access is granted automatically.
- Advanced access, with a review averaging about 24 hours, is only for apps that other
  businesses use.

Tokens:
- System User tokens are long-lived: "Use them if you are a direct developer".
- To create one: Business settings > System Users > +Add (Admin or Employee) > Assign assets
  (the app, with "Manage app") > Generate token, then choose an expiry.
- Permissions: `business_management`, `whatsapp_business_management` and
  `whatsapp_business_messaging`.
- Give the system user access to the WABA under Accounts > WhatsApp Accounts > WhatsApp Account
  Access.
- The page does not list the expiry options. The "Never" option is general knowledge and was not
  verified.

Sources: .../solution-providers/app-review.md and .../access-tokens.md (fetched 2026-10-15).
Confidence: high.

**W8 — Going Live needs a public privacy-policy URL, and Dev mode loses webhooks. [DECISION-CRITICAL]**
- Switching a Meta app to Live requires a valid, publicly reachable privacy-policy URL in
  Basic settings. The reported error is "You must provide a valid Privacy Policy URL in order to
  take your app Live".
- Meta's privacy-policy expectations: say what is collected, how it is used and how to request
  deletion. Copying someone else's policy does not satisfy Meta.
- Meta's webhook docs: "Make sure your app is in Live mode; some webhooks will not be sent if
  your app is in Dev mode."
- The Terms themselves contain no privacy-policy clause. This is a Meta-wide app rule.

Sources: a WebSearch on 2026-10-15 (Meta's privacy-policy expectations page at
developers.facebook.com/documentation/development/terms-and-policies/privacy-policy.md, a Meta
community forum thread, martech.org, and the Meta blog post of 2019-09-23); .../webhooks/overview.md
(fetched 2026-10-15). Confidence: medium-high. This ties in with policy-legal.md, since the site
needs a privacy policy anyway.

### Pricing after 2026-10-01

**W9 — Meta bills per message, and in-window replies ("service messages") are charged from
2026-10-01. [DECISION-CRITICAL]**
- Per-message billing has applied since 2025-07-01, and conversation pricing is deprecated.
- Meta's page says: "Effective October 1, 2026, Meta will charge for service messages, which have
  not been charged since November 2024." It also says "Meta will charge on a per-message basis
  for service messages", that the rate equals the market's utility/authentication rate, and that
  service messages have no volume tiers.
- Messages in the 72-hour free-entry-point window (Click-to-WhatsApp ads, Facebook call-to-action
  buttons) remain free for delivery.
- Meta Business Agent messages (Meta's own AI) cost USD 2.00 per 1M tokens from 2026-08-01.
  A message is never charged twice.
- AI Providers are billed under a separate policy (W15).
- Sending rules are unchanged. Free-form replies are still allowed only inside the 24-hour
  window, which "opens and resets with each user message".

Sources: .../pricing/non-template-messages (en_US HTML and .md, fetched 2026-10-15, undated);
.../pricing.md (fetched 2026-10-15). The fetch tool returned an **older** copy of the main pricing
page that still says "All non-template messages are free"; see W11. Confidence: high.

**W10 — PRIMARY: Meta's INR rate card effective 2026-10-01 for India. [DECISION-CRITICAL]**

The card is titled "Cost per message in INR on the WhatsApp Business Platform, effective
October 1, 2026". India's row:

| Category | INR per delivered message |
|---|---|
| Marketing | 0.8631 |
| Utility | 0.1150 |
| Authentication | 0.1150 |
| Authentication-International | 2.4971 |
| **Service** | **0.1150** |
| Meta Business Agent | "$2.00 USD / 1 M (million) tokens" |

- "Volume tiers apply only to utility and authentication messages." India's utility list rate
  holds up to 25,000,000 messages a month.
- The card has no footnote about a free allowance.
- Service equals utility in every market on the card.
- Separately, India billing moved to INR on 2026-01-01. All WABAs must use INR by 2026-12-31, or
  Meta stops delivering their messages from 2027-01-01. Choose INR when creating the WABA.

Source: Meta's rate-card PDF on scontent.fbom3-2.fna.fbcdn.net, linked from the pricing page's
"Rate cards and volume tiers" (a signed link that expires around 2026-10-19), read on 2026-10-15.
The fetch tool kept a local copy under the session's tool-results folder
(`webfetch-1792082165914-yjn2oz.pdf`). The INR deadline comes from .../pricing.md.
Confidence: high, because the numbers are verbatim from the primary source.

**W11 — 1,000 free service messages per business number per month. Without a card, sending stops
when they run out. [DECISION-CRITICAL]**

What Meta's pricing page says, as returned by a WebSearch limited to Meta's own domains (page
"last updated September 30, 2026"):
- Charging starts at midnight on 2026-10-01 in each WABA's time zone.
- "every business phone number gets 1,000 free service messages a month before any fees apply".
  Unused messages lapse at the monthly reset.
- Accounts **without a payment method** still get the allowance, but sending stops once it runs
  out. Meta's deadline to add a payment method was 2026-09-30.
- Direct customers pay by card or on a monthly-invoiced Meta credit line.
- Eligible government and nonprofit organisations are exempt until 2027-12-31.

360dialog's blog says the same about the allowance: it counts per registered number, a WABA with
5 numbers gets 5 allowances, and billing starts at the 1,001st delivered message. It quotes USD
0.0014 for India, which equals the INR 0.115 above.
Sources: developers.facebook.com/documentation/business-messaging/whatsapp/pricing (search
index; page dated 2026-09-30) and whatsappbusiness.com/resources/faq/, searched 2026-10-15;
360dialog.com/blog/whatsapp-service-message-charging-october-2026/ (undated, cites Meta pages
checked 2026-09-08). Confidence: medium-high. Two independent sources agree, but a direct fetch
of Meta's page returned a stale copy without the allowance.

**W12 — What replies cost (Meta's fee only, INR 0.1150 per service message, before 18% GST).
[DECISION-CRITICAL]**

| Checks per month | Messages sent | With the 1,000 allowance (W11) | Without any allowance |
|---|---|---|---|
| 100, one message each | 100 | INR 0 | INR 11.50 |
| 100, verdict + "checking…" note | 200 | INR 0 | INR 23 |
| 1,000, one message each | 1,000 | INR 0 | INR 115 |
| 1,000, two messages each | 2,000 | INR 115 (about 136 with GST) | INR 230 |

- Inbound messages are not billed by Meta, which charges for delivered outbound messages.
  Templates are not needed for a reply-only bot.
- Every extra message per check costs INR 0.115 beyond the allowance. That includes a split long
  answer or an interim note.
- For scale: the deployment cap of 5 checks a day allows at most about 155 checks a month, which
  costs INR 0 at Meta. The LLM costs USD 0.05–0.17 per check (CLAUDE.md), so 1,000 checks cost
  USD 50–170 in model fees against at most INR 230 at Meta.

### Policy: the AI-Provider ban

**W13 — The text of section 4.7 (Meta Terms for WhatsApp Business Platform, "Last modified:
September 23, 2026"). [DECISION-CRITICAL]**
`whatsapp.com/legal/business-solution-terms/` now redirects (301) to
`facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform`. The fetch tool quotes at most
125 characters at a time. Its segments, in page order and verbatim (the joining words between
them were **not** verified):

> "Providers and developers of artificial intelligence or machine learning technologies" …
> "including but not limited to large language models, generative artificial intelligence
> platforms" … "general-purpose artificial intelligence assistants, or similar technologies as
> determined by Meta in its sole discretion" … "are strictly prohibited from accessing or using
> the WhatsApp Business Platform, whether directly or indirectly" … "when such technologies are
> the primary (rather than incidental or ancillary) functionality being made available for use"
> … "as determined by Meta in its sole discretion".

The current text also says:
- Such technologies "may be made available to businesses in certain countries as set forth here",
  with a link to Meta's list of countries; see W14.
- "you may retain an AI Provider as your Solution Provider".
- Platform data must not be used to train AI models. Fine-tuning a model for your exclusive use
  is allowed.

Section 1.2 refers to signing up "on behalf of a company or other legal entity". No clause bars
an individual.
Source: facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform (fetched 2026-10-15).
Confidence: high on the segments.

**W14 — Meta's "AI Providers" page: paid access only where the law forces Meta, and India is not
one of those markets. [DECISION-CRITICAL]**
- AI Providers may offer general-purpose AI assistants "only ... where Meta is legally required
  to permit this use case". **Paying does not buy access anywhere else.**
- In those markets Meta charges per non-template message delivered, from 2026-02-16. Its example:
  3 replies to an Italian user in 5 minutes are 3 charges.
- The markets:
  - Italy (+39): 2026-02-16 to 2026-05-12.
  - EU/EEA (29 countries): 2026-03-11 to 2026-05-12.
  - Brazil (+55): from 2026-03-11, with no end date.
- Meta's changelog, 2026-05-12: no charges for AI Providers' messages to EU/EEA users from
  2026-05-13. "Charges for non-template messages delivered to users in Brazil remain in effect."
- Pricing category `AI_BOT`; webhook category `general_purpose_ai`.

Sources: developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers.md
and .../changelog.md (entry of 2026-05-12), both fetched 2026-10-15. Confidence: high.

**W15 — Regulators: the EU ordered free access and Meta is appealing; Brazil allows it for a fee;
no Indian case was found.**
- **European Commission:**
  - The antitrust probe opened in December 2025, with a statement of objections in February 2026
    and a supplementary one in April 2026.
  - Interim measures came on **2026-06-09** under Article 8 of Regulation 1/2003. Meta had to
    restore **free** access for rival general-purpose assistants within 5 working days,
    reverting to its pre-October-2025 terms, while the case runs.
  - The Commission treated Meta's paid access from March 2026 as equivalent to the ban.
  - Meta called it "regulatory overreach" and appealed to the EU General Court in August 2026
    (Slaughter and May act for Meta; MLex reported it on 2026-08-17). An appeal does not suspend
    the decision by itself, and no suspension was found.
- **Italy:** AGCM ordered Meta to suspend the terms in Italy in December 2025.
- **Brazil:** CADE imposed an injunction. A federal court suspended it (MLex, 2026-01-23, case
  under seal). Reports say CADE imposed daily fines in April 2026. Meta's own page lists Brazil
  as legally required from 2026-03-11.
- **COMESA:** a probe has been open since a complaint on 2026-01-05.
- **India (CCI):** no complaint, probe or order on these terms was found. The CCI's live WhatsApp
  matter is the 2021 privacy-policy case, now in the Supreme Court.

Sources: WebSearch on 2026-10-15 (AP via WTOP/NY1, Morningstar/Dow Jones, Bloomberg Law and the
Washington Times, all 2026-06-09; the Slaughter and May page; MLex 2433430; globalcompetitionreview.com;
theeastafrican.co.ke; nasdaq.com; newsonair.gov.in 2026-02-09). The Commission's own text was not
read. Confidence: medium-high for the EU, medium for Brazil, medium for India (absence of evidence).

**W16 — Meta's stated intent: the ban targets general-purpose assistants, not businesses that use
AI with customers. [DECISION-CRITICAL]**
- Meta's spokesperson: "The purpose of the WhatsApp Business API is to help businesses provide
  customer support and send relevant updates."
- Meta confirmed that businesses using AI to serve their customers are not affected; a travel
  company's support bot was the example.
- The targets were assistants such as ChatGPT, Perplexity, Luzia and Poke. The rule took effect
  for them on 2026-01-15.
- No Meta FAQ with examples of "primary" versus "incidental" AI was found on any Meta domain.

Sources: TechCrunch (Ivan Mehta, 2025-10-18, with an update); a WebSearch of Meta domains on
2026-10-15. Confidence: high that this was Meta's position. The Terms still say "sole discretion".

**W17 — The Business Policy requires a human escalation path, and Meta expects third-party AI.
[DECISION-CRITICAL]**
- Business Policy: "You may use automation when responding during the 24-hour window, but must
  also have available prompt, clear, and direct escalation paths." It also says "Using
  unauthorized third-party tools is prohibited", without defining the term.
- Meta's pricing docs define a service message as: "Any non-template message not powered by the
  Meta Business Agent Platform. These can be powered by a 3rd-party AI solution or people".
- Meta launched its own "Business AI on WhatsApp for Small Businesses in India" in May 2026.

Sources: whatsappbusiness.com/policy/ and Meta's pricing docs, via the Meta-domain WebSearch on
2026-10-15; about.fb.com (2026-05). Confidence: medium-high, since the text was read through
search excerpts.

**W18 — How real Indian fact-check tiplines run on WhatsApp in 2026. [DECISION-CRITICAL]**
- **The Quint** (2026-05-04): "In partnership with Meedan, we have built a new conversational
  AI-driven bot".
  - It runs on WhatsApp +91-8826811818 and on Telegram as @Suwali_Quintbot.
  - It answers from the paper's own archive of about 200 recent stories, in English and Hindi,
    text only.
  - If it cannot answer, "our team of journalists will be alerted". It opened to subscribers
    first. The model is not named.
  - **An AI tipline is live in India after the ban took effect, but its AI is secondary to a
    newsroom.**
- **Meedan Check**, which most IFCN tiplines run on, matches tips against existing fact-checks
  and groups them with AI. Unmatched tips go to human reporters. Factly (+91 92470 52470) uses it.
- **Vishvas News** (+91 95992 99372) and **Newschecker** use bots only to screen and match;
  humans reply.
- **MCA's deepfake tipline** (+91 9999025044) was launched with Meta on 2024-03-25.
- No 2026 report was found of BOOM, Factly, Vishvas News or Fact Crescendo having an LLM *write*
  the verdicts.

Sources: thequint.com/news/webqoof/welcome-to-the-quint-ai-chatbot-on-whatsapp-telegram
(2026-05-04); a WebSearch on 2026-10-15 (meedan.com post on Factly, leadstories.com 2024-08,
about.fb.com 2024-02, newschecker.in). Confidence: high for The Quint; medium for the others.

**W19 — ASSESSMENT: does section 4.7 cover an LLM-powered claim-verification tipline?
[DECISION-CRITICAL]**

For "not covered":
- The owner does not build LLMs or a general-purpose assistant. He runs a single-purpose
  service: `app/engine/triage.py` already refuses small talk before any money is spent.
- Its answers rest on vetted fact-checkers (Google Fact Check API plus the whitelist), with
  sources.
- Meta exempts businesses that use AI to serve customers (W16) and expects third-party AI in
  service messages (W17).
- The Quint's AI bot is live in India (W18).

For "covered":
- Here the LLM's verdict *is* the product. There is no newsroom, no archive and no staff behind
  it, so a reviewer could call generative AI the "primary functionality".
- Meta decides in its "sole discretion", and the penalty is a disabled number or WABA.
- There is no human escalation path today (W17).

**Verdict: probably permissible, but not safe to assume. The risk is moderate, and research
cannot remove it.** Ways to reduce it:
- Keep the bot strictly single-purpose.
- Describe it accurately as a verification service that cites fact-checkers, never as "ask our AI
  anything".
- Add a human escalation path and a contact in the profile.
- Never let WhatsApp data train a model. Anthropic's API does not train on inputs by default
  (general knowledge; check the current commercial terms).
- Keep Telegram and the web page primary, so that losing WhatsApp loses a channel, not the
  product.
- Optionally, ask a BSP account manager or Meta support for a written view before investing build
  time.

Confidence: medium. This is a judgement on an undefined standard.

### Technical requirements

**W20 — Webhooks: handshake, signature, retries, duplicates.**
- **Handshake:** Meta sends `GET ?hub.mode=subscribe&hub.challenge=…&hub.verify_token=…`. If the
  verify token matches yours, reply 200 with the `hub.challenge` value.
- **Events:**
  - Each event POST carries `X-Hub-Signature-256: sha256=<hash>`. The hash is an "HMAC-SHA256
    hash, calculated using the post body payload and your app secret as the secret key".
    Compute it over the raw bytes before parsing, and compare in constant time.
  - Reply 200 if valid, non-200 if not.
  - A valid TLS certificate is required ("Self-signed certificates are not supported"). A
    cloudflared URL qualifies. mTLS is optional.
  - A POST can batch up to 1,000 updates (not guaranteed), and payloads can be up to 3 MB.
- **Retries:** Meta retries "with decreasing frequency until the request succeeds, for up to
  7 days", and "These retries can result in duplicate webhook notifications".
- **For this codebase (invariant 5):**
  - Dedupe on the message id (`wamid`) before any paid work.
  - Acknowledge with 200 at once and run the check asynchronously, or a slow handler causes
    retries and double spending.
  - Subscribe to the `messages` field (needs `whatsapp_business_messaging`) under App Dashboard >
    Use cases > Customize > Configuration.
  - Keep the app in Live mode (W8).

Sources: .../webhooks/create-webhook-endpoint.md and .../webhooks/overview.md (fetched
2026-10-15). Confidence: high.

**W21 — Media: the webhook id gives a 5-minute URL, which needs an authenticated GET.**
- Flow: `GET /MEDIA_ID` with the token returns a URL. Download it with `Authorization: Bearer`
  ("If you omit your token, the request will fail").
- "Media URLs expire after 5 minutes". Media ids from webhooks stay downloadable for 7 days. On a
  404, fetch a fresh URL, then renew the token.
- Size caps:
  - Audio (AAC, AMR, MP3, M4A, OGG "OPUS codecs only … mono input only"): 16 MB.
  - Image (JPEG, PNG): 5 MB.
  - Video (MP4 or 3GPP, H.264 with AAC): 16 MB.
  - Document: 100 MB.
  - Sticker (WebP): 100 KB static, 500 KB animated.
  - "The maximum supported file size for media messages on Cloud API is 100MB". Larger inbound
    files arrive as a webhook with error code 131052.
- WhatsApp voice notes are OGG/Opus, the format the Telegram path already sends to Sarvam ASR.
- Apply the project's own size and duration caps before downloading or transcribing.

Source: .../business-phone-numbers/media.md (fetched 2026-10-15). Confidence: high.

**W22 — Text, formatting, typing indicator and read receipt.**
- **Text:**
  - The text body is limited to "Maximum 4096 characters", so split longer answers.
  - "The WhatsApp client automatically hyperlinks URLs in the body text". As on Telegram,
    invariant 3 means stripping URLs from the model's prose and sending sources only from
    structured fields.
  - `preview_url` previews only the first URL.
  - The page does not document formatting. WhatsApp's own syntax (`*bold*`, `_italic_`,
    `~strike~`, ```` ```mono``` ````) is general knowledge and was not verified here.
- **Typing indicator and read receipt:**
  - Send `POST /<PHONE_NUMBER_ID>/messages` with
    `{"messaging_product":"whatsapp","status":"read","message_id":"<wamid>","typing_indicator":{"type":"text"}}`.
    The one call marks the message as read and shows "typing".
  - "dismissed once you respond, or after 25 seconds, whichever comes first", so re-send it during
    a 30–90 s check. An interim text message would be billable.
  - Show it "only if you are going to respond".

Sources: .../messages/text-messages.md and .../typing-indicators.md (fetched 2026-10-15).
Confidence: high.

**W23 — Inbound message types and forwarded flags: only partly verified.**
- The messages webhook reference says that undeliverable inbound types arrive with
  `type: "unsupported"`, and that senders are identified by `from` and `wa_id`. Each type has its
  own reference page, and those pages were not read.
- `context.forwarded` / `context.frequently_forwarded` and the audio `voice: true` flag exist
  according to general knowledge of the Cloud API. **No page read today confirms them.**

Source: .../webhooks/reference/messages.md (fetched 2026-10-15). Confidence: low for the flags.

### Alternatives

**W24 — Twilio.**
- The sandbox shares the number +14155238886. Users join by sending "join <code>", and the session
  expires after 3 days.
- It handles text and media inside the 24-hour window, at 1 message every 3 seconds, with 3 fixed
  templates.
- It is "testing and discovery purposes only". Messages are billed at standard Twilio rates, and
  trial accounts get 100 free WhatsApp messages.
- Production needs your own sender through WhatsApp Self Sign-up, which uses the same Meta
  portfolio, WABA and Terms underneath. Twilio adds its own fee per message, inbound and
  outbound; USD 0.005 is general knowledge and was not verified.

Source: twilio.com/docs/whatsapp/sandbox (last modified 2026-08-19). Confidence: high for the
sandbox, medium for the fee.

**W25 — Indian BSPs: their fees sit on top of Meta's, plus 18% GST. They help with onboarding,
not eligibility.**
- **Gupshup** (self-serve): a flat USD 0.001 per message in both directions, plus Meta at actual
  cost, from a prepaid USD wallet. No monthly plan.
- **AiSensy:** about INR 999–1,500 a month for the basic plan (Pro about 2,399). It lists India
  utility at INR 0.145.
- **Interakt:** about INR 999 a month historically. It claims to pass Meta's charges through;
  third parties estimate a markup of about 12%.
- **WATI:** about INR 2,499–2,999 a month for the entry tier, with about 20% markup on
  utility/authentication.
- All of them ask for the same Udyam/GST/PAN documents, and some insist on GST. A
  partner-assisted verification can unlock the 2,000 tier (W5), but none can verify an
  unregistered individual. All are bound by section 4.7.

Sources: a WebSearch on 2026-10-15 (the gupshup.ai self-serve pricing page, AiSensy's
December 2025 notice, interakt.shop, the codingclave.com and richautomate.in 2026 audits, and
help.tallysolutions.com). Confidence: low-medium on prices, which are vendor-reported and
conflicting.

## Access routes compared

| Route | Monthly cost (reply-only, this volume) | Fits? | For | Against |
|---|---|---|---|---|
| Meta Cloud API, **test number** | INR 0 | Development only | Free today; real webhooks, media and typing; no number or company needed | At most 5 allowlisted recipients; cannot serve the public |
| **Meta Cloud API direct, own number, unverified portfolio** | INR 0 for ≤1,000 service messages per number; then INR 0.115 each + GST; plus a SIM recharge | **Yes (recommended)** | Cheapest; no middleman; replies do not use the 250 limit; no App Review; existing FastAPI + cloudflared can host the webhook | Card on file; privacy policy + Live app; dedicated number; you run the infrastructure; section 4.7 risk |
| Same + Meta business verification (Udyam sole proprietorship) | Same (Udyam is free) | Yes, later | 2 → 20 numbers, 2,000+ limit, smoother display-name review, credibility | Registered-business documents with an exact name match; about 7 business days; not needed for replies |
| Twilio (Self Sign-up; sandbox for tests) | Meta fees + about USD 0.005 per message each way (unverified): about USD 10–15 for 1,000 checks | Possible, not better | Good docs; sandbox works with no Meta setup | USD billing; fee on inbound too; same verification and section 4.7; sandbox has 3-day joins and is not for production |
| Gupshup self-serve | Meta at cost + USD 0.001 per message: about USD 2–3 for 1,000 checks | Possible | Smallest markup; Indian; onboarding help | Prepaid USD wallet; extra hop; may ask for GST; same section 4.7 |
| AiSensy / Interakt / WATI | INR 999–3,000 a month + 3–26% markup | Poor | No-code inbox; onboarding help | Built for marketing broadcasts; the plan fee dwarfs Meta's; may ask for GST; same section 4.7 |
| Unofficial WhatsApp Web automation (personal number) | INR 0 | **No** | No Meta setup | Breaks WhatsApp's Terms and risks a number ban (general knowledge; listed only to rule it out) |

## Start TODAY: the slow items, in order

1. **Get the dedicated number.** Buy a new prepaid SIM (KYC'd in your name) that has never been
   on WhatsApp, or delete the WhatsApp account on a spare number. Keep it recharged, because
   losing the SIM means losing the OTP when the number is re-verified (W3).
2. **Choose the business name, and register it on Udyam as a sole proprietorship** if
   verification is wanted. It is free and online with Aadhaar and PAN. Use exactly the name that
   will go into Meta's portfolio and onto the website, since an exact match is required (W6).
3. **Publish a privacy policy (and terms) on the public site.** Meta needs one before the app
   can go Live (W8), and policy-legal.md needs one anyway.
4. **This afternoon, for free:**
   - Create the Meta developer account, the app (WhatsApp use case), the business portfolio (in
     the chosen name) and the WABA, with currency **INR** (W10).
   - Allowlist up to 5 test phones and build the webhook against the test number (W1, W2, W20).
     Do not run any paid check without asking.
5. **Add a card in Billing Hub.** Without one, replies stop after the 1,000 free service
   messages (W11).
6. **Set up credentials.**
   - Create a System User and a long-lived token. Keep the app secret for signature checks and
     store both only in `.env`.
   - Add the WhatsApp provider to `scripts/fake_stages.py` and neutralise its credential
     (CLAUDE.md money rules, invariant 9) (W7).
7. **Design in the human escalation path** and a contact line for the profile (W17). Keep
   triage's refusals so the bot stays single-purpose (W19).
8. **Put the number into production.** Add the real number (OTP), register it with a two-step
   PIN, set a display name that matches the site, and switch the app to Live (W3, W4, W8).
9. **Start Meta business verification once the Udyam certificate exists**, which takes about
   7 business days. It is optional for launch (W6).
10. *(Optional)* Ask a BSP account manager or Meta support for a written view on section 4.7 for
    this use case before investing build time (W19).

## Unknowns

1. **How Meta will classify this bot under section 4.7.** It is Meta's "sole discretion", and Meta
   has published no examples. Only Meta can answer this (W19).
2. **The 1,000 allowance and the stop without a card** were read through the search index's copy
   of Meta's pricing page (dated 2026-09-30) plus 360dialog, not from a direct fetch. WebFetch
   returned a stale copy (W11).
3. **The forwarded flags and the `voice` flag** on inbound webhooks are not verified (W23).
4. **Throughput:** Meta's per-number messages-per-second limit was not checked (80/s is general
   knowledge). It does not matter at this volume.
5. **The display-name guidelines** text was not read (W4).
6. **The India document list** for business verification comes from vendors that reproduce Meta's
   list. Meta's live list appears in Security Center (W6).
7. **GST on Meta's INR invoices:** vendors say 18%. Not checked on a Meta page.
8. **The EU General Court appeal** (filed August 2026) has no outcome yet. **Brazil's** sequence
   after the January 2026 suspension is unclear. There is no Indian proceeding (W15).
9. **The Twilio per-message fee and all BSP prices** are unverified or vendor-reported and
   conflicting (W24, W25).
10. **Coexistence** (keeping the WhatsApp Business app and the API on one number) was not checked
    for availability to direct developers in India (W3).
11. **The Quint's bot's model and hosting route** (official API through Meedan or otherwise) are
    not stated, so how far it works as a precedent is uncertain (W18).
