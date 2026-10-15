# Policy and compliance for a free public service in India

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: 0 of 1 verifier(s) finished; the rest are still running or died (usage limit / network) - treat the unverified parts as unverified.** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

Picked up from the killed attempt's source trail (leads_policy-legal.txt), using about 26 web calls. Main results, as of 15 Oct 2026:

(1) DPDP. Only the Rules on definitions and the Board, plus the Act sections that set up the Board, are in force (since 13 Nov 2025). Consent-manager Rule 4 starts 13 Nov 2026. All the duties a data fiduciary owes start 13 May 2027: notice, security, breach reporting, erasure/retention, children, grievance and penalties. The 'Removal of Difficulties' Order (S.O. 5458(E), 5 Oct 2026, gazetted 6-7 Oct) only rewords Sections 9(1) and 10(2)(c)(ii) and does not move any date. The '13 March 2027' date appears only in one India-Briefing article and is not supported by any official or tracker source. MeitY's January 2026 proposal to shorten the timelines was never notified. No Section 17(3) start-up exemption has been notified, so the 3 Dec 2025 'simplified framework' PIB release is a Lok Sabha answer with no substance. An individual running a public service is a Data Fiduciary. The big surprise is Rule 8(3), in force from 13 May 2027: it requires keeping personal data, traffic data and processing logs for at least one year. That conflicts with the app's 30-day deletion.

(2) IT Rules. The SGI amendment was notified 10 Feb 2026 and took effect 20 Feb 2026. It defines SGI as audio/visual/audio-visual only, so a text answer is outside the labelling duty. It also shortened timelines: grievances 7 days, takedown on actual knowledge 3 hours, intimate imagery 2 hours. On the Fact Check Unit, the Supreme Court issued notice on 10 Mar 2026 and refused to stay the Bombay High Court judgment, so the FCU rule stays struck down.

(3) Providers. Anthropic's AUP requires telling users they are talking to AI, and the minors guidelines (updated 16 Mar 2026) apply to anyone under 18. The Commercial Terms say Anthropic does not train on customer content and that the customer must tell its users that outputs can be wrong. API inputs and outputs are deleted within 30 days by default. Sarvam keeps data indefinitely until the workspace Owner sets a retention period; zero retention is available for Model APIs, and data is stored in India. Google's API ToS §3d requires a privacy policy. Telegram applies a default bot privacy policy unless you set your own in BotFather.

(4) WhatsApp. Meta's WhatsApp Business Platform terms §4.7 (last modified 23 Sep 2026) strictly prohibit AI Providers where AI is the 'primary (rather than incidental or ancillary)' functionality, and Meta decides what counts. India is not on Meta's list of markets where AI providers are let in; Brazil is the only current one. This is the biggest launch risk for a WhatsApp bot.

(5) YouTube's ToS (5 Jan 2022) forbids downloading and automated access without permission. Meta/Instagram terms similarly bar automated collection; that was not re-fetched.

## Findings

### F1. DPDP timeline in Oct 2026: none of the duties a data fiduciary owes are in force yet. Consent managers (Rule 4, s.6(9), s.27(1)(d)) start 13 Nov 2026. Rules 3, 5-16, 22, 23 and Act ss.3-17, 27-34 start 13 May 2027. The Oct 2026 Removal of Difficulties Order does not change any date.
*Confidence: high — **decision-critical***

From the Rules text: Rule 1(2) says Rules 1, 2 and 17-21 start on publication (13 Nov 2025, G.S.R. 846(E)). Rule 1(3) says Rule 4 starts 'one year after'. Rule 1(4) says Rules 3, 5-16, 22, 23 start 'eighteen months after' publication, which is 13 May 2027. That group covers notice, security, breach, erasure/retention, contact info, children's consent, grievance and penalties. The Digital Personal Data Protection (Removal of Difficulties) Order 2026 is S.O. 5458(E), dated 5 Oct 2026 and gazetted 6 or 7 Oct 2026; sources differ on which. It only inserts 'of' in s.9(1) and changes 'periodic audit' to 'periodic data audit' in s.10(2)(c)(ii). India-Briefing (7 Oct 2026) says ss.9-10 take effect '13 March 2027'. No official or tracker source supports that: dpdprules.org (checked 15 Oct 2026) and SS Rana (12 Oct 2026) keep May 2027. MeitY's 22 Jan 2026 proposal to shorten some windows (Mondaq, 28 Jan 2026) was never notified, and no 'DPDP (Amendment) Rules 2026' turns up. In practice: the obligations are not enforceable today, but launch with compliant documents now. They cost nothing, and the 13 May 2027 date is fixed.

Sources: DPDP Rules 2025 gazette text, Rule 1 (dpdpa.com/DPDP_Rules_2025_English_only.pdf) · https://dpdprules.org/timeline (status checked 15 Oct 2026) · https://ssrana.in/articles/dpdp-removal-of-difficulties-order-2026-what-has-been-changed-for-childrens-data-and-sdf-audits/ (12 Oct 2026) · https://www.india-briefing.com/news/dpdp-removal-of-difficulties-order-2026-consent-data-audit-47274.html (7 Oct 2026; the outlier '13 March 2027' claim) · https://webiis10.mondaq.com/india/data-protection/1737438/meity-signals-a-sharper-turn-in-indias-data-protection-rollout (28 Jan 2026)

### F2. From 13 May 2027, DPDP Rule 8(3) requires every Data Fiduciary to keep 'such personal data, associated traffic data and other logs of the processing for a minimum period of one year from the date of such processing'. This also covers processing done by its Data Processors. It conflicts with the app's 30-day deletion of answers.
*Confidence: high — **decision-critical***

The Rule text says the duty is 'without prejudice to sub-rules (1) and (2)' and exists for the Seventh Schedule purposes: State access for sovereignty/security, legal functions, and SDF assessment. Illustration Case 2 says the fiduciary must make sure its processor (the cloud host) also keeps the data and logs for a year. It is in the Rule 5-16 group, so it starts 13 May 2027. For this app, the 30-day answer deletion (invariant 10) and Anthropic's 30-day API deletion will need a decision before then. One option is to keep a minimal access/processing log and the submitted text for 1 year in restricted storage and then erase it. The other is to get legal advice on whether 'such personal data' covers the message content itself. It does not change hosting cost much, because the volumes are tiny. Nothing requires the storage to be in India.

Sources: DPDP Rules 2025 gazette text, Rule 8(3) and Seventh Schedule (dpdpa.com/DPDP_Rules_2025_English_only.pdf, notified 13 Nov 2025)

### F3. Meta's WhatsApp Business Platform terms (Last Modified 23 Sep 2026), §4.7: 'AI Providers' are 'strictly prohibited from accessing or using the WhatsApp Business Platform, whether directly or indirectly' where AI/LLM technologies 'are the primary (rather than incidental or ancillary) functionality', as determined by Meta.
*Confidence: high — **decision-critical***

whatsapp.com/legal/business-solution-terms now redirects (301) to the Meta Terms for WhatsApp Business Platform. A business may still use an AI Provider as its Solution Provider, and may not use WhatsApp data to train models other than ones for its own exclusive use. A claim verifier whose whole answer is LLM-generated is at real risk of counting as 'primary' AI functionality. A human fact-check tipline (BOOM, Factly) would clearly not be. Meta decides, so a WhatsApp bot could be refused or shut down. Mitigations: present it as a domain-specific fact-check service rather than a general chatbot, refuse off-topic chat (the app's triage already does), and expect the risk of account review.

Sources: https://www.facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform (Last Modified 23 Sep 2026, §4.7)

### F4. Meta's 'AI Providers' pricing page (updated 12 May 2026) lets general-purpose AI providers onto WhatsApp only where Meta is legally required to. Brazil (+55, from 11 Mar 2026) is the only market still listed. Italy and EU charges ran Feb/Mar to 12 May 2026 and have ended. India is not listed.
*Confidence: medium — **decision-critical***

Billable messages carry the category general_purpose_ai. Inference: an Indian AI-first bot has no paid route around §4.7; it has to qualify as 'incidental/ancillary' AI. No source found an Indian CCI order forcing access.

Sources: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers (updated 12 May 2026)

### F5. No small-fiduciary or start-up exemption under DPDP s.17(3) has been notified. The 'simplified compliance framework for start-ups' is a 3 Dec 2025 Lok Sabha answer (PIB Release ID 2198217) with no content. An individual running a public free service is a 'Data Fiduciary' ('person' includes an individual), and the personal/domestic-purpose exclusion in s.3(c)(i) does not cover it.
*Confidence: medium — **decision-critical***

The PIB text only says the Act and Rules 'provide for a simplified compliance framework'. A King Stubb & Kasiva commentary says the s.17(3) power, which could disapply ss.5, 8(3), 8(7), 10 and 11, is unused. Security safeguards and children's rules cannot be waived. Plan for full compliance by 13 May 2027. Penalties under the Schedule run up to Rs 250 crore for security failures, but s.33 also starts only on 13 May 2027.

Sources: PIB Release ID 2198217, 03 Dec 2025 (PDF copy via negd.gov.in/wp-content/uploads/2025/12/Press-Release_Press-Information-Bureau3-1.pdf) · https://www.digitalindia.gov.in/press_release/simplified-compliance-framework-for-start-ups-and-certain-data-fiduciaries-under-dpdp-act-and-rules/ (last updated 14 Oct 2026) · https://ksandk.com/data-protection-and-data-privacy/dpdp-compliance-for-startups-msmes/

### F6. DPDP Rules content from 13 May 2027:
- Rule 3: a standalone notice with an itemised list of personal data, the specified purpose and the service, plus how to withdraw consent, use your rights and complain to the Board.
- Rule 7: breach notice to each affected person without delay; to the Board without delay and with a detailed report within 72 hours.
- Rule 9: prominently publish contact details of someone who can answer questions.
- Rule 14(3): grievances answered within 90 days.
- Rule 10: verifiable parental consent before processing any child's (under 18) data.
*Confidence: high*

Rule 10 lets the parent be checked against identity/age details the fiduciary already holds, details the person volunteers, or a virtual token (for example DigiLocker). A site with no accounts cannot realistically run this. The practical, common approach is: the service is for 18+, a visible 18+ affirmation before submitting, no tracking or ads (s.9(3) bans tracking, behavioural monitoring and targeted ads at children), and deletion on notice. This is not a full legal answer. Forwarded messages often contain third parties' data. s.7 'legitimate uses' do not clearly cover that, and s.3(c)(ii) excludes only data made public by the person themselves or under a legal obligation. Minimising data, the 30-day deletion and a 'do not submit others' private details' notice are the practical mitigations.

Sources: DPDP Rules 2025 gazette text, Rules 3, 7, 9, 10, 14 (dpdpa.com/DPDP_Rules_2025_English_only.pdf)

### F7. The IT (Intermediary Guidelines and Digital Media Ethics Code) Amendment Rules 2026 were notified 10 Feb 2026 and took effect 20 Feb 2026. 'Synthetically generated information' (Rule 2(1)(wa)) covers audio, visual and audio-visual content only, not text, so the app's text answers fall outside the SGI labelling duty.
*Confidence: medium*

Labelling duties (Rule 3(3): visible label, audio prefix, permanent metadata) fall on intermediaries whose resources enable creating or spreading SGI. Timelines cut:
- Takedown on actual knowledge: 36 h to 3 h.
- Intimate imagery: 24 h to 2 h.
- Grievance resolution: 15 days to 7 days.
- Rule 3(1)(b) complaints: 72 h to 36 h.

Whether this app is an 'intermediary' at all (s.2(1)(w): receives or transmits records on behalf of another) is unclear. Its answers are its own content, which looks like a publisher, so s.79 safe harbour probably does not protect the answers. Publishing a grievance contact is free anyway. The G.S.R. number was not captured. The MeitY 15 Mar 2024 AI advisory (label 'possibly unreliable' AI output) has no confirmed 2026 status. Treat a fallibility disclaimer as best practice.

Sources: https://www.mondaq.com/india/it-and-internet/1749836/update-overview-of-the-it-intermediary-amendment-rules-2026 (2026) · https://ssrana.in/articles/government-notifies-information-technology-amendment-rules-2026/ · https://inc42.com/buzz/it-ministry-removes-approval-need-for-new-ai-models-rollout (Mar 2024)

### F8. Fact Check Unit: the Bombay HC (Sept 2024) struck down Rule 3(1)(b)(v). On 10 Mar 2026 the Supreme Court issued notice on the Union's appeal and refused a stay ('No, not at this stage'). No next date was reported. The FCU rule cannot be used in the meantime.
*Confidence: high*

No obligation for this app follows from it. A future SC reversal could let a government FCU flag content about the central government's business as 'fake', and intermediaries would then have to act on it.

Sources: https://www.livelaw.in/amp/top-stories/important-issue-supreme-court-agrees-to-hear-unions-challenge-to-bombay-hc-quashing-it-rules-on-fact-check-unit-525783 (10 Mar 2026)

### F9. Anthropic: the Usage Policy (page shows 'Effective November 12, 2026') says consumer-facing chatbots 'must disclose to users that they are interacting with AI rather than a human', at the start of each session or in the interface. It defines minors as anyone under 18 and points to the minors guidelines (updated 16 Mar 2026). Those ask for age verification, moderation, monitoring and an AI disclosure, and Anthropic may audit, suspend or terminate. The Commercial Terms (effective 17 Jun 2025) say Anthropic may not train on Customer Content and that the customer 'must notify its Users' about output reliability (D.3). API inputs and outputs are deleted within 30 days by default (privacy center, updated 1 Jul 2026). Flagged content is kept up to 2 years, classifier scores up to 7 years.
*Confidence: high*

The Commercial Terms say the Services are 'not for consumer use'. That means the customer (the owner) is the contracting party and carries the duties for the app's public users: AUP compliance, legal compliance and the reliability notice. The AUP bans spreading false or misleading information about people, health or elections. A fact-checker that says what is false is fine, but this reinforces showing uncertainty and allowing 'could not verify'. The current AUP may be an earlier version until 12 Nov 2026; the disclosure rule exists in both.

Sources: https://www.anthropic.com/legal/aup (fetched 15 Oct 2026; 'Effective November 12, 2026') · https://support.claude.com/en/articles/9307344-responsible-use-of-anthropic-s-models-guidelines-for-organizations-serving-minors (updated 16 Mar 2026) · https://www.anthropic.com/legal/commercial-terms (effective 17 Jun 2025) · https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data (updated 1 Jul 2026)

### F10. Sarvam keeps workspace data 'indefinitely' until an organisation Owner sets a retention period (Settings > Workspace > Data retention). Options run from 0 days to 730 days, and zero retention is available for Model APIs. Changes apply only to new data. Sarvam's ToS: data is processed and stored in India (s.8.2); Sarvam may use inputs and outputs, including speech/audio, for training under its Privacy Policy, with withdrawal of consent possible (s.17.5); the customer must have all consents for personal data it sends (s.7.3); Sarvam acts as processor (s.8.1); Indian law, Bengaluru arbitration.
*Confidence: high*

Action (free): set Model APIs retention to 0 days now, because voice notes already sent are retained indefinitely and the setting is not retroactive. Then say in the privacy notice that audio goes to Sarvam (India) for transcription and is not kept. No date is shown on the retention page.

Sources: https://docs.sarvam.ai/api/platform/data-retention · https://www.sarvam.ai/terms-of-service

### F11. Google APIs Terms §3d: 'You will provide and adhere to a privacy policy for your API Client that clearly and accurately describes to users' what is collected and how it is shared with Google and third parties. §6b: display any attribution the API documentation requires; the Fact Check claim-search page (updated 25 May 2023) names no specific attribution. §5e: no permanent copies or caching beyond the cache headers; do not remove attribution notices. §6c: do not imply a partnership with Google.
*Confidence: medium*

In practice: link each fact-check to its publisher (the app already shows clickable sources) and keep the publisher name. Do not say 'verified by Google'. Expire cached fact-check results (the app's answer-cache TTL already exists). The Terms' last-modified date was not captured.

Sources: https://developers.google.com/terms · https://developers.google.com/fact-check/tools/api (last updated 25 May 2023)

### F12. Telegram Bot Developer Terms: every bot must be bound by an easily accessible privacy policy. Telegram's Standard Privacy Policy for Bots applies by default, but you must supply your own (set in @BotFather) if the standard one does not describe your data practices. The app's do. You must store only the data you need, delete it on request or when no longer needed, encrypt it at rest, and not collect data to build AI datasets (s.4.3). User-submitted data may be used only with explicit, active, revocable consent after explaining its use.
*Confidence: high*

The bot sends message text, images and voice to Anthropic, Google and Sarvam, so a bot-specific policy (or a link to the site's policy) should be set in BotFather. Add a /privacy command and a /delete path. No effective date is shown on the page.

Sources: https://telegram.org/tos/bot-developers

### F13. YouTube's Terms (effective 5 Jan 2022) forbid users to 'access, reproduce, download, distribute…' content unless the Service expressly allows it or you have written permission. They also forbid accessing the Service 'using any automated means (such as robots, botnets or scrapers)' except public search engines, and allow viewing only for 'personal, non-commercial use'. Meta and Instagram terms similarly forbid automated collection without permission (not re-fetched this run).
*Confidence: medium*

A public service that runs yt-dlp on user-pasted Reels/Shorts breaches platform terms. The realistic exposure is contractual and technical: IP/account blocks and possible cease-and-desist letters, not criminal liability. It is lower because the app processes one user-supplied link at a time, transiently, keeps only a transcript, and redistributes nothing. Meta v. Bright Data (N.D. Cal., Jan 2024) found that logged-out scraping of public data did not breach Meta's terms, but that is a US ruling and may not carry over. Mitigations: no login cookies or accounts, no storing or re-serving media, delete downloaded media after ASR, and honour takedown requests. Copyright: a short transcript used to fact-check is a reasonable fair-dealing argument (s.52 Copyright Act, criticism/review), but this is untested.

Sources: https://www.youtube.com/static?template=terms (effective 5 Jan 2022)

### F14. Defamation: in India criminal defamation now sits in BNS 2023 s.356 (in force 1 Jul 2024; replaced IPC s.499), alongside civil defamation. The exceptions that matter are truth for the public good and good-faith opinion. An AI-written answer is the operator's own speech, so intermediary safe harbour probably does not apply to it.
*Confidence: low*

Practical norms used by fact-checkers and AI tools: attribute every finding to a cited source, use calibrated language ('no evidence found', 'could not verify'), and keep a visible 'AI-generated, may be wrong, not legal advice' notice. Offer a corrections and takedown contact with a fast response, and keep a log of corrections. The app's design already helps: tier 'none' is allowed, the model cannot raise the tier, and URLs come only from structured fields. Rated low because this is from background knowledge and was not re-fetched this run.

Sources: Bharatiya Nyaya Sanhita 2023 s.356 (background knowledge, not re-fetched this run)

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| Privacy notice (DPDP Rule 3 + Google API ToS s3d + Telegram bot policy) | 0 | Applies. Required by Google's API ToS and Telegram now; DPDP-mandated from 13 May 2027. One page linked from the site footer, the submit box, the bot's /privacy and BotFather. | Meets three regimes with one page; Already true to the app's design (no accounts, 30-day deletion, cost-only ledger) | Must be rewritten for the Rule 8(3) one-year logs before 13 May 2027; Third-party data in forwards has no clean lawful basis to cite |
| Terms of use with AI-accuracy and no-advice disclaimer | 0 | Applies. Anthropic Commercial Terms D.3 require telling users that outputs may be wrong. It is also the main defamation and negligence mitigation. | Sets the 18+ rule, acceptable use (no others' private data, no illegal content) and the limitation of liability; Covers the corrections and takedown process | A disclaimer does not cure a defamatory statement; calibrated wording matters more |
| AI disclosure in the interface (every surface) | 0 | Applies now (Anthropic AUP; minors guidelines). | One line: 'Answers are written by an AI (Claude) and can be wrong' | Must appear in the web page, the Telegram /start and any WhatsApp greeting |
| Contact / grievance officer details (DPDP Rule 9, Rule 14(3); IT Rules r.3(2) if an intermediary) | 0 | Applies (DPDP from May 2027; free to do now). Use a dedicated email and the owner's name as grievance contact. Respond within 7 days (IT Rules 2026) and well inside DPDP's 90 days. | Also the defamation correction channel | Publishes the owner's name; a role email avoids a personal address |
| 18+ only policy, age affirmation, no tracking or ads (DPDP s.9 / Rule 10) | 0 | Applies from 13 May 2027. Rule 10 verifiable parental consent is unworkable without accounts, so restrict to adults instead. | Also covers Anthropic's under-18 guidance; No analytics or ads means s.9(3) is met automatically | Self-declaration is not 'verifiable'; there is residual risk if children use it anyway |
| Set Sarvam Model API retention to 0 days | 0 | Applies now. The default is indefinite retention, and the change is not retroactive. | One dashboard setting; lets the notice say audio is not kept by the ASR vendor | Audio already sent stays under the old setting |
| Telegram bot privacy policy set in @BotFather plus /privacy and /delete | 0 | Applies now (Telegram Bot Developer Terms). | Can just link the site policy | Telegram requires explicit consent before using submitted data; add a one-time /start consent line |
| Breach response note (DPDP Rule 7; CERT-In 6-hour directions if applicable) | 0 | DPDP part applies from 13 May 2027. CERT-In April 2022 directions name service providers, intermediaries and body corporates; whether an individual is covered is unclear. | A half-page runbook: who to tell, 72-hour Board report, notice to affected users | With no accounts, telling affected users may be impossible; public notice is the fallback |
| Retention redesign for DPDP Rule 8(3) (1-year minimum logs) by 13 May 2027 | 0 (tiny storage) | Applies from 13 May 2027; conflicts with invariant 10's 30-day deletion. | Decide early and record it in PROJECT_PLAN §7 | Keeping message content a year raises breach impact; get advice on the minimum scope |
| WhatsApp bot under Meta §4.7 AI-provider ban | 0 for terms (Meta per-message pricing separate) | High risk. AI as 'primary functionality' is strictly prohibited and India has no AI-provider route. Feasible only if Meta accepts it as a domain-specific service with incidental AI. | Domain-limited triage already refuses general chat | Meta's discretion; the number or WABA could be banned after launch |
| Reel/Shorts link downloading (platform ToS) | 0 | Breaches YouTube/Meta terms. The exposure is contractual and technical (blocks, cease-and-desist letters). | Transient, one user-supplied link, no redistribution, transcript only | No permission route for an individual; datacenter-IP blocking is likely on cloud hosts |
| SGI labelling under IT Amendment Rules 2026 | 0 | Does not apply to text answers (SGI = audio/visual/audio-visual). It would apply only if the app ever generated audio or images. |  |  |
| Fact Check Unit rule (IT Rules 3(1)(b)(v)) | 0 | Does not apply. Struck down; the Supreme Court refused a stay on 10 Mar 2026. |  | Watch the SC appeal |
| Google Fact Check API attribution (publisher name and link, no 'by Google' claim) | 0 | Applies now. | Already done by the clickable sources |  |

## Recommendation (the researcher's)

Before the public launch, publish two pages, a Privacy Notice and Terms, and add an AI line to every surface. All of this costs nothing.

PRIVACY NOTICE must say:
(a) Who runs it: the owner's name, a contact email and a grievance contact (DPDP Rule 9).
(b) What is collected, as an itemised list: submitted text, images, voice notes, pasted links, the transcripts and OCR text made from them, the answer, the IP address for rate limiting, and the Telegram chat ID for the bot.
(c) Why: to check the claim and to stop abuse or overspend.
(d) Who receives it:
- Anthropic (USA) generates the answer and deletes API data within 30 days; it does not train on it.
- Google's Fact Check Tools API receives the claim text.
- Sarvam (India) transcribes audio; retention is set to 0 days.
- Instagram, YouTube and Facebook are contacted to fetch a pasted link.
- Telegram carries bot messages.
(e) Retention: answers are deleted after 30 days. Transcript and answer caches expire. A spend ledger keeps only cost and date, never content.
(f) No accounts, no ads, no tracking, 18+ only.
(g) Don't submit others' private information. Forwarded messages may contain it, and the app keeps it only as long as stated.
(h) How to ask for deletion or correction, the response time (7 days), and the right to complain to the Data Protection Board.
(i) A note that the notice will change as the DPDP Rules take effect on 13 May 2027.

TERMS must say:
- Answers are AI-generated (Claude), can be wrong or out of date, are not legal, medical or financial advice, and are not endorsed by Google or any fact-checker.
- Sources are third-party.
- Free, best-effort service with a 5-a-day limit, no warranty, liability limited.
- Acceptable use: no illegal content, no harassment, no others' private data.
- Corrections and takedown via email.
- Indian law applies.

UI: one 'Answers are written by AI and can be wrong' line on the web page, in the Telegram /start message, and in any WhatsApp greeting. Also an 18+ affirmation next to submit. Set the bot's privacy policy link in @BotFather.

Do the Sarvam 0-day retention setting today.

Record two decisions in PROJECT_PLAN §7 before May 2027:
- How to meet the DPDP Rule 8(3) one-year log retention without breaking the 30-day message deletion.
- The WhatsApp §4.7 risk. Do not build or pay for WhatsApp until the owner accepts that Meta can refuse an AI-first bot. If possible, apply for a WhatsApp Business account first and describe it as a domain-specific fact-check service before writing code.

None of the October 2026 findings changes where the app should run. Nothing requires India data residency, apart from unverified CERT-In log questions.

## Unknowns

- Whether the '13 March 2027' date (India-Briefing, 7 Oct 2026) has any official basis. No gazette, PIB or tracker source supports it, and every other source keeps 13 May 2027. The egazette text of S.O. 5458(E) was not fetched.
- Whether 'such personal data' in DPDP Rule 8(3) forces keeping message content for 1 year, or only logs. No MeitY FAQ or guidance was found.
- Lawful basis under DPDP for third parties' personal data in forwarded messages. s.7 legitimate uses do not clearly cover it, and s.3(c)(ii) excludes only data the person made public themselves or published under a legal obligation.
- Whether Meta would class a single-purpose LLM fact-check bot as an 'AI Provider' with AI as 'primary' functionality. This is Meta's discretion, and no India-specific ruling or CCI order was found.
- Whether the app is an 'intermediary' under IT Act s.2(1)(w). This decides the IT Rules grievance-officer and takedown duties and whether the CERT-In 2022 directions apply (6-hour incident reports, 180-day logs). CERT-In applicability to an individual was not verified this run.
- Current status of MeitY's 15 Mar 2024 AI advisory (labelling of unreliable AI output). No 2026 source confirms it is still in force or rescinded.
- The Anthropic AUP page shows 'Effective November 12, 2026'. Which version applies before that date was not checked; the AI-disclosure rule appears in both.
- Sarvam's Privacy Policy and DPA terms on training with API audio were not fetched; only the ToS and the retention page were read.
- Instagram/Meta terms text was not re-fetched this run (Instagram help-centre page returned no content), and the Google APIs Terms last-modified date was not captured.
- Indian defamation and copyright fair-dealing positions for AI-generated fact-checks are untested in court; the defamation finding comes from background knowledge.

