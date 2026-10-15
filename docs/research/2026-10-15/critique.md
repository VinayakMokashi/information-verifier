# What was missing — the critic's gaps, and the ones closed (2026-10-15)

A critic read every research result and audit (with verdicts) and listed what
was missing, contradictory or unresolved that could change one of the four
decisions; up to four of the gaps not needing Vinayak were then closed by
further research or free repo checks. Written before Vinayak decided; his
decisions are in decision-brief.md and PROJECT_PLAN §7. Durable copy of the
workflow's output (its raw journal is session-internal).

## The gaps (10)

### G1. Nobody measured how available the home 'PC' really is, and it is a laptop: an HP ENVY x360 13-ay1xxx convertible with a battery (ChassisTypes 31). The Windows event log, read-only on 2026-10-15, shows for the last 30 days:
- 104.7 h asleep. That includes one 74.3 h sleep (15 Sep 14:51 to 18 Sep 17:09) and one of 18.9 h (18-19 Sep).
- A 9.9 h sleep on 23 Sep that ended in a failed Modern-Standby resume: Kernel-Power 41 with ConnectedStandbyInProgress=true, then the power button.
- A sudden power loss or hard hang on 13 Sep, down about 22 h (no bugcheck, no button, not in standby).
- A Windows-Update forced restart on 20 Sep at 11:41, just after active hours (18:00-11:00) ended.
- Repeated switches between AC and battery on 21-22 Sep, so it is unplugged and moved.
That is about 85% availability. Only since the 29 Sep boot, when the bot went live, has it stayed up: 16.7 days with about 1.5 h asleep. Updates are paused only until 2026-10-25, so a forced restart is due within about 10 days.
*Decision: hosting · closable by: owner-question*

**Why it matters.** home-tunnel's case for shape H assumes a machine that stays on, with reboots only now and then. This machine is used as a laptop. What a 74 h outage would do:
- The site and API show Cloudflare errors.
- Telegram discards bot updates older than 24 h, so those users are never answered.
- A WhatsApp webhook would come back after the free 24 h reply window had closed, so only a paid, pre-approved template could reply.
- In-flight checks are billed and lost (OPS-04).
This is the single fact that most changes home versus cloud. It also decides whether the ytdlp result's $0 fix for a cloud host (route link traffic through the home PC) is viable at all.

**How to close.** Ask Vinayak:
1. Can this laptop stay at home, plugged in and never sleeping, for months? That means lid open or lid action set to 'do nothing'. Or does he carry it (college, travel)?
2. What caused the 13 Sep (22 h) and 23 Sep outages: a power cut, the battery running out, or did he put it to sleep?
3. How often does the power go out, and are the router and ONT on an inverter or UPS?
4. Does he accept the battery wear of charging a convertible 24/7? HP's BIOS battery-care option can cap the charge.
Then re-run the same read-only event-log queries in two weeks (Power-Troubleshooter event 1 for sleeps; Kernel-Power 41/6008/1074 for crashes and restarts) to see whether the post-29-Sep pattern holds.

### G2. Sources contradict each other on whether Meta's §4.7 'AI Providers' ban shuts this bot out in India. This is a conflict, not just a missing check.
- policy-legal F4 and limits-budget F4 say India has no route, and that Brazil is the only market still listed.
- Business Today (14 Jul 2026) reports ChatGPT back on WhatsApp in the EEA, citing OpenAI's own post. Its reporter wrote 'we can also access the feature in India'.
- The unfinished WhatsApp research (whatsapp.md, W-log-1) says Meta's EEA arrangement ended 2026-05-12.
The regulatory leads the dead WhatsApp agent was chasing are unread: the EU interim measures and Meta's appeal, the lifting of CADE's block in Brazil, and any CCI case. No result asks whether a business that deploys someone else's LLM for one narrow purpose counts as an 'AI Provider' at all. The app's own system prompt scopes it to check 'Anything … from anywhere in the world' (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/chat_prompts.py:52-56). That breadth is what Meta would judge as 'primary functionality'.
*Decision: whatsapp · closable by: research*

**Why it matters.** It decides whether decision 4 is 'start Meta onboarding today' or 'don't invest in WhatsApp yet'. Both results call §4.7 the biggest launch risk. If general-purpose AI bots are in fact reachable from India in 2026, the risk is far smaller. If Meta judges by the bot's scope, the WhatsApp surface may have to be narrowed (claims only, vetted fact-checks first) before Meta will allow it. Either way the build plan changes.

**How to close.** Free, one minute: from an Indian WhatsApp account, message 1-800-CHATGPT (+1 800 242 8478) and see whether it answers.

Research:
1. Re-fetch today's text of WhatsApp Business Solution Terms §4.7 and Meta's AI Providers pricing page, including its market list.
2. Find the status of the EU interim-measures appeal, of CADE (see the slaughterandmay and mlex leads in C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/rerun/leads_whatsapp.txt) and of any CCI complaint.
3. Look for precedent: are Indian AI-assisted fact-check tiplines on the Business Platform still running after 2026-01-15? Candidates: The Quint's WhatsApp AI chatbot, the MCA deepfakes helpline, and the Meta/IFCN-funded DFRAC project.

Then ask the owner whether he would accept a narrower WhatsApp scope if that is the price of approval.

### G3. WhatsApp replies are no longer free, but the research says they are. Meta's non-template-messages page, fetched 2026-10-15, says 'Effective October 1, 2026, Meta will charge on a per-message basis for service messages'. Rates are 'the same as the rates for utility and authentication messages', with no volume tiers and no stated free allowance. limits-budget F5, its option table and PROJECT_PLAN §11's WhatsApp notes ('user-initiated service replies are free') all predate this.

Two things nobody has priced:
1. The India rate. About ₹0.115 per message according to a third-party summary; Meta's own India rate card has not been read.
2. Messages sent per check. The existing bot (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/telegram_bot.py) sends at least two: 'Checking…' at :708 and the answer at :748. A long check adds two more (:739, :678-679). Every small-talk reply, cap refusal or unsupported type gets one.
*Decision: whatsapp · closable by: research*

**Why it matters.** Per check the cost is small, about ₹0.23-0.46, or 4-9% on top of the $0.066 average. The bigger problem is that every reply is billed, including replies that buy no check: the 'hi' that triage answers for free, the 'daily limit reached' refusal, and cache hits. The 5-a-day check cap therefore bounds none of the WhatsApp message spend. One number sending 1,000 messages costs about ₹115 unless the bot stops answering it. The budget needs a per-number reply cap and its own WhatsApp line, and the WhatsApp bot should send one message per check, not 'Checking…' plus the answer.

**How to close.** Read Meta's current India rate card for the INR utility and authentication rates and any free-tier wording. It is linked from developers.facebook.com/documentation/business-messaging/whatsapp/pricing; the scontent CSV/PDF links in leads_whatsapp.txt carry expired tokens. Cross-check against the 360dialog and ycloud October-2026 notes in the same leads file. Then correct limits-budget F5 and the PROJECT_PLAN §11 WhatsApp notes, and add per-number reply caps to the limits design.

### G4. No result knows the owner's all-in monthly ceiling in rupees, or how he can pay. Every item is priced on its own, in pre-tax USD.
- A $1.50/day API budget is about $45 a month, roughly ₹4,000 before the card's 2-3.5% forex markup. That is over 5 times the recommended ₹730 host and about 50 times the ₹75/month domain. So the ceiling decides affordability, not the host.
- API credits still appear to be sold in USD by card only. Rupee pricing reached Claude subscriptions in July 2026, not Console credits, according to third-party reports. Whether his receipts show GST is unknown.
- Recurring USD auto-charges on Indian cards fail without an RBI e-mandate. cloud-hosting checked that risk for Railway and Fly only. It did not check Cloudflare Registrar's yearly renewal, DigitalOcean, the proxy vendors, or Meta's WABA billing, which must be in INR by 2026-12-31 (W-log-3).
*Decision: budget-limits · closable by: owner-question*

**Why it matters.** Several choices follow from two facts only the owner has:
- The L1 daily dollar budget.
- The L0 backstops: the workspace spend limit and a prepaid balance with auto-reload off.
- The host. AWS India bills in INR with UPI AutoPay; DigitalOcean bills in USD.
- Where to buy the domain. A .com bought from an Indian registrar in INR and pointed at Cloudflare avoids a USD renewal.

**How to close.** Ask Vinayak:
1. The most he will spend per month, all-in, in rupees.
2. What he pays with. Credit or debit card, and is it enabled for international payments and e-mandates? UPI? PayPal? Has a recurring foreign charge ever renewed on it?
3. How he buys Anthropic credits today, whether auto-reload is on, and whether his last receipt shows GST or forex charges (Console > Settings > Billing).
Then restate the L1 budget and the L0 limits in rupees.

### G5. The hosting shortlist is ranked on 'in India, nearest the users', which barely matters for this app. A check runs 30-295 s, dominated by Claude calls served from outside India, so an Indian host saves a fraction of a second.

The shortlist misses three things that change cost and risk:
1. Lightsail's own pricing page says 'As part of the AWS Free Tier, you can get started with Amazon Lightsail for free'. Secondary summaries of AWS's free-tier page give 90 days on the $5/$7/$12 Linux bundles, one bundle per account. cloud-hosting charges the $7 Mumbai plan from month one.
2. This PC already has the Google Cloud SDK signed in to the owner's Gmail, with project 'harvard-mlops'. So he has a Google Cloud account; whether billing is enabled is unknown.
3. Docker Desktop 29.8.1 is installed, although CLAUDE.md says Docker is not. That means the Deno + curl_cffi + ffmpeg image the ytdlp result requires can be built and tested here.
*Decision: hosting · closable by: research*

**Why it matters.** The deciding unknown for any cloud host is whether its datacenter IP gets bot-walled on reels, which are a core requirement. The ytdlp result says only a probe from that host, repeated over days, can tell. A free trial makes that measurement cost $0 on the exact recommended host, before he commits money or builds the residential-proxy paid seam. An existing Google Cloud billing account would also settle the Indian-card question for that provider.

**How to close.** Research the Lightsail trial's current terms on AWS's free-tier page, and whether an AWS India (AISPL) account qualifies. AISPL is the INR-billing entity that cloud-hosting relies on. Ask the owner whether his Google Cloud account has billing or credits, and whether harvard-mlops is his own project or a course's: a public service should not run on course credits. If a trial applies, run link_probe.py from the trial host daily for a week before choosing. It now reports the app's own resolve_link verdict.

### G6. The 'start today' list for WhatsApp depends on facts the unfinished WhatsApp research never reached (its source trail stops at these searches) and on things only the owner has:
- Can an individual with no registered business pass Meta Business Verification in India, and with which document? Udyam registration is free and online for a sole proprietor.
- What can an unverified number do: reply to user-initiated chats, within which messaging limit, and with what display-name review?
- Does the owner have a SIM never registered on WhatsApp to dedicate to this?
- Will he be named publicly as the business, as the operator in the privacy notice, and as the DPDP grievance contact?

W-log-3 adds a hard rule: India WABAs must bill in INR by 2026-12-31, or delivery stops on 2027-01-01. So the currency should be chosen when the account is created.
*Decision: whatsapp · closable by: owner-question*

**Why it matters.** Business verification is the slow step (§11 B: 'start it early'). Starting with the wrong entity, the wrong currency or his personal number costs weeks or forces a migration. The answers turn 'start today' into concrete steps:
- Create the Meta Business portfolio, billed in INR.
- Register Udyam if verification needs it.
- Buy the SIM.
- Build against Meta's free test number (5 recipients) in the meantime.

**How to close.** Ask Vinayak:
1. Does he have a spare number, or will he buy a new SIM?
2. Does he have any business registration (Udyam, GST, shop licence), or is he willing to get Udyam?
3. Is he OK publishing his name and an email as the operator?

Then research, from the dead agent's leads in C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/rerun/leads_whatsapp.txt (the business-phone-numbers, display-names, messaging-limits, get-started and app-review pages): which verification documents Meta accepts from Indian sole proprietors, and what an unverified WABA may send.

### G7. No Claude call carries a per-person identifier: a grep of app/ finds no `metadata` or `user_id`. That includes the vision call, which sends any stranger's image straight to the API (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/providers/vision.py). The Messages API reference, fetched 2026-10-15, defines metadata.user_id as an opaque id, a uuid or hash and never a name, email or phone number, that 'Anthropic may use … to help detect abuse'. Without it, all strangers' abuse is attributed to the owner's organization. limits-budget's 'dedicated workspace' separates spend, not enforcement. No result asks what happens to the organization, and to the owner's own API use, if strangers submit prohibited content, for example deliberately to get the key banned.
*Decision: pre-public-fixes · closable by: research*

**Why it matters.** A suspension would take down the web page, both bots and his own testing at once, which is worse than any cap. The fix is cheap but belongs on the pre-public list: put a hash of the per-person key the limits design already introduces into metadata.user_id on every call. That key is the Telegram user id, a hashed WhatsApp number, or the Turnstile cookie id. It also raises a design question: should the public deployment live in a separate Anthropic organization rather than just a separate workspace?

**How to close.** Research Anthropic's operator obligations for consumer-facing API apps (the Usage Policy and safeguards guidance), and whether enforcement acts per organization or per workspace or key. Add the user_id change to the pre-public list. It is testable for free with the existing fakes: assert that every messages.create carries an opaque metadata.user_id and never a raw phone number. Ask the owner whether a separate organization for the public key is acceptable.

### G8. Under shape H, strangers' inputs would be processed on the owner's daily personal laptop, inside his own Windows session. No result weighed this.
- yt-dlp fetches whatever a stranger links to.
- ffmpeg and ffprobe parse strangers' audio and video.
- start.ps1 runs the app and bot as his own user, so the process can read everything his account can: the .env with every API key, his browser profiles, and the Google Cloud SDK signed in as his Gmail (observed 2026-10-15).
The security audit covered network exposure only: SSRF, CSRF and the dashboard gate. On a cloud host the same compromise would cost a $7 VM.
*Decision: hosting · closable by: owner-question*

**Why it matters.** This is a home-versus-cloud factor that the cost comparison leaves out. If H is chosen, it also changes how H must be set up: app, bot and tunnel should run under a separate low-privilege local account, started by Task Scheduler at boot. OPS-21 and OPS-22 already need that setup. Docker Desktop is installed, but it starts at sign-in, not at boot, so on its own it does not meet the restart-without-login requirement.

**How to close.** Ask Vinayak whether he banks, studies or keeps credentials on this laptop, and whether he accepts strangers' media being parsed there. If H is chosen, record in PROJECT_PLAN §7 that the services run under a separate local account. Then check (free) that this account cannot read %APPDATA%\gcloud, his browser data or anything outside the repo apart from the .env it needs.

### G9. Two results conflict on whether to keep logs.
- The ops audit (OPS-11) makes this a pre-public fix: stop logging visitor IPs and job ids (--no-access-log) and keep host logs for 30 days or less, in line with invariant 10.
- policy-legal reports that DPDP Rule 8(3), in force from 13 May 2027, requires keeping 'personal data, associated traffic data and other logs of the processing' for at least a year. It also left open whether CERT-In's 2022 directions bind an individual running a public service: they require a rolling 180 days of ICT logs and incident reports within 6 hours.
Neither claim was verified: policy-legal.verification.md stops at 'status: in progress'.
*Decision: pre-public-fixes · closable by: research*

**Why it matters.** What the app logs, for how long and where is being decided now: in OPS-11's fix, in the privacy notice's retention promise, and in the backup design (OPS-10). A notice that promises '30 days, no IPs' could be false from day one under CERT-In, or from May 2027 under DPDP. The likely answer is a separate content-free log with hashed IPs, keeping messages at 30 days. That needs deciding before the privacy notice is written.

**How to close.** Verify against the primary texts:
- CERT-In's directions of 28 Apr 2022 and its FAQ: who counts as a 'service provider' or 'body corporate', and whether logs must stay in India.
- DPDP Rules 2025, Rule 8(3) with the Seventh Schedule: does a free service run by an individual have to keep message content, or only processing logs?
Then record the logging and retention design in PROJECT_PLAN §7 before the privacy notice is drafted, and adjust OPS-11's fix to match.

### G10. The identity scheme assumes Google Sign-In and Turnstile work where Indian visitors actually open the link: inside WhatsApp's, Instagram's and Facebook's in-app browsers.
- Google has refused OAuth from embedded WebViews since 30 Sep 2021 (403 disallowed_useragent), and Instagram and Facebook in-app browsers are documented to hit this.
- WhatsApp on Android has opened some links in its own in-app browser since 2025. Whether that is a WebView or a Custom Tab is unknown.
- How Turnstile in managed mode behaves inside these webviews on low-end Android is unmeasured.
limits-budget only suggests offering 'open in Chrome' after a failure.
*Decision: budget-limits · closable by: owner-question*

**Why it matters.** If sign-in fails for most visitors, the 'Google Sign-In for 10 checks' tier serves almost no one. Per-person limits would then rest on a cookie that a webview may not keep. In that case the better per-person key is the messaging identity (Telegram user id, WhatsApp number), which changes which identity tiers to build and in what order.

**How to close.** Ask the owner for a 5-minute free test on his Android phone. Put a test page behind the tunnel with a real free Turnstile widget (the always-pass test sitekey would prove nothing) and a Google sign-in button. Send its link to himself in WhatsApp, and paste it into an Instagram DM. Record:
- whether Turnstile passes;
- whether sign-in returns 403;
- whether the page's cookie survives reopening.
The usual workaround is to spot the 'wv' token in the user agent and offer 'Open in Chrome' before asking anyone to sign in.

## Closed (4)

### Sources contradict each other on whether Meta's §4.7 'AI Providers' ban shuts this bot out in India. This is a conflict, not just a missing check.
- policy-legal F4 and limits-budget F4 say India has no route, and that Brazil is the only market still listed.
- Business Today (14 Jul 2026) reports ChatGPT back on WhatsApp in the EEA, citing OpenAI's own post. Its reporter wrote 'we can also access the feature in India'.
- The unfinished WhatsApp research (whatsapp.md, W-log-1) says Meta's EEA arrangement ended 2026-05-12.
The regulatory leads the dead WhatsApp agent was chasing are unread: the EU interim measures and Meta's appeal, the lifting of CADE's block in Brazil, and any CCI case. No result asks whether a business that deploys someone else's LLM for one narrow purpose counts as an 'AI Provider' at all. The app's own system prompt scopes it to check 'Anything … from anywhere in the world' (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/chat_prompts.py:52-56). That breadth is what Meta would judge as 'primary functionality'.
*Confidence: medium*

RESUME CHECK: Before doing anything I checked what was already saved. whatsapp.md (W-log-1 to W-log-27), policy-legal.md F4 and limits-budget.md F4 are all in docs/research/2026-10-15/. Nothing from the killed attempt at this gap had been saved, so this run started fresh and kept its findings in scratch as it went (scratchpad/gap_ai_providers/notes.md). It used 13 web calls and no paid calls. I did not modify the repo.

BOTTOM LINE: Read precisely, the sources mostly don't contradict each other on India. What the briefs got wrong is the EEA, plus one overclaim about our own bot.
(a) The EEA was not closed again on 2026-05-12. Only Meta's charge ended then. Access in the EEA and Italy is now free, because regulators ordered it.
(b) India still has no legal route. Business Today's line that "we can also access the feature in India" has nothing behind it.
(c) The question that actually decides this is whether our bot counts as an "AI Provider" at all. That depends on its scope, and today its scope is broad.
So the risk is no smaller than the briefs said. But it now has a lever we control: narrowing the scope.

FINDINGS (DC = decision-critical):

DC1. Meta's AI Providers pricing page (fetched 2026-10-15) says "updated as of May 12, 2026". It applies where "Meta is legally required to support AI Providers' usage". The markets listed are:
- Brazil (+55): from 2026-03-11, no end date.
- 29 EU/EEA countries: 2026-03-11 to 2026-05-12.
- Italy (+39): 2026-02-16 to 2026-05-12.
The page then says "Effective May 13, 2026 ... Meta will no longer charge" in the ended markets. It says nothing about access ending, and it does not mention India. So whatsapp.md W-log-1, read as "the EEA arrangement ended", is a misreading: the charge ended, not the access. policy-legal F4 ("Brazil is the only market still listed") is correct only in the sense that Brazil is the only market still being charged.

DC2. EU: the Commission's interim measures of 2026-06-09 (case AT.41034, Art. 8 of Reg. 1/2003) ordered Meta to restore FREE access for rival AI assistants, on the terms in force before 2025-10-15, within 5 working days.
- Meta appealed to the General Court in August 2026 (Slaughter and May page dated 2026-08-25).
- I found no case number, no request to suspend the order and no hearing date. An appeal does not suspend the order by itself.
- Meta has complied: OpenAI's release note of 2026-07-13 says "ChatGPT is available again on WhatsApp in the European Economic Area (EEA)" and "Availability is based on the country code associated with your WhatsApp number".
- Italy is covered separately by AGCM's interim order of December 2025.

DC3. India: no route.
- Business Today (2026-07-14, byline "Business Today Desk", Noida) adds "we can also access the feature in India". The only source it gives is OpenAI's post, which says "in the EEA". OpenAI's own help page returned 403 to my fetcher.
- I found no CCI complaint or case about the AI-chatbot terms (searched 2026-10-15). CCI's only live WhatsApp matter is the 2021 privacy-policy case. This is absence of evidence, and CCI's own case list was not checked.
- Brazil, for context: CADE's Tribunal unanimously upheld its preventive measure on 2026-03-04. CADE's Superintendence fined Meta R$250k a day from 2026-03-17, and the Tribunal confirmed that on 2026-04-23. A federal court in São Paulo suspended the fine on 2026-04-29 (SEI 08700.012397/2025-63). I found nothing from August to October 2026.
- Even if 1-800-CHATGPT answers a +91 number, that would only show Meta isn't enforcing the ban for OpenAI in India. It would not change the text of §4.7. It's worth the free minute anyway: if it answers, that's real evidence Meta doesn't block by country code in India; a refusal confirms the ban.

DC4. The Terms (re-fetched 2026-10-15, "Last Modified: September 23, 2026"), §4.7:
- It covers "providers and developers of artificial intelligence or machine learning technologies" (LLMs, generative AI platforms, general-purpose assistants).
- They are "strictly prohibited" from the platform "when such technologies are the primary (rather than incidental or ancillary) functionality being made available for use", and Meta decides that "in its sole discretion".
- Two exceptions: the country list (DC1), and "you may retain an AI Provider as your Solution Provider", provided WhatsApp data is never used to train AI models.
- Meta's stated intent (TechCrunch, Oct 2025): businesses using AI to serve their customers, such as a travel company's support bot, are unaffected; the targets are general-purpose assistants.
- So the test is not "do you use someone else's LLM". It is "is AI the main thing the number offers". A business deploying Anthropic's model is not automatically an AI Provider. But a bot whose whole product is LLM-written answers to anything is the edge case.

DC5. The repo check shows our bot is broad today, which weakens W-log-27's "cannot be used as a general chatbot".
- app/engine/chat_prompts.py:51-56 says "You check whether things people send you are true. Anything: ... a claim about history, science, money, technology or a public figure — from anywhere in the world".
- app/engine/triage.py:8-12 is "Deliberately narrow": it refuses only a WHOLE message that is a greeting, a thanks, an acknowledgement, or has no letters or digits.
- chat_prompts.py:72-74 tells the model only to stop on "an opinion, a joke, a greeting, a matter of taste". No rule turns away task requests ("write an essay", "explain X").
- Read by Meta, that looks closer to "LLM answers are the primary functionality" than a fact-check tipline does. This is an inference from the code; I made no paid run.

DC6. Precedent in India: The Quint launched a "conversational AI-driven bot" built with Meedan on WhatsApp +91-8826811818 on 2026-05-04, after the 2026-01-15 ban took effect.
- It is narrow: it answers news and fact-check questions from its own archive (about 200 recent stories), text only, and alerts its journalists when it can't answer.
- I found no 2026 status for the MCA Deepfakes Analysis Unit tipline (+91 9999025044; all sources are from its 2024 launch), and no WhatsApp tipline for DFRAC at all.
- Meedan Check tiplines match claims against existing fact-checks and send the rest to humans. Nothing found shows any of them being hit by §4.7.
- So narrow, grounded, human-backed AI tiplines do run in India in 2026. I found no open-scope LLM verifier that does.

WHAT IT CHANGES (decision 4): don't start Meta onboarding for the bot as it is scoped today. Make the WhatsApp surface a separate, narrower product before investing:
- claims and forwards only, with a refusal for task or general requests;
- vetted fact-checks first (Google Fact Check and the whitelist), with answers grounded in cited sources;
- a human or contact escalation path in the profile;
- presented as a fact-check tipline, not "ask our AI".
Then ask a BSP (Gupshup or Twilio) or Meta for a written pre-check. Meanwhile run the free one-minute test (message +1 800 242 8478 from an Indian WhatsApp number and note the reply verbatim). Keep Telegram and the web as the main surfaces.

QUESTION FOR THE OWNER (I could not ask him; please relay): "Meta judges by what the WhatsApp number mainly offers. Our checker today takes 'anything, from anywhere'. Would you accept a narrower WhatsApp version — forwarded claims only, vetted fact-checks first, a polite refusal for anything else, and a contact for a human — if that is the price of Meta allowing it? Telegram and the website would keep the full version."

FLAGS: EU dates come from law-firm and news reporting; I did not read the Commission's decision text. OpenAI's help page could not be fetched (403); the release note was read via the releases.sh mirror of help.openai.com/en/articles/6825453. CADE's status after May 2026 and the DAU tipline's status after 2024 are unknown.

**Changes the decision?** Yes. Decision 4 changes from "start Meta onboarding today" to "don't onboard the bot as scoped today". If the owner agrees, build a narrower WhatsApp version (claims only, vetted fact-checks first, refusal of general requests, human contact), get a BSP's or Meta's pre-check in writing, then onboard. The briefs also need two corrections: the EEA was not closed again on 2026-05-12 (only the charge ended; access is free under the EU order of 2026-06-09), and India's lack of a regulatory route is confirmed. The risk is still Meta's sole-discretion "primary functionality" test, now tied to our scope (chat_prompts.py:51-56), not to India's market listing. That makes WhatsApp a narrower product, not a dead one. The free 1-800-CHATGPT test from a +91 number is worth running but cannot change the §4.7 text.

Sources: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers (fetched 2026-10-15; 'updated as of May 12, 2026') · https://www.facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform (fetched 2026-10-15; 'Last Modified: September 23, 2026', s.4.7) · https://www.slaughterandmay.com/recent-work/meta-on-its-appeal-against-the-european-commission-s-whatsapp-interim-measures-decision/ (2026-08-25) · https://releases.sh/release/rel_xGE4yrUcXo3nCBBYTksF8-chatgpt-available-again-on-whatsapp-in-eea (mirror of help.openai.com/en/articles/6825453#chatgpt-returns-to-whatsapp-in-the-eea, 2026-07-13) · https://www.businesstoday.in/technology/news/story/chatgpt-makes-a-comeback-on-whatsapp-everything-users-need-to-know-542721-2026-07-14 (2026-07-14) · https://www.steptoe.com/en/news-publications/stepahead-antitrust-and-competition-insights/must-meta-open-whatsapp-to-competing-ai-assistants.html (search summary: AT.41034, 2026-06-09 order) · https://www.morningstar.com/news/dow-jones/202606095919/meta-gets-eu-antitrust-order-to-open-whatsapp-to-rival-ai-chatbots-update (2026-06-09) · https://lefosse.com/newsletter/cade-confirma-descumprimento-de-medida-preventiva-no-caso-whatsapp-business-e-mantem-multa-diaria-de-r-250-mil/ (search summary, Apr-May 2026) · https://tecnoblog.net/noticias/tribunal-do-cade-mantem-decisao-que-permite-ias-concorrentes-no-whatsapp/ (2026-03-04, search summary) · https://globalcompetitionreview.com/article/metas-whatsapp-ai-policy-faces-fresh-antitrust-scrutiny (search result; no CCI action found) · https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/ (2025-10-18, Meta's stated intent) · https://www.thequint.com/news/webqoof/welcome-to-the-quint-ai-chatbot-on-whatsapp-telegram (2026-05-04) · https://about.fb.com/news/2024/02/mcas-whatsapp-helpline-curbing-the-spread-of-ai-generated-misinformation/ (2024; no 2026 status found) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/chat_prompts.py:51-56 and :72-74 (scope 'Anything ... from anywhere in the world'; only opinion/joke/greeting/taste declined) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/triage.py:8-12 ('Deliberately narrow': only whole-message greetings/thanks refused) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/whatsapp.md W-log-1, W-log-7, W-log-9, W-log-27 · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/policy-legal.md:42-47 (F4) · C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/gap_ai_providers/notes.md (working notes saved as found)

### WhatsApp replies are no longer free, but the research says they are. Meta's non-template-messages page, fetched 2026-10-15, says 'Effective October 1, 2026, Meta will charge on a per-message basis for service messages'. Rates are 'the same as the rates for utility and authentication messages', with no volume tiers and no stated free allowance. limits-budget F5, its option table and PROJECT_PLAN §11's WhatsApp notes ('user-initiated service replies are free') all predate this.

Two things nobody has priced:
1. The India rate. About ₹0.115 per message according to a third-party summary; Meta's own India rate card has not been read.
2. Messages sent per check. The existing bot (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/telegram_bot.py) sends at least two: 'Checking…' at :708 and the answer at :748. A long check adds two more (:739, :678-679). Every small-talk reply, cap refusal or unsupported type gets one.
*Confidence: high*

GAP CLOSED. The gap's premise is half right. Service replies are no longer free, but there IS a free allowance: 1,000 delivered service messages per month per business phone number. The India rate after that is exactly INR 0.115 per message. Both facts are now read from Meta's own live pages. No money was spent: about 9 web calls, one Chrome render, and one fake-only script.

[DECISION-CRITICAL] F1. India rate (primary, read 2026-10-15). I rendered the live pricing page in headless Chrome to get fresh signed rate-card links, then downloaded Meta's INR and USD rate cards. They are .csv by name but xlsx inside, Last-Modified 30 Sep 2026. Both are titled "Cost per message in INR [USD] on the WhatsApp Business Platform, effective October 1, 2026".
- India row, INR: Marketing 0.8631 | Utility 0.115 | Authentication 0.115 | Authentication-International 2.4971 | **Service 0.115** | Meta Business Agent "$2.00 USD / 1 M (million) tokens".
- India row, USD: 0.0118 | 0.0014 | 0.0014 | 0.0304 | **Service 0.0014**.
- The INR volume-tier card lists tiers only for utility and authentication; service is not in it.
- The rate card has no free-allowance footnote; the allowance appears only on the pricing page (F2).
- These are list rates. Meta's INR invoicing adds 18% GST (secondary: freepressjournal says "excluding taxes"; whatsapp.md W12), so the effective rate is about INR 0.1357 per message.

[DECISION-CRITICAL] F2. Free tier (primary, live page "Updated: Sep 30, 2026", rendered 2026-10-15). Verbatim from the page:
- "As Meta resumes charging for service messages, Meta provides every business phone number with a free tier of 1,000 service messages per month. Each business phone number has one free tier of 1,000 delivered service messages per month. Meta charges as of the 1,001st service message per month".
- "Unused service messages in the free tier do not roll over"; it resets at 12am in the messaging account's time zone.
- "If businesses do not have a payment method for their Messaging account(s), Meta will deliver service messages within the free tier but not deliver them after the free tier has been used."
- The page also lists "Free messages: Two instances (all messages in free entry point window; free tier of monthly service messages)".
- The 72-hour free-entry-point window still applies. Only eligible government and non-profit organisations stay free beyond the tier, through 2027-12-31.
- "Pricing updates for service messages launching October 1, 2026 do not apply to AI Providers" (separate policy; see F6).
- Cross-checks agree: ycloud (dated 2026-09-04) and 360dialog (undated; cites Meta pages checked 2026-09-08) both say "1,000 free service messages per business phone number per month", with billing from the 1,001st delivered message. 360dialog quotes $0.0014 for India.
- Why the gap said there was no allowance: the non-template-messages page is Meta's "upcoming updates" page and never mentions the tier. Also, the pricing.md export (and the fetch tool's copy) is STALE. It still says "All non-template messages are free" and treats 2026-10-01 as future. Only the rendered HTML carries the 30 Sep text. Anyone re-checking must render the page, not fetch the .md.
- Effect on whatsapp.md: W11 relied on a search index (medium-high). It can be raised to high.

[DECISION-CRITICAL] F3. Messages sent per event, measured on the CURRENT scripts/telegram_bot.py. Method: the real handle_message, with fake Telegram and API clients and no network. Script: scratchpad/audit/rv/count_sends.py. Output:
- smalltalk "hi": 1
- /start help: 1
- normal check, or an answer-cache hit: 2 ("Checking…" at :708, answer at :748)
- **daily cap refused: 2.** "Checking…" goes out at :708 BEFORE the API refuses, then "😕 <detail>" at :716. The gap counted this as 1.
- slow check, then a poke: 4 (:708, "still running" at :739, then :678 and :679)
- slow check, then a new claim as the poke: 4
- Not exercised in the script: an unsupported type sends 1 (:694), and any message arriving mid-check gets 1 (_NOT_CHECKED or the "still running" text at :672).
- Every inbound message gets at least one reply, including stickers.
- A Telegram send rejected for its HTML is retried as plain text (:524-557). On WhatsApp only delivered messages are billed, so this does not double-bill.

[DECISION-CRITICAL] F4. What it costs.
- Normal use is FREE at Meta: the 5/day cap allows at most about 155 checks a month, about 310 messages at 2 per check, well under 1,000. Per check after the tier: 2 × INR 0.1357 ≈ INR 0.27 (about $0.0033), about 5% on top of the $0.066 average.
- The real exposure is replies that buy no check. The check cap bounds none of them.
- With a payment method, cost is linear and unbounded: 10,000 junk messages from one number cost about 9,000 × 0.1357 ≈ INR 1,220; 100,000 cost about INR 13,400 (about $160). The gap's "1,000 messages ≈ INR 115" is wrong: the first 1,000 are free.
- WITHOUT a payment method, cost is capped at INR 0, but about 1,000 "hi"s from ONE number use up the month's tier. Meta then stops delivering every reply, to every user, until the 1st of next month. That is a cheap lock-out, which is blocker-class under the rubric.
- Inbound messages are not billed (Meta charges only business-to-user), so silence costs nothing.

F5. Required corrections (I edited no repo files).
- (a) limits-budget.md F5 (line 47) and line 50 ("pays Meta $0 per reply"), plus the option-table row at line 95. Replace "free" with: "From 2026-10-01 service replies cost INR 0.115 (+18% GST) each, after 1,000 free per business number per month (pricing page, updated 2026-09-30; INR rate card effective 2026-10-01). Utility templates in the window are also charged from 2026-10-01, which settles the Zoho conflict."
- (b) PROJECT_PLAN.md:388-390 (§6 roadmap) and :1914-1916 (§11 WhatsApp notes). Same correction, plus "add a payment method, or sending stops after 1,000 a month".
- (c) Add to the limits design:
  - A per-number REPLY cap enforced before any send: e.g. at most 20 replies a day per hashed number. Past it, stay silent, or send one final "limit reached" notice per day.
  - The cap-refusal path must not send "Checking…" first: claim the slot, then acknowledge.
  - A global monthly outbound-message budget as its own WhatsApp line in the ledger and dashboard, alerting near 800 of the 1,000.
  - A deliberate payment-method choice. Recommend a card plus the reply caps; with no card, the reply caps are the only thing standing between one spammer and a month-long outage.
- (d) The WhatsApp bot should send ONE message per check: no "Checking…" text, with a typing indicator instead. The typing-indicators doc says nothing about billing and Meta's pricing pages count only business-to-user messages, so typing indicators are assumed unbilled. That is unverified.

F6. Effect on the WhatsApp decision.
- The pricing does NOT change the go/no-go. At the 5/day cap Meta's fee is INR 0. It is negligible next to the LLM bill even past the tier.
- It DOES change the build requirements. Per-number reply caps, single-message replies, an outbound-message budget line and a payment-method decision become launch preconditions for WhatsApp; they are not needed for Telegram.
- The deciding risk is still Meta Terms §4.7 (AI-primary providers barred; India not an allowed AI-Provider market; limits-budget F4, whatsapp.md W13). If Meta classes the bot as an AI Provider, the service-pricing question is moot: the Oct-1 pricing explicitly does not apply to AI Providers, and India is not on their pricing list.

Flags:
- The pricing page's .md export disagrees with the rendered page. I trust the rendered page because it carries the newer "Updated: Sep 30, 2026" date.
- 18% GST is from secondary sources only.
- Signed rate-card links expire about 2026-10-19 (oe=6AD6...). Re-render the pricing page to refresh them.

**Changes the decision?** Partly. The WhatsApp go/no-go is unchanged. Meta's fee is INR 0 at the 5/day cap, because 1,000 free service messages a month per business number cover about 310 messages a month. After the tier it is INR 0.115 (+GST) per message, about 5% on top of a check. Policy (§4.7, AI-Provider ban, India not allowed) remains the deciding risk. The build requirements change. A WhatsApp launch now needs these preconditions: a per-number reply cap enforced before sending; one message per check (no "Checking…", and no "Checking…" before a cap refusal); an outbound-message budget line in the ledger and dashboard; and an explicit payment-method decision. Without a card, one spammer can use up the 1,000-message tier and silence the bot for everyone until the month resets. With a card, junk replies cost about INR 0.136 each with no upper bound. limits-budget F5 (line 47), lines 50 and 95, and PROJECT_PLAN.md:388-390 and :1914-1916 must stop saying service replies are free.

Sources: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing (rendered in headless Chrome 2026-10-15; page shows 'Updated: Sep 30, 2026'; free tier, payment-method, AI-Provider and gov/non-profit text quoted from it; rendered copy at scratchpad/audit/rv/dom.html.txt) · Meta INR rate card 'Cost per message in INR on the WhatsApp Business Platform, effective October 1, 2026' - scontent.fbom19-5.fna.fbcdn.net/v/t39.8562-6/830985615_1819783359150737_3237041219299440415_n.csv (fresh signed link from the rendered pricing page, Last-Modified 2026-09-30; local copy scratchpad/audit/rv/dl/INR_list_rates.csv; India row: 0.8631 / 0.115 / 0.115 / 2.4971 / Service 0.115) · Meta USD rate card effective October 1, 2026 - scontent.fbom19-1.fna.fbcdn.net/v/t39.8562-6/829311379_1537421421402610_366484812346475911_n.csv (India Service 0.0014; local copy scratchpad/audit/rv/dl/USD_list_rates.csv) · Meta INR volume tiers effective October 1, 2026 - .../828939221_1081733358177980_6811734651913870898_n.csv (tiers only for utility/authentication) · https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/non-template-messages (the 'upcoming updates' page: per-message service charges from 2026-10-01, rate = utility/auth, no volume tiers, no free-tier mention; fetched 2026-10-15) · https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing.md (STALE export: still says 'All non-template messages are free'; fetched 2026-10-15) · https://www.ycloud.com/blog/whatsapp-api-message-pricing-update-effective-october-1-2026 (2026-09-04; 1,000 free per number per month) · https://360dialog.com/blog/whatsapp-service-message-charging-october-2026/ (undated, cites Meta pages verified 2026-09-08; 1,000 free; India $0.0014) · https://www.freepressjournal.in/tech/how-much-does-india-have-to-pay-for-whatsapp-messages-from-october-1 (secondary: Rs 0.115 after 1,000 free, excluding taxes) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/telegram_bot.py:524-557 (send + plain-text retry), :642, :663, :672, :678-679, :694, :698, :705, :708, :713, :716, :733, :739, :748, :751 · Script output: C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/audit/rv/count_sends.py -> smalltalk 1, help 1, check/cache-hit 2, cap refusal 2, slow check + poke 4 · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/limits-budget.md:47-52 (F5) and :95 (option table) - stale 'free' claims · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/PROJECT_PLAN.md:388-390 and :1914-1916 - stale 'user-initiated service replies are free' · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/whatsapp.md W9-W12 (lines 216-305; consistent; W11 confidence can be raised to high)

### The hosting shortlist is ranked on 'in India, nearest the users', which barely matters for this app. A check runs 30-295 s, dominated by Claude calls served from outside India, so an Indian host saves a fraction of a second.

The shortlist misses three things that change cost and risk:
1. Lightsail's own pricing page says 'As part of the AWS Free Tier, you can get started with Amazon Lightsail for free'. Secondary summaries of AWS's free-tier page give 90 days on the $5/$7/$12 Linux bundles, one bundle per account. cloud-hosting charges the $7 Mumbai plan from month one.
2. This PC already has the Google Cloud SDK signed in to the owner's Gmail, with project 'harvard-mlops'. So he has a Google Cloud account; whether billing is enabled is unknown.
3. Docker Desktop 29.8.1 is installed, although CLAUDE.md says Docker is not. That means the Deno + curl_cffi + ffmpeg image the ytdlp result requires can be built and tested here.
*Confidence: medium*

## Summary

Three things change. The Lightsail 90-day trial in the gap's premise no longer exists. AWS credits now cover Lightsail instead, which is better for the owner. And his Google Cloud account turns out to be a personal one with billing switched on.

None of this moves the hosting choice away from a Lightsail-class VM. It changes two things:
- **Cost.** A new AWS account can probably run the $7 Mumbai plan on credits for about 12 months. This rests on AISPL eligibility, which is unconfirmed.
- **Order of steps.** The datacenter-IP reel probe can now run for $0 out of pocket, on the exact recommended host, before he pays for anything or builds the residential-proxy seam.

Total calls: 11 web, plus local read-only checks. No money spent and no repo files changed.

## Findings

**F1 (decision-critical). The Lightsail free trial is gone. Credits replace it.**
- Lightsail billing FAQ (docs.aws.amazon.com, read 2026-10-15): "Lightsail's short-term free trial offers have been replaced by the AWS Free Tier … These offers are no longer available to new Lightsail customers. Instead, you can get started with Amazon Lightsail for free with the AWS Free Tier where you can get up to $200 USD in free AWS credits."
- AWS's own Lightsail free-tier page (aws.amazon.com/free/compute/lightsail/, ©2026): "Use credits to access features in both Free and Paid plans, including: Virtual private server (VPS) instances…"
- So the secondary summaries offering "90 days free on the $5/$7/$12 bundles" are out of date. They only apply to trials started before the offer was removed (same FAQ: "What if I am already on a free trial?").
- cloud-hosting.md:140 and :305 already flagged this conflict as unresolved. These two AWS pages settle it.
- Conflict: an older re:Post answer (about 10 months old; the page returned 403 when fetched) said Free-plan accounts cannot open Lightsail and must upgrade to the Paid plan. The current official page says they can. If the console refuses, upgrading to Paid keeps the credits (billing docs: "Any remaining credits … are automatically applied").

**F2 (decision-critical). The credit terms.** Source: AWS Free Tier Terms, "Last Updated: July 9, 2025", and the AWS billing docs free-tier.md and free-tier-plans.md.
- $100 credit at sign-up, plus up to $100 more earned through activities.
- "Free Tier Credits expire twelve months from the date you opened your account."
- "you are not eligible to receive Free Tier Credits for more than one account."
- Only new AWS customers qualify.
- **Free plan:** no charges at all. The account closes after 6 months or when the credits run out, whichever comes first. Data is kept 90 days, then deleted unless he upgrades.
- **Paid plan:** pay-as-you-go once the credits are used up.

What it means here (my arithmetic, not AWS's figures):
- **Probe:** one week on the $7 Mumbai plan is about 168 h × ($7/730 h) ≈ $1.6 of credit and $0 cash. On the Free plan, an accidental bill is impossible.
- **Production:** $100 covers the $7 plan for about 14 months, but the credits expire at 12, so it is roughly 12 months at ≈$0 instead of ≈₹730 a month from month one.
- The probe box can stay on as the production box after upgrading to Paid.
- Unverified: whether credits also cover the 18% GST on an AISPL (AWS India) bill.

**F3 (decision-critical, UNVERIFIED). AISPL eligibility is not settled.**
- None of these pages mentions AISPL or India: the AWS free-tier pages, the FAQ, the terms, or two searches.
- The terms apply under "the AWS Customer Agreement or other agreement with us", which neither includes nor excludes the AISPL agreement.
- I found nothing that excludes India accounts. I also found no primary source saying they qualify.
- He has to confirm it himself: at sign-up, look for the plan choice and the Credits page in Billing.
- Also unknown: whether he already has an AWS account. No ~/.aws folder and no aws CLI exist on this PC, but that proves nothing. If he has one, he gets no credits.

**F4 (decision-critical). His Google Cloud account is personal and billing is on.** These are read-only gcloud calls, run 2026-10-15 and free.
- `gcloud config list`: account vinayakmokashi305@gmail.com, project harvard-mlops.
- `gcloud projects describe harvard-mlops`: name "Harvard MLOps", created 2026-09-21, ACTIVE, **no parent organization**. So it is not a course's or university's organization project.
- `gcloud billing projects describe harvard-mlops`: billingEnabled=true, linked to billing account 01262C-…-38097A.
- `gcloud billing accounts list` / `describe`: one account, displayName "My Billing Account", open=true, currencyCode **USD**, masterBillingAccount "" (not a reseller or education sub-account), parent "".
- The same billing account also covers project **information-verifier** (created 2026-07-24, billingEnabled=true). That project's enabled APIs include factchecktools.googleapis.com. Compute Engine has never been enabled there (`instances list` returned "has not been used in project information-verifier before").

What follows:
- Some payment instrument was accepted when the account was set up, so sign-up is not the blocker for Google.
- Still untested: an RBI e-mandate on a recurring USD charge.
- The CLI cannot show the credit balance or coupons, so whether course credits sit on this account is unknown. Ask the owner whether the $300 / 90-day trial or any course coupon is active, and when the billing account was opened.
- If course credits are applied, the public service should not draw on them. The natural home is the existing information-verifier project.
- A Google VM tests Google's IP ranges, not AWS's. Its reel verdict would not carry over to Lightsail.

**F5 (decision-critical). Docker works here, so the cloud image can be built and tested locally for $0.**
- `docker version`: client and server 29.8.1.
- `docker info`: OSType linux, 16 CPUs, about 7.4 GiB of memory.
- The image ghcr.io/astral-sh/uv:0.12.19-python3.12-trixie-slim is already cached.
- The repo has no Dockerfile.
- CLAUDE.md:57 ("Not installed and not needed: … Docker") is wrong.
- The image recipe from the yt-dlp research (yt-dlp[default,curl-cffi] plus Deno and ffmpeg, ytdlp-cloud-ips.md F8 at line 188) can be built and checked here.
- A local run only proves the image works. It runs from the home residential IP, so it says nothing about how a datacenter IP is treated.
- scripts/link_probe.py:139-147 now calls the app's own `resolve_link`, so the probe's verdict is the app's verdict.

**F6 (decision-critical). Rank hosts on reel success, payment and cost after credits, not on being in India.**
- A check takes 30–295 s and is dominated by Claude calls served from outside India. Being in Mumbai rather than Singapore or the EU saves well under a second.
- The deciding unknown is whether reels resolve from the host's IP class (ytdlp-cloud-ips.md F1–F3, F12). That needs a probe on the exact host, repeated over days.

## How this changes the decision

**First choice:** still Lightsail Mumbai. The reasons now are the AISPL rupee payment rails (cloud-hosting F5) and roughly 12 months covered by credits. Proximity to users is no longer a reason.

**Before any money or proxy work:**
1. **Owner answers four questions:**
   - Does he already have an AWS account?
   - Does the AISPL sign-up offer the credits?
   - Is a Google Cloud trial or any coupon active, and from when?
   - Is harvard-mlops coursework? Course credits must not pay for the public service.
2. **Build and test the Docker image here** ($0).
3. **Open a new AWS account on the Free plan** (no-charge guarantee) and start the $5 or $7 Mumbai bundle.
4. **Run link_probe.py daily for 7 days** with one YouTube Shorts, one Instagram reel and one Facebook reel link.
5. **Decide from the results:**
   - If all three resolve on most days: upgrade to Paid and keep the box, with no residential-proxy seam yet.
   - If any of them is walled: build the home-PC route or the pay-as-you-go proxy (ytdlp F5/F6) before going public.

**Optional:** if Google trial credits remain, run the same probe on a Google VM in parallel as a second datacenter sample.

## Flags
- **No primary source found:** AISPL eligibility; whether credits cover GST.
- **Conflicts:** the Free plan's Lightsail access (an older re:Post answer against the current official page); the Free-plan close date (6 months) against the credit expiry (12 months), though these are two separate clocks.
- **Unknowable from here:** the Google credit balance.

**Changes the decision?** Yes, in cost and in the order of steps, not in the host chosen. Lightsail Mumbai stays first choice, but for its rupee payment rails and the AWS credits, not for being in India. On a new AWS account the $7 plan is probably ≈$0 for about 12 months instead of ≈₹730/month from month one (it depends on AISPL eligibility and on whether credits cover GST, both unverified). The decisive datacenter-IP reel probe can run for $0 on a Free-plan Lightsail box for 7 days before any spend or proxy work. The Docker image can be built and tested locally now. The owner has a personal, open Google Cloud billing account (USD) with an information-verifier project. Whether the hosting goes ahead now depends on the probe result and four owner answers, not on latency.

Sources: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html (read 2026-10-15; 'short-term free trial offers have been replaced by the AWS Free Tier') · https://aws.amazon.com/free/compute/lightsail/ (©2026; 'Use credits to access features in both Free and Paid plans, including: Virtual private server (VPS) instances') · https://aws.amazon.com/lightsail/pricing/ (©2026; 'As part of the AWS Free Tier, you can get started with Amazon Lightsail for free'; Mumbai gets half the transfer allowance) · https://aws.amazon.com/free/terms/ (Last Updated July 9, 2025; credits expire 12 months; not eligible for more than one account; Free plan expires at 6 months or when credits run out) · https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier.md and free-tier-plans.md (read 2026-10-15; $100 + up to $100; Free plan closes, 90-day retention; remaining credits carry over on upgrade) · https://aws.amazon.com/free/free-tier-faqs/ (©2026; Free plan cannot be extended past 6 months; new customers only; no AISPL mention) · https://aws.amazon.com/free/ (©2026; Free vs Paid plan, up to $200 credits) · https://repost.aws/questions/QUScuupiDZTGeZbF89dT7yMg (older answer that Free-plan accounts cannot use Lightsail; 403 on fetch, seen in a search snippet only) · Local: gcloud config list / projects describe harvard-mlops / billing projects describe / billing accounts list+describe / services list --project information-verifier / compute instances list (read-only, 2026-10-15) · Local: docker version and docker info (29.8.1, linux engine, 16 CPU) and docker images (uv python3.12-trixie-slim cached); no Dockerfile in repo · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/CLAUDE.md:57 (says Docker is not installed; wrong) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/scripts/link_probe.py:139-147 (calls the app's resolve_link) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/cloud-hosting.md:127-142, 275-277, 305 (Lightsail F5, the $7 plan charged from month one, the unresolved trial conflict) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/ytdlp-cloud-ips.md:7-26, 180-188 (datacenter-IP risk, image recipe)

### No Claude call carries a per-person identifier: a grep of app/ finds no `metadata` or `user_id`. That includes the vision call, which sends any stranger's image straight to the API (C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/providers/vision.py). The Messages API reference, fetched 2026-10-15, defines metadata.user_id as an opaque id, a uuid or hash and never a name, email or phone number, that 'Anthropic may use … to help detect abuse'. Without it, all strangers' abuse is attributed to the owner's organization. limits-budget's 'dedicated workspace' separates spend, not enforcement. No result asks what happens to the organization, and to the owner's own API use, if strangers submit prohibited content, for example deliberately to get the key banned.
*Confidence: medium*

## The gap: no per-person ID on Claude calls, and whether a workspace protects the owner's org

### 1. Repo check against the current tree (free, read-only, no network)
- The app makes Claude requests from two places: `app/engine/chat.py:386` (`async_client.messages.stream(**request)`, used for pass 1 and pass 2) and `app/providers/vision.py:25` (`async_client.messages.create`). `app/providers/usage.py:195-196` only wraps them for metering. There is no other `messages.*` call in app/; `scripts/crawl_probe.py:45` is an operator script and does not serve strangers.
- Grepping app/ for `metadata` or `user_id` finds only a comment at `app/providers/links.py:8`.
- I ran a script that replaces both clients with recorders: `scratchpad/audit/rv/uid/repro_user_id.py`, run from that folder with dummy keys and a scratch DB. One check plus one OCR produced 3 requests:
  ```
  chat.stream    keys=['max_tokens','messages','model','output_config','system','tools'] metadata=None
  chat.stream    keys=[...same...] metadata=None
  vision.create  keys=['max_tokens','messages','model'] metadata=None
  ANY user_id: False
  ```
- **No per-person identity reaches either call site today.**
  - `chat.answer(text, heard, emit, language)` and `ocr_image(image_bytes, media_type)` take no person argument.
  - `run_check` (`app/engine/job.py:44`) has none either.
  - The limiter keys only on `request.client.host` (`app/api/limits.py:119`).
  - The Telegram bot reaches the API as one client. So the user_id fix depends on the limits redesign's per-person key, which does not exist in the server yet.
- **The vision call is inside the daily cap.** `/verify/image` takes `_quota` and calls `spend.begin()` before `ocr_image` (`app/api/routes.py:280-288`). At today's cap of 5 checks a day (`app/config.py:88`), shared by web and bot, a stranger can get at most about 5 inputs a day to Claude. A dollar budget would raise that number.

### 2. Policy facts (all fetched 2026-10-15)
- **The `metadata.user_id` field** (Messages API reference, platform.claude.com/docs/en/api/messages, page undated):
  - It is "optional string or null", maxLength 512.
  - "This should be a uuid, hash value, or other opaque identifier. Anthropic may use this id to help detect abuse. Do not include any identifying information such as name, email address, or phone number."
- **Anthropic's API Safeguards Tools page** (support.claude.com/en/articles/9199617, updated Sep 14 2026):
  - "Consider assigning IDs to users, which can help you track specific individuals who are violating Anthropic's AUP."
  - "If provided, we can more precisely pinpoint violations."
  - "Any IDs passed should be cryptographically hashed."
  - The operator should "Warn, throttle, or suspend users who repeatedly violate".
  - "Failure to comply with the Terms and Usage Policy may result in suspension or termination of your access to the services."
  - Nothing in it says that sending user IDs shields the organization. They only make the attribution more precise.
- **Responsibility sits with the account holder.**
  - The Usage Policy (anthropic.com/legal/aup, "Effective November 12, 2026"; the Sep 15 2025 version is still in force until then) covers "the end users of products or services integrating Claude".
  - Enforcement wording: "we may warn you or throttle, limit, suspend, or terminate your access to our products and services."
  - The Commercial Terms (effective June 17 2025) say in D.5: "Customer is responsible for all activity under its account."
  - Under I.3.a, Anthropic "may suspend Customer's access to any portion or all of the Services" if D.2 is violated (D.2: "Customer and its Users may only use the Services in compliance with … the Usage Policy"). No prior notice is required; I.3.b promises only "reasonable efforts" to give written notice.
- **Enforcement is measured per account, not per workspace.**
  - The Safeguards Warnings and Appeals page (support.claude.com/en/articles/8241253, "Updated today") says: "For API customers, these warnings are linked to ongoing thresholds of violative behavior across their entire API account."
  - Holds are listed per organization ("each organization that's on hold").
  - The Workspaces doc (platform.claude.com/docs/en/manage-claude/workspaces) describes workspaces as "maintaining centralized billing and administration". They isolate keys, spend and rate limits, prompt caches, files and batches.
  - No document says that workspaces isolate enforcement or account standing.
  - **Inference, not stated outright:** a suspension caused by the public workspace takes down the whole organization, including the owner's testing key.
  - The organization guidance for products serving minors (9307344, updated Mar 16 2026) describes escalation: an organization with a high violation rate is first asked to add safeguards, and suspension follows if it does not. That points to warnings before a ban for ordinary violations. Whether the worst categories bring an immediate suspension is not documented; I.3.a would allow it.
- **A separate organization is possible, but needs a different email.**
  - The Creating and Managing Workspaces article (support.claude.com/en/articles/9796807, updated June 30 2026) says: "A single email address can create only one Console organization."
  - "A separate organization is independent of your existing one, with its own members, billing, and Workspaces."
  - To create one: "sign up with a work email address that isn't already registered with Anthropic."
  - An existing email can be invited into the new organization and switch between the two.
- **The owner's claude.ai subscription is a separate account.** Article 8987223 (undated) says a Claude.ai account and a Console account with the same email "will operate independently". It says nothing about whether a ban carries from one to the other.

### 3. Effect on the pre-public-fixes decision
This adds two items to the pre-public list and changes the limits-budget recommendation from a dedicated workspace to a dedicated organization. It does not change where the app runs, and the only cost is a second prepaid balance.

**(a) Should-fix, before inviting real users: put an opaque per-person ID on every Claude request.**
- Every `messages.stream` and `messages.create` call should carry `metadata={"user_id": HMAC-SHA256(server_secret, person_key)}`.
- The person key is the Telegram user id, the WhatsApp number or the Turnstile cookie id, as in the limits design.
- **Why HMAC rather than a plain hash** (my own reasoning, not from a source): a plain SHA-256 of a 10-digit Indian mobile number can be reversed by trying every number, so a plain hash still leaks the phone number.
- **Keep the secret stable.** If it rotated daily like a quota salt, Anthropic could not link one person's requests across days.
- **Plumbing it needs:**
  - The person key has to pass through `run_check`, `chat.answer` and `ocr_image`.
  - The bot must send its person key in a header protected by a shared secret, or a web visitor could claim to be any Telegram user.
- **The other half the Safeguards page asks for:** the app's own warn/throttle/block of repeat-violating person keys.
- **A free test:** use the existing `StubClient` (`tests/test_chat_engine.py:70`) or my recorder, and assert that every request has a `metadata.user_id` that is 64 hex characters, at most 512 long, never the raw id, and contains no run of 10 or more digits. Check that it fails against today's tree; the repro shows it would.

**(b) Owner decision, recommended before the first public URL: put the public key in a separate Console organization.**
- A workspace caps spend but does not protect the owner's account standing. One determined stranger could get the account warned or suspended, and that would take down the web page, both bots and his own testing together. The 5-a-day cap only slows this down.
- What it takes:
  - a second email address;
  - a separate prepaid balance with auto-reload off;
  - possibly starting again at the lowest rate-limit tier (I did not verify this).
- On deployment shape (H), his PC, the public server needs its own env file holding the public organization's key. Otherwise `smoke_test.py` and the public site share one key and one blast radius again.

**Question for the owner:** is it acceptable to create a second Console organization under a different email for the public key, and keep the current organization for your own testing?

### 4. Not pinned down
- No document states outright that suspending an organization disables keys in every workspace. A third-party report quotes the error text "This organization has been disabled".
- The violation thresholds are not published.
- Whether a Console ban carries over to a claude.ai account with the same email is undocumented.
- The AI-disclosure and high-risk ("Media or professional journalistic content") Usage Policy rules are already covered in `docs/research/2026-10-15/policy-legal.verification.md` (F9), so I did not repeat that work here.

I used about 13 web calls.

**Changes the decision?** Yes, two additions, and one change to the limits-budget recommendation.

1. **New should-fix item (before inviting real users):** every Claude request must carry `metadata.user_id`. That means the two `chat.py:386` stream passes and the `vision.py:25` create. The value is HMAC-SHA256(stable server secret, person key), where the person key is the Telegram id, WhatsApp number or Turnstile cookie id. It must never be a raw or plain-hashed phone number.
   - This depends on the limits redesign, because no person key reaches the server today: `limits.py:119` keys only on the client IP, and the bot arrives as one client. The bot must send its key in a header protected by a shared secret.
   - Pair it with the app's own block-list for repeat violators. Anthropic's Safeguards Tools page asks operators to warn, throttle or suspend such users.
   - It can be tested for free with the existing `StubClient`.

2. **Change "dedicated workspace" to "dedicated organization" (owner decision, recommended before the first public URL):**
   - API warnings count "across their entire API account".
   - The Commercial Terms make the customer "responsible for all activity under its account" and allow suspending "any portion or all of the Services".
   - Workspaces separate keys, spend and rate limits but keep "centralized billing and administration".
   - So only a separate organization keeps a stranger-caused suspension away from the owner's testing key. It needs a second email ("A single email address can create only one Console organization") and its own prepaid balance. On shape (H) the public server also needs its own env file.

The hosting choice is unchanged, and the cost changes only by needing a second prepaid balance.

Decision-critical findings:
- **[DC1]** Enforcement scope: per account or organization, not per workspace.
- **[DC2]** A separate organization needs a different, unregistered email; it gets its own members, billing and workspaces (support article 9796807, updated 2026-06-30).
- **[DC3]** `metadata.user_id` spec: opaque, at most 512 characters, never a name, email or phone number; "Anthropic may use this id to help detect abuse"; Anthropic asks that IDs be cryptographically hashed (Safeguards Tools page, updated 2026-09-14).
- **[DC4]** The repo sends no `metadata` on any of its 3 requests, and no person identity reaches the engine.
- **[DC5]** Commercial Terms (effective 2025-06-17): D.5 makes the customer responsible for all activity, and I.3.a allows suspension without prior notice.

Sources: https://platform.claude.com/docs/en/api/messages (metadata.user_id definition, maxLength 512; fetched 2026-10-15, page undated) · https://support.claude.com/en/articles/9199617-api-trust-safety-tools (API Safeguards Tools, updated 2026-09-14) · https://support.claude.com/en/articles/8241253-safeguards-warnings-and-appeals ('across their entire API account'; fetched 2026-10-15) · https://www.anthropic.com/legal/aup (Usage Policy, Effective 2026-11-12; covers end users; warn/throttle/limit/suspend/terminate) · https://www.anthropic.com/legal/archive/22742366-2ef0-4c7a-a833-6523f10d3944 (Usage Policy in force until then, Effective 2025-09-15) · https://www.anthropic.com/legal/commercial-terms (Effective 2025-06-17; D.2, D.5, I.3.a, I.3.b) · https://platform.claude.com/docs/en/manage-claude/workspaces (workspaces: centralized billing and administration; what is isolated) · https://support.claude.com/en/articles/9796807-creating-and-managing-workspaces (updated 2026-06-30; one email creates one Console organization) · https://support.claude.com/en/articles/8987223-does-my-claude-ai-account-work-for-the-developer-console (claude.ai and Console accounts operate independently) · https://support.claude.com/en/articles/9307344-responsible-use-of-anthropic-s-models-guidelines-for-organizations-serving-minors (updated 2026-03-16; escalation to suspension) · https://aicoding.csdn.net/6a40105110ee7a33f2833ba7.html (third-party: 'This organization has been disabled.' error text) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/chat.py:374-386 (stream request, no metadata) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/providers/vision.py:23-38 (create, no metadata; no person parameter) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/engine/job.py:44-48 (run_check has no person argument) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/api/limits.py:119 (limiter keyed only on request.client.host) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/api/routes.py:280-288 (vision call happens after the quota claim and spend.begin) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/app/config.py:88 (max_checks_per_day = 5) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/tests/test_chat_engine.py:70 (StubClient records each request; reusable for the free test) · C:/Users/VINAYA~1/AppData/Local/Temp/claude/c--Users-Vinayak-Mokashi-Python-Sab-Information-Verifier/4b88200f-d561-4246-b38d-1eac8cf3cade/scratchpad/audit/rv/uid/repro_user_id.py (output: 3 requests, metadata=None on all, ANY user_id: False) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/policy-legal.verification.md (F9: AI disclosure and high-risk rules, already covered) · C:/Users/Vinayak Mokashi/Python Sab/Information_Verifier/docs/research/2026-10-15/limits-budget.md:7,95 (dedicated workspace recommendation; person keys)

