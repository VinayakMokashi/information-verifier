# Verification of policy-legal.md

**status: complete** (2026-10-15).

**Tally of the decision-critical findings:**
- **F1 (DPDP dates): confirmed.** Verified against the official Rules (G.S.R. 846(E)), the corrigendum (G.S.R. 892(E)) and the Act's commencement notification (G.S.R. 843(E)). Rule 4 and s.6(9) start 13 Nov 2026; everything else starts 13 May 2027. The Oct 2026 Removal of Difficulties Order is uncertain, because only secondary sources were found, but none of them says it moves a date. "13 March 2027" is unsupported.
- **F2 (Rule 8(3) one-year retention): confirmed and stronger.** Illustration Case 1 keeps the personal data itself, and Rule 6(1)(e) adds a second one-year duty.
- **F3 (WhatsApp AI-provider ban): text confirmed; risk is uncertain.**
- **F4 (Meta AI-provider markets): confirmed.**
- **F5 (no start-up exemption): confirmed.**

**Other findings:** F6, F7, F9, F10 and F12 confirmed (F7's commencement date and F9's missed high-risk rules noted); F8 uncertain (secondary reports only); F11, F13 and F14 not re-checked.

Verifier: adversarial verification agent, 2026-10-15. Method: for every decision-critical finding and every date a recommendation rests on, try to REFUTE it from primary sources (gazette / MeitY / PIB / court records / the vendors' own terms pages), fetched afresh. Verdicts: confirmed / corrected / refuted / uncertain. "Uncertain" is used where only secondary sources (law-firm blogs, news) were reachable. This is practical guidance, not legal advice.

## Verdicts

### Primary source obtained for all DPDP Rules verdicts

The official Gazette of India copy of the DPDP Rules, 2025, as hosted by MeitY (https://www.meity.gov.in/static/uploads/2025/11/53450e6e5dc0bfa85ebd78686cadad39.pdf). The page refuses the web fetcher (403) but downloads with a browser user agent. It is 41 pages, Hindi then English, and its English text was extracted and quoted from directly. The masthead reads "No. 760, NEW DELHI, THURSDAY, NOVEMBER 13, 2025", "G.S.R. 846(E) ... New Delhi, the 13th November, 2025", and the gazette ID is CG-DL-E-14112025-267650. The 14 Nov in that ID is the upload stamp, which explains why some sources give 14 Nov. The issue date is 13 Nov 2025.

### F1 (part 1: the Rules' own commencement clauses): CONFIRMED, with one addition

- Verbatim: "(2) Rules 1, 2 and 17 to 21 shall come into force on the date of their publication in the Official Gazette. (3) Rule 4 shall come into force one year after the date of publication of this Gazette. (4) Rules 3, 5 to 16, 22 and 23 shall come into force eighteen months after the date of publication of this Gazette."
- So Rule 4 (consent managers) starts 13 Nov 2026, and Rules 3 and 5-16 (notice, security, breach, retention, contact, children, rights, grievance, transfers) plus 22 and 23 start 13 May 2027. Some trackers give 14 May 2027 because they count from the gazette ID's upload date. Treat the start as "13 May 2027, possibly read as 14 May", which changes nothing in practice.
- **Addition the colleague missed.** A corrigendum, G.S.R. 892(E) dated 10 Dec 2025, is on the e-Gazette (https://egazette.gov.in/WriteReadData/2025/268455.pdf) and refers back to the 13 Nov 2025 notification. Secondary sources (DPDP Wiki, search summary 2026-10-15) say it only rewords "of this Gazette" in Rule 1(3) and 1(4), not the periods. Its text could not be read: the e-Gazette fails certificate checks. Uncertain, but nobody reports a changed date.
- The Removal of Difficulties Order and the "13 March 2027" question are checked in F1 part 2 below.

### F2. DPDP Rule 8(3), one-year minimum retention from 13 May 2027: CONFIRMED (verbatim), and STRONGER than reported

- Verbatim (official gazette, English, p.27): "(3) Without prejudice to sub-rules (1) and (2), a Data Fiduciary shall retain, in respect of any processing of personal data undertaken by it or on its behalf by a Data Processor, such personal data, associated traffic data and other logs of the processing for a minimum period of one year from the date of such processing, for the purposes as specified in the Seventh Schedule, after which the Data Fiduciary shall cause such personal data and logs to be erased, unless further retention is required for compliance with any other law for the time being in force or notified by the Government."
- The Seventh Schedule ("[See rule 23(1) and 8(3)]") has three items: (1) State use in the interest of sovereignty, integrity or security; (2) State use for any function under law, or disclosure to meet a legal obligation; (3) assessment for notifying Significant Data Fiduciaries. This matches the colleague's description.
- Illustration Case 2 is as reported: the fiduciary must ensure its cloud processor "also retains the data and associated logs for at least one year".
- **What the colleague under-read.** Illustration **Case 1** largely answers their open question of whether "such personal data" means content and not only logs: "The platform Y must retain the order details, personal data, and logs of the processing ... for at least one year from the date of the transaction, **even if X deletes her account**." So the processed personal data itself is kept, and an erasure request does not shorten the year. For this app, a submitted message that contains personal data is probably covered. Still take legal advice on scope, but plan for keeping content.
- **Also missed: Rule 6(1)(e)**, a second, separate one-year retention duty in the same 13 May 2027 group, under the security safeguards. Verbatim: "(e) for enabling the detection of unauthorised access, its investigation, remediation to prevent recurrence and continued processing in the event of such a compromise, retain such logs and personal data for a period of one year, unless compliance with any law for the time being in force requires otherwise". Any 2027 retention redesign has to satisfy both 6(1)(e) and 8(3).
- Where the stored data lives: Rule 15 lets personal data go outside India subject only to requirements the Central Government may specify by order about making it available to a foreign State. Nothing in the Rules makes a one-year store sit in India, so the colleague's "Nothing requires the storage to be in India" holds for the DPDP Rules.
- Recommendation impact: the colleague's "record a §7 decision before May 2027" is right. Its framing ("keep a minimal access/processing log ... or get advice on whether content is covered") understates the duty: Case 1 points to content, and Rule 6(1)(e) adds a separate security-log year.

### F6. DPDP Rules content (Rules 3, 7, 9, 10, 14(3)): CONFIRMED against the official text

- Rule 3: standalone notice, "itemised description of such personal data", the specified purpose, a description of the goods or services, and the means to withdraw consent, exercise rights and complain to the Board. Matches.
- Rule 7(2): to the Board "(a) without delay" and "(b) within seventy-two hours of becoming aware of the breach, or within such longer period as the Board may allow". Rule 7(1): to each affected Data Principal "without delay". Matches.
- Rule 9: "prominently publish on its website or app ... the business contact information of the Data Protection Officer, if applicable, or a person who is able to answer on behalf of the Data Fiduciary". Matches.
- Rule 14(3): grievances answered "within a reasonable period not exceeding ninety days". Matches.
- Rule 10(1): verifiable parental consent, checked against (a) reliable identity and age details the fiduciary already holds, (b) details volunteered by the individual or a virtual token from an authorised entity, including a DigiLocker provider. Rule 10(2)(a): "adult" means 18 or over. Matches.
- The colleague's judgement that "an 18+-only service is the common practical route, and not a full legal answer" is fair. Self-declaration is not "verifiable" consent.

### F7. IT Amendment Rules 2026 (synthetically generated information, shortened timelines): CONFIRMED (content and notification date); commencement date UNCERTAIN

- Primary source: MeitY's consolidated IT (Intermediary Guidelines and Digital Media Ethics Code) Rules, 2021, "[updated as on 10.02.2026]" (https://www.meity.gov.in/static/uploads/2026/02/550681ab908f8afb135b0ad42816a1c9.pdf; 403 to the fetcher, downloaded with a browser user agent, text extracted). Every 2026 change carries the footnote "Ins./Subs. by **G.S.R. 120(E), dated 10.02.2026**". **That is the G.S.R. number the colleague did not capture.**
- Rule 2(1)(wa), verbatim: "'synthetically generated information' means **audio, visual or audio-visual information** which is artificially or algorithmically created, generated, modified or altered using a computer resource, in a manner that such information appears to be real, authentic or true and depicts or portrays any individual or event in a manner that is, or is likely to be perceived as indistinguishable from a natural person or real-world event". Routine editing, transcription and accessibility are carved out. Text answers are outside it, as the colleague said.
- Rule 3(3) labelling and due diligence apply "Where an intermediary offers a computer resource which may enable, permit, or facilitate the creation, generation ... of information as synthetically generated information". Matches.
- Timelines, each footnoted "Subs. by G.S.R. 120(E), dated 10.02.2026 for ...":
  - actual-knowledge removal under 3(1)(d): "three hours", replacing "thirty-six hours"
  - grievance resolution under 3(2)(a)(i): "seven days", replacing "fifteen days"
  - 3(1)(b) removal complaints: "thirty-six hours", replacing "seventy-two hours"
  - non-consensual intimate imagery under 3(2)(b): "two hours", replacing "twenty-four hours"
  
  All four match the colleague.
- **Commencement on 20 Feb 2026 is not stated in the consolidated text**, which shows only the 10.02.2026 notification date. It rests on secondary reports, so uncertain. This changes nothing for the app.
- Also in the same document: a separate amendment, G.S.R. 775(E) of 22.10.2025 (w.e.f. 15.11.2025), rewrote Rule 3(1)(d), the rule on who may issue takedown notices. It does not affect this app.
- Recommendation check: "respond within 7 days (IT Rules 2026)" is an IT Rules duty that binds only an *intermediary*. The colleague rightly flags that intermediary status is unclear. Using 7 days as a self-imposed target is harmless. The legally binding DPDP figure (from 13 May 2027) is the Rule 14(3) cap of 90 days.

### F9. Anthropic (Usage Policy, Commercial Terms, retention): CONFIRMED on every stated fact, but it MISSES the Usage Policy's high-risk rules

All sources fetched 2026-10-15 from Anthropic's own pages.

- **Retention: confirmed.** privacy.claude.com article 7996866 shows the date "July 1, 2026". It says: "we automatically delete inputs and outputs on our backend within 30 days of receipt or generation". The exceptions are a longer-retention service under your control (e.g. Files API), an agreement otherwise (e.g. zero data retention), "to enforce our Usage Policy", and "In compliance with the law". Flagged content: "up to 2 years"; "trust and safety classification scores for up to 7 years"; feedback: 5 years. The page says nothing about the web-search tool.
- **Commercial Terms: confirmed.** Effective June 17, 2025. §B: "Anthropic may not train models on Customer Content from Services." **§D.3: "Customer acknowledges, and must notify its Users, that factual assertions in Outputs ... should not be relied upon without independently checking their accuracy."** Preamble: "Services under these Terms are not for consumer use." There is no clause about minors. Note for the drafted Terms: D.3 is specifically about *factual assertions* and *independent checking*. For a fact-checker the notice should say to check the linked sources before relying on an answer, not only that answers "can be wrong".
- **AUP version dates: confirmed.** The live page says "Effective November 12, 2026". Its "Previous Version" (anthropic.com/legal/archive/22742366-2ef0-4c7a-a833-6523f10d3944) is "Effective September 15, 2025" and is the one in force today.
- **AUP disclosure rule: confirmed, but stricter than the colleague's wording.** The version in force today says: "All consumer-facing chatbots, including any external-facing or interactive AI agent, must disclose to users that they are interacting with AI rather than a human", and "must be provided **at a minimum at the beginning of each chat session**". The Nov 2026 version keeps the disclosure for "All consumer-facing chatbots or AI agents that communicate directly with external users". A Telegram chat has no session boundary, so a line in /start alone is thin. A short "AI-written" tag on **every answer** satisfies both versions at no cost.
- **Minors: confirmed.** Both versions: "We define a minor or child to be any individual under the age of 18 years old, regardless of jurisdiction". Products serving minors must follow the linked guidelines. The guidelines page's date (16 Mar 2026) was not re-fetched.
- **Misinformation: confirmed.** "Do Not Create or Spread Disinformation" covers people or groups, "political and electoral contexts", and "medical, health, or science issues".
- **MISSED: the high-risk use-case requirements.**
  - *In force today (Sep 2025 version):* the high-risk list includes **"Media or professional journalistic content" ("automatically generate content and publish it for external consumption")** and Healthcare (medical guidance). For high-risk uses that "directly affect individuals or consumers", "a qualified professional in that field must review the content or decision prior to dissemination", and AI use must be disclosed. An answer returned privately to the person who asked is a weak fit for "publish for external consumption". But a public feed of fact-checks, an auto-posting channel, or answers republished as articles would fit it squarely. So do not build any "publish" surface without re-reading this.
  - *From 12 Nov 2026:* "High-risk AI Recommendations" in 11 areas, including **Medical** ("diagnosing a condition; recommending, starting, stopping, or adjusting a treatment or medication ...") and **Legal** ("advising an individual on their legal rights ..."). These need meaningful review by a qualified person before delivery, plus disclosure. They explicitly exclude "General information or educational content ... without applying it to the individual's circumstances."
  - A claim check ("is this forwarded health claim true?") is general information. A user asking "should *I* stop my medicine?" is not. The prompt and triage should decline individualized medical, legal or financial advice, and the Terms should say so.

### F3. Meta Terms for WhatsApp Business Platform §4.7 (AI Providers): CONFIRMED; the risk rating is a judgement, so treat it as UNCERTAIN, not "high"

- Fetched 2026-10-15 from facebook.com/legal/Meta-Terms-for-WhatsApp-Business-Platform. The page says "Last Modified: September 23, 2026".
- §4.7, verbatim fragments:
  - "Providers and developers of artificial intelligence or machine learning technologies, including but not limited to large language models, generative artificial intelligence platforms ... or similar technologies as determined by Meta in its sole discretion ("AI Providers")"
  - "are strictly prohibited from accessing or using the WhatsApp Business Platform, whether directly or indirectly"
  - the prohibition applies "when such technologies are the primary (rather than incidental or ancillary) functionality ... as determined by Meta in its sole discretion"
  - "Notwithstanding the foregoing, you may retain an AI Provider as your Solution Provider"
  - "such technologies may be made available to businesses in certain countries as set forth" on a linked page
  - Training: WhatsApp Business Platform Data may not be used "to create, develop, train, or improve any machine learning or artificial intelligence systems", except fine-tuning a model "for your exclusive use".
- Everything the colleague quoted is accurate.
- **Why the rating is softened.** Meta's own developer page (F4) describes what is restricted as "general-purpose AI assistants". A single-purpose claim checker that refuses off-topic chat is not obviously one, and the owner does not *develop* AI technology, he builds an app on it. Whether it counts as an "AI Provider" with AI as "primary" functionality is Meta's call and cannot be settled from the text.
- The colleague's recommendation (apply for a WhatsApp Business account and describe it as a domain-specific fact-check service *before* writing code, and accept that Meta can refuse) follows from the evidence and is the right hedge.

### F4. Meta "AI Providers" markets page: CONFIRMED

- Fetched 2026-10-15 from developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers: "Markets and effective dates (updated as of May 12, 2026)".
- AI Providers "are only permitted to offer general-purpose AI assistants on the WhatsApp Business Platform ... where Meta is legally required to permit this use case."
- Markets:
  - Italy (+39): 16 Feb 2026 to 12 May 2026
  - 29 EEA countries: 11 Mar 2026 to 12 May 2026
  - Brazil (+55): from 11 Mar 2026, no end date
  - **India (+91): not listed**
- From 13 May 2026, "Meta will no longer charge 'AI Providers' for non-template messages ... in certain markets".
- Category names: webhooks `general_purpose_ai`, pricing analytics `AI_BOT`.
- The colleague's inference holds: there is no paid "AI provider" route in India.

### F10. Sarvam data retention: CONFIRMED

- Fetched 2026-10-15 from docs.sarvam.ai/api/platform/data-retention; the page shows no date.
- "Until an Owner sets a retention period, your workspace's data is retained indefinitely."
- "Only a workspace's org Owner can change retention settings", under "Settings → Workspace → Data retention".
- Options run from "No retention (0 days)" to 24 months (730 days). Zero-day retention is supported for Model APIs; it "is not yet supported for Voice Agents", which this app does not use.
- "Changing the retention period only affects data going forward."
- The recommendation "set Model APIs retention to 0 days today" follows directly. It is free, and past audio stays under the old (indefinite) setting.
- Not re-checked: the Sarvam ToS clause numbers (s.7.3, 8.1, 8.2, 17.5) and the training-use clause.

### F1 (part 2: has anything moved the dates?): CONFIRMED for the corrigendum; UNCERTAIN (secondary only) for the October 2026 Order; "13 March 2027" unsupported

- **Corrigendum, now read from the official e-Gazette.** https://egazette.gov.in/WriteReadData/2025/268455.pdf, downloaded with curl; the web fetcher fails its certificate check. It is "No. 806, NEW DELHI, THURSDAY, DECEMBER 11, 2025", "CORRIGENDA, New Delhi, the 10th December, 2025, G.S.R. 892(E)", referring to G.S.R. 846(E) of 13 Nov 2025. Its changes:
  - page 24 lines 22 and 24 (Rule 1(3) and 1(4)): "for 'of this Gazette', read 'in the Official Gazette'"
  - five typo fixes ("Departments", "given in such order", "every body", "(18 of 2013)", "(a) to (g)")
- **No period changes.** Rule 4 is one year, and Rules 3, 5-16, 22, 23 are eighteen months, "after the date of publication in the Official Gazette". The Gazette issue is dated 13 Nov 2025, so the dates are 13 Nov 2026 and 13 May 2027.
- **DPDP (Removal of Difficulties) Order, 2026: UNCERTAIN.** The official text was not found. MeitY and PIB searches returned nothing, and the one 2026 e-Gazette PDF the search surfaced (270936.pdf) is an unrelated weekly issue. Four independent secondary sources agree: CyberPeace, King Stubb & Kasiva, SS Rana per the colleague, and India Briefing per the search summaries. Their account:
  - It was issued 5 Oct 2026 and published 7 Oct 2026 under s.43(1).
  - It only inserts "of" in s.9(1) ("child or of a person with disability") and "data" before "audit" in s.10(2)(c)(ii).
  - It moves no commencement date.
  - The number "S.O. 5458(E)" appears in none of the sources this verifier saw. Treat the number as unverified.
- **"13 March 2027": UNSUPPORTED.** A dedicated search found no source giving it as a DPDP deadline. Its only March-2027 hit was an indicative SDF audit cycle in an analysis. The official corrigendum confirms the 18-month clock. Also note 13 Nov 2025 + 16 months = 13 Mar 2027, so the date would need a "sixteen months" amendment, and none was found. Plan on 13 May 2027.
- **MeitY's proposal to shorten the timelines: unnotified, as far as can be seen.** Secondary reports (Storyboard18, exchange4media) carry the IT Minister's Nov 2025 remarks about shortening the 18 months. No "DPDP (Amendment) Rules, 2026" appeared in the MeitY, PIB or e-Gazette results. This is absence of evidence, not proof. Re-check egazette.gov.in before launch.

### F5. No start-up or small-fiduciary exemption; an individual running a public service is a Data Fiduciary: CONFIRMED (PIB part from the primary source; Act-text part in the next entry)

- PIB Release ID 2198217, downloaded 2026-10-15 from pib.gov.in with curl (the fetcher gets 403). Its whole substantive text: "Posted On: 03 DEC 2025 4:49PM by PIB Delhi". It says the Act and Rules "have been notified on 13 November 2025, They provide a timelines for implementation"; the Board "has been notified"; "The Act and the Rules provide for a simplified compliance framework for start-ups and certain data fiduciaries"; "The Act and Rules provide for Government to notify jurisdictions where transfer of personal data may be restricted"; and an awareness paragraph. "This information was submitted by Union Minister of State ... Shri Jitin Prasada in Lok Sabha on 03.12.2025." **The colleague is right: it names no exemption and no notification.**
- PIB 2190014 (the Rules release) also speaks only generally of "a facilitative compliance regime for startups and smaller enterprises" and an "18-month phased compliance timeline". It lists no exemption.
- No s.17(3) notification turned up in any MeitY, PIB or e-Gazette search result. That is absence of evidence. The digitalindia.gov.in and KSK sources the colleague cited were not re-fetched.

### F8. Fact Check Unit at the Supreme Court: UNCERTAIN (consistent secondary court reporting; no SC order fetched); substance stands

- Reporting found 2026-10-15 (Storyboard18, Odishabytes; the colleague used LiveLaw): on Tue 10 Mar 2026 a three-judge bench led by CJI Surya Kant agreed to hear the Union's appeal against the Bombay HC judgment of 26 Sep 2024 (Justice A.S. Chandurkar's tie-breaking opinion) that struck down Rule 3(1)(b)(v), and refused to stay it.
- **Small correction.** Reports say the appeal was "admitted" or the court "agreed to hear". None this verifier saw says "issued notice". No later hearing was found.
- No obligation for the app follows either way, so the colleague's "does not apply; watch the appeal" stands.

### F12. Telegram Bot Developer Terms: CONFIRMED, with one nuance

- Fetched 2026-10-15 from telegram.org/tos/bot-developers; the page shows no date.
- §4: "all TPA must be bound by a privacy policy that is easily accessible to their users"; the Standard Policy "applies by default to all TPA that don't provide a privacy policy of their own"; if it "does not properly detail the ways in which you collect, process and use personal data", "you must provide a separate privacy policy"; "TPAs must set up a Privacy Policy in @BotFather".
- §4.2(a): delete user data on request. §4.4(a): data "encrypted at rest and stored separately from its encryption key".
- §4.3 ("Data Scraping"): no collecting or processing "beyond what is essential for the operation of your services", including "data collection aimed at creating large datasets, machine learning models and AI products". Data users submit may be used where users "give their individual, explicit, active and revocable consent" and are clearly told its intended use.
- **Nuance.** The consent sentence sits in the data-scraping clause, so it most clearly governs uses *beyond* running the service. The colleague's "one-time /start consent line" is still cheap insurance, because the bot forwards content to third-party AI.
- **Encryption at rest (§4.4(a)) is a concrete duty the recommendation does not list.** Check whether the SQLite answer store and transcript cache are encrypted at rest. If not, either encrypt them or keep the bot's data out of them.

### F1 (part 3: the Act's own commencement) and F5 (the Act's text): CONFIRMED from the official e-Gazette and MeitY's copy of the Act

- **Commencement: G.S.R. 843(E)**, "New Delhi, the 13th November, 2025" (e-Gazette 2025/267647.pdf, downloaded with curl):
  - "(a) the date of publication of this notification": s.1(2), s.2, ss.18-26, 35, 38-43, 44(1) and 44(3)
  - "(b) one year from the date of publication": s.6(9) and s.27(1)(d)
  - "(c) eighteen months from the date of publication": ss.3-5, 6(1)-(8) and (10), 7-10, 11-17, 27 except (1)(d), 28-34, 36, 37 and **44(2)**
- So in October 2026 no data-fiduciary duty, no right, and no penalty (s.33 and the Schedule) is in force. **The colleague's F1 is exactly right.**
- **Not drawn out by the colleague:** s.44(2) is the clause that **omits IT Act s.43A**. It is in the 18-month group, so **s.43A and the 2011 SPDI Rules made under it are still the law today**. See Missed.
- **Act text** (MeitY copy, meity.gov.in/static/uploads/2024/06/2bf1f0e9f04e6fb4f8fef35e82c42aa5.pdf), all as the colleague said:
  - s.2(i): "'Data Fiduciary' means any person who alone or in conjunction with other[s] ..."
  - s.2(s): "'person' includes -- (i) an individual"
  - s.3(c)(i): the Act does not apply to "personal data processed by an individual for any personal or domestic purpose"
  - s.3(c)(ii): it does not apply to data "made or caused to be made publicly available by (A) the Data Principal ... or (B) any other person who is under an obligation under any law"
  - s.17(3): may "notify certain Data Fiduciaries or class of Data Fiduciaries, including startups, as Data Fiduciaries to whom the provisions of section 5, sub-sections (3) and (7) of section 8 and sections 10 and 11 shall not apply"
  - Schedule item 1 (security safeguards, s.8(5)): "May extend to two hundred and fifty crore rupees"
  - s.9(3): no "tracking or behavioural monitoring of children" or targeted advertising at them
  
  A public service run by an individual is not a "personal or domestic purpose". F5 is confirmed.

### F11 (Google APIs Terms), F13 (YouTube Terms), F14 (defamation): NOT RE-CHECKED (not decision-critical; web budget spent on the critical items)

- F11: the cited clauses (§3(d) privacy-policy duty, §5(e) no permanent copies beyond cache headers and no stripping attribution, §6(b) attribution, §6(c) no implied endorsement) match this verifier's knowledge of the Google APIs Terms, but were not re-fetched. Uncertain on the dates.
- F13: the YouTube Terms date ("5 Jan 2022") was not re-fetched. YouTube revises its terms by region, so re-check the India version before quoting a date. The substance (no downloading, no automated access) is long-standing.
- F14: BNS 2023 s.356 (defamation, in force 1 Jul 2024, replacing IPC s.499/500) matches this verifier's knowledge. Not re-fetched. The colleague rated it low confidence themselves.

## Recommendation check

**Overall, the recommendation follows from the evidence:** publish a Privacy Notice and Terms before launch, put an AI line on every surface, set Sarvam to 0-day retention today, record two decisions in §7 before 13 May 2027, and do not build WhatsApp until Meta accepts an account. Every date it rests on is confirmed from primary text: Rule 4 and s.6(9) on 13 Nov 2026, everything else on 13 May 2027, and no date moved by the Oct 2026 Order or the Dec 2025 corrigendum. Corrections to make while drafting:

1. **Anthropic retention line.** "Deletes API data within 30 days" is the default only. The notice should add the exceptions: flagged content kept up to 2 years, classifier scores 7 years, and longer where the law requires.
2. **Terms reliability line (Anthropic Commercial Terms D.3).** D.3 requires telling users that "factual assertions in Outputs ... should not be relied upon without independently checking their accuracy". For a fact-checker, say "check the linked sources before relying on an answer", not only "can be wrong".
3. **AI disclosure placement.** The Usage Policy in force today requires it "at a minimum at the beginning of each chat session". A Telegram chat never restarts, so add a short "AI-written" tag to every answer, not only the /start message.
4. **"Right to complain to the Data Protection Board."** The Board exists, but the complaint and inquiry machinery (ss.13 and 27) only starts 13 May 2027. Word it as "from 13 May 2027".
5. **"Respond within 7 days (IT Rules 2026)."** This binds only intermediaries. As a voluntary service level it is fine. The binding DPDP limit from May 2027 is 90 days (Rule 14(3)).
6. **The 2027 retention decision is bigger than "a minimal log".** Rule 8(3) Illustration Case 1 keeps the personal data itself "even if X deletes her account", and Rule 6(1)(e) adds a separate one-year security-log duty. From 13 May 2027 the 30-day deletion (invariant 10), the planned /delete command and Telegram §4.2(a) delete-on-request all collide with a legal one-year minimum. The notice will have to say so. Record this in §7 now, not in 2027.
7. **"Sarvam retention is set to 0 days"** is true only once the owner changes the setting. Audio already sent stays under the old indefinite setting.
8. **WhatsApp.** Downgrade "strictly prohibited / high risk" to "Meta's discretion, uncertain". Meta's own page describes what it restricts as "general-purpose AI assistants". The colleague's hedge of applying first remains right.
9. **"Nothing requires India data residency."** This holds for the DPDP Act and Rules (Rule 15 allows transfers abroad subject only to future government orders). The CERT-In 2022 directions remain unverified; they require 180-day logs "within the Indian jurisdiction" if they apply, which could bear on hosting.

## Missed

1. **DPDP Rule 6(1)(e)**: a second one-year retention duty for logs and personal data, under the security safeguards, from 13 May 2027. Quoted verbatim in F2.
2. **Rule 8(3) Illustration Case 1** largely answers the colleague's open question: personal data, not just logs, is kept a year, "even if X deletes her account".
3. **The regime in force today is IT Act s.43A plus the 2011 SPDI Rules, not DPDP.** DPDP s.44(2), which omits s.43A, starts 13 May 2027 (G.S.R. 843(E)). The SPDI Rules bind a "body corporate", which by s.43A's explanation includes a sole proprietorship "engaged in commercial or professional activities". A free, non-commercial individual is probably outside them. That is this verifier's reading from knowledge, not re-fetched. If the owner ever charges, takes donations as a business, or registers a proprietorship, SPDI Rules 4, 5 and 8 apply: a website privacy policy, a grievance officer, and reasonable security practices. Also from knowledge: IT Act s.72A (disclosing personal information in breach of a lawful contract) is outside s.44(2) and stays. That is one more reason the notice should name every recipient (Anthropic, Google, Sarvam, the platforms).
4. **Anthropic Usage Policy high-risk use cases** (F9):
   - *Today:* "Media or professional journalistic content" ("automatically generate content and publish it for external consumption") and Healthcare guidance need review by a qualified professional before dissemination when they affect individuals.
   - *From 12 Nov 2026:* Medical and Legal "High-risk AI Recommendations" need the same, but general information is excluded.
   - Mitigations: decline individualized medical, legal or financial advice in the prompt or triage and in the Terms, and add no "publish" surface (public feed, channel, articles) without re-reading this.
5. **Telegram §4.4(a): data "encrypted at rest and stored separately from its encryption key".** This is a concrete technical duty in force now, and the recommendation does not mention it. Check the SQLite store and the transcript cache.
6. **A lawful basis for the submitter's own data exists.** DPDP s.7(a) (from May 2027) covers personal data a person "has voluntarily provided ... for the specified purpose" (the pharmacy-receipt illustration). That covers the submitter's own message, IP address and chat ID without a separate consent form. Third parties' data inside forwards remains the unsolved case, as the colleague said.
7. **IT Amendment Rules 2026**: the colleague did not have the number. It is G.S.R. 120(E), dated 10.02.2026.
8. **DPDP Rules corrigendum**: G.S.R. 892(E), 10 Dec 2025 (published 11 Dec), with wording fixes only. It was missing from the colleague's timeline.
9. **Still open after this verification:**
   - the official text and S.O. number of the Oct 2026 Removal of Difficulties Order
   - CERT-In applicability to an individual operator
   - Sarvam's ToS and privacy policy clauses on training
   - the date of Anthropic's minors guidelines
   - Instagram/Meta terms
   - the India version of YouTube's terms

Web calls used: about 26 (searches, fetches, and curl downloads of official PDFs and pages). Money spent: $0.

