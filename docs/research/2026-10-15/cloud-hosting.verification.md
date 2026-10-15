# Verification: Cloud hosts for running the app 24/7

status: complete (2026-10-15; 25 web calls, $0 spent)

Verifier: adversarial verification agent, 2026-10-15. Target: `cloud-hosting.md` (same folder).
Method: for each decision-critical finding (F1-F6) and each price/plan/timeout/free-tier claim the
recommendation rests on, try to REFUTE it with primary sources (official pricing/docs pages,
vendor changelogs), searched afresh. Verdicts: confirmed / corrected / refuted / uncertain
(uncertain is preferred over confirming on secondary reports). No money spent; no other file touched.

## Verdicts

### F5a. Lightsail prices and bundle (Mumbai $7 plan) - CONFIRMED

- Claim: $7/month = 1 GB RAM, 2 vCPU, 40 GB SSD, 2 TB transfer (Mumbai: half, so 1 TB); $5 = 512 MB/20 GB/1 TB; $12 = 2 GB/60 GB/3 TB; IPv6-only $3.50/$5/$10; snapshots $0.05/GB-month.
- Evidence: the official pricing page (fetched 2026-10-15, footer "(c) 2026") lists exactly these General Purpose Linux bundles with public IPv4, and says plans in Asia Pacific (Mumbai), Sydney, Jakarta, Malaysia, Hong Kong and Sao Paulo "include half the data transfer allowances mentioned in the bundles above". Snapshots "$0.05 USD GB/mo" for manual and automatic, instance and disk. IPv6-only: $3.50 / $5 / $10.
- Small notes, not errors: (1) 2 vCPU applies to servers created after 29 June 2023 (page footnote); new ones get 2. (2) The page says a static IP is "included in all Lightsail plans" but does not state the unattached-IP charge, so "free while attached" is consistent but its other half (charged when unattached) was not verified. (3) The page does not mention that Lightsail bundles are burstable (a CPU baseline with credits, per Lightsail's own burst-capacity docs - known to the verifier, not re-fetched this session); the researcher did not mention it either. It matters little for an app that idles, but ffmpeg bursts draw on those credits.
- Free trial: the page says only "As part of the AWS Free Tier, you can get started with Amazon Lightsail for free", with no amount, dates or "3 months". So the researcher's "treat any free period as unconfirmed" stands; nothing in the recommendation rests on it.
- Source: https://aws.amazon.com/lightsail/pricing/ (fetched 2026-10-15; (c) 2026).

### F5b. AWS India (AISPL) payment: RuPay, net banking, UPI, UPI AutoPay, card e-mandate up to INR 15,000, INR 2 verification charge - CONFIRMED (one sub-claim not shown on the page)

- Evidence (AWS Billing docs, "Managing your payments in India", fetched 2026-10-15): "AWS supports Visa, Mastercard, American Express, and RuPay credit and debit cards for AWS India accounts ... internet banking (net banking) ... Unified Payments Interface (UPI) ... You can only use e-mandates for charges up to INR 15,000." "We currently support automatic payments up to INR 15,000 for each bill. You are required to make manual payments to bills that exceed INR 15,000." Saving a card: "charged 2 Indian rupee (INR) ... refunded ... within 5-7 business days." UPI AutoPay is a documented automatic-payment method.
- Details the researcher left out, all relevant to a cost-conscious individual: (1) net banking "can't [be used] for automatic payments" - each bill needs a bank redirect; (2) the card e-mandate checkbox is unavailable "if your credit or debit card is not supported" - "Contact your bank to learn more about e-mandate support", so card AutoPay is bank-dependent, and UPI AutoPay is the safer automatic route; (3) "Manual payments are temporarily disabled up to 96 hours while AWS attempts to charge your card automatically"; (4) failed automatic charges are retried several times with an email each time (no instant suspension is described).
- Not shown on this page: that AISPL invoices are in rupees. It is implied (RuPay, net banking and UPI are rupee rails; limits are in INR) and is standard AISPL practice, but this page does not say it; the researcher cited no page that does. Also not checked: that an Indian individual's new account lands on AWS India (the page defers to "Finding the seller of record").
- Source: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/edit-aispl-payment-method.html (fetched 2026-10-15; no updated date shown; mentions an AISPL "legacy model" migration "expected to be completed by December 2026", so it is current).

### F6. DigitalOcean Basic droplets $4 (512 MiB) / $6 (1 GiB), backups 20% weekly / 30% daily, snapshots $0.06/GB-month, USD only + 18% GST - CONFIRMED on prices; CORRECTED on sourcing and on payment risk

- Evidence, pricing page (digitalocean.com/pricing/droplets, fetched 2026-10-15, (c) 2026): $4/mo = 512 MiB, 1 vCPU, 10 GiB SSD, 500 GiB transfer; $6/mo = 1 GiB, 1 vCPU, 25 GiB SSD, 1,000 GiB transfer ($0.00893/hr). "Percentage-based Backups, set at 20% (Weekly) or 30% (Daily) of Droplet cost." Snapshots "$0.06/GB per month". "Effective January 1, 2026" Droplets get "per-second billing (with a minimum charge of 60 seconds or $0.01, whichever is higher)". Bangalore is listed as a datacenter; there is no per-region price anywhere on the page, so the single price applies (the researcher's worry that BLR1 might differ finds no support).
- Evidence, India tax page (docs.digitalocean.com/platform/billing/taxes/ind/, "Last verified 22 Jun 2026"): "As of 1 July 2017, DigitalOcean charges Goods and Services Tax (GST) ... The current tax rate is 18%." Adding a GSTIN stops DO charging GST (reverse charge instead). "USD is the only currency we accept for payments, so all invoices are in USD."
- Correction 1 (sourcing): the researcher attributed "Debit and credit cards are accepted, charged on the 1st of each month" and "per-second billing" to the India tax page. That page says neither; per-second billing is on the pricing page, and payment methods are on a separate "Manage payment methods" page (last verified 13 July 2026 per search results) which, per the search summary, does NOT list RuPay and requires Indian cards to have international transactions enabled. The Options-table claim "Accepts ... PayPal and Google Pay" was not verified; an older version of that page reportedly allows PayPal only for prepayment.
- Correction 2 (new, matters for the ranking): DigitalOcean now sells two kinds of Droplet. The $6 plan is a "Bundled Plan" ("a public IPv4 is included at no extra cost"; "a monthly cap, so you'll never pay more than the flat monthly price"). The new "v5" configurations bill hourly with no cap, and their public IPv4 is a separate line item whose "introductory line-item price is currently $0.00/hour, but is subject to change". The cheapest 1 GB v5 example starts at $0.024/hour (about $16-17/month, the verifier's arithmetic). The owner must pick the Basic Bundled plan or the price claim does not hold.
- Correction 3 (payment risk): no DigitalOcean page ties Indian-card declines to RBI e-mandate rules, but DO auto-charges a USD card monthly, exactly the pattern behind the Railway/Fly declines the researcher counted against those two. The research calls DO "equivalent" to Lightsail and penalises only Railway and Fly. On the evidence, DO carries the same class of risk (unverified either way: no primary source), while AWS India alone has documented domestic rails (UPI AutoPay).
- Sources: https://www.digitalocean.com/pricing/droplets (fetched 2026-10-15) - https://docs.digitalocean.com/platform/billing/taxes/ind/ (last verified 22 Jun 2026) - https://docs.digitalocean.com/platform/billing/manage-payment-methods/ (search summary only, not fetched; last verified 13 Jul 2026) - https://ideas.digitalocean.com/billing/p/upi-payment-method-support-for-indian-customers (users asking for UPI; not fetched).

### F2. Railway Hobby $5 incl. $5 usage; ~$10/GB-RAM-month, ~$20/vCPU-month, $0.15/GB-month volume, 5 GB Hobby volume cap; 15 min while data flows / 5 min idle; X-Real-IP; Singapore only Asian region - CONFIRMED (two omissions noted)

- Pricing (railway.com/pricing, fetched 2026-10-15, undated): Free Trial "$5 one-time credit (30 days)", 2 vCPU / 1 GB, 500 MB volume; Free "$1/month", "1 vCPU / 0.5 GB", 500 MB volume; Hobby fee "$5", credit "$5/month", "48 vCPU / 48 GB", max volume "5 GB"; Pro $20. Memory "$0.00000386 per GB/s" (~$10/GB-month), CPU "$0.00000772 per vCPU/s" (~$20/vCPU-month), volumes "$0.00000006 per GB/s" (~$0.15/GB-month), egress "$0.05 per GB". All match F2 exactly.
- Limits (docs.railway.com specs-and-limits, fetched 2026-10-15, undated): "HTTP requests can run for up to 15 minutes if data keeps transferring", "otherwise closed after 5 minutes with no data transferred", "Request bodies must finish uploading within 5 minutes", "Idle HTTP/1.1 connections are closed after 60 seconds between requests", "X-Real-IP for identifying client's remote IP". No proxy IP range and nothing on whether a client-supplied X-Real-IP is overwritten - so the researcher's "I assumed it overwrites it" remains UNCERTAIN and must be tested on the platform (free: send a forged X-Real-IP and log what arrives) before the limiter relies on it.
- Regions (docs.railway.com/reference/regions, fetched 2026-10-15): US West Metal (California), US East Metal (Virginia), EU West Metal (Amsterdam), Southeast Asia Metal (Singapore). No India region; Singapore is the only Asian one. Confirmed.
- Omission 1 (resolves a listed unknown): volumes DO have backups - "Services with volumes support manual and automated backups" (docs.railway.com/reference/volumes, fetched 2026-10-15); schedules/retention are on a separate guide, not checked.
- Omission 2 (the same drawback the research counted against Render): "there will be a small amount of downtime when re-deploying a service that has a volume attached ... we prevent multiple deployments from being active", and "Replicas cannot be used with volumes". The research lists deploy downtime only under Render, so the Railway-vs-Render comparison is tilted. (One instance is what this app needs anyway: its stream registry and limiter are in-memory.)
- The bot as a second Railway service is fine: scripts/telegram_bot.py talks to the app over HTTP (APP_BASE, default http://127.0.0.1:8000/api/v1) and opens no database, so it needs no volume; APP_BASE must then point at the app's private-network address.
- Sources: https://railway.com/pricing - https://docs.railway.com/networking/public-networking/specs-and-limits - https://docs.railway.com/reference/regions - https://docs.railway.com/reference/volumes (all fetched 2026-10-15; no page dates shown).

### F1. Render: free cannot run the app; paid minimum Starter $7 (512 MB / 0.5 CPU) + disk $0.25/GB-month; a disk disables zero-downtime deploys; no other service can read the disk - CONFIRMED on behaviour and specs; prices CONFIRMED only from Render's own secondary pages; one rename the research missed

- Disk behaviour (render.com/docs/disks, fetched 2026-10-15, (c) 2026): "You can attach a persistent disk to a paid Render web service, private service, or background worker" (so free cannot); one snapshot every 24 hours, "available for at least seven days"; "Adding a disk to a service prevents zero-downtime deploys ... Render stops the existing instance before bringing up the new instance"; "A persistent disk is accessible by only a single service instance"; "You can't access a service's disk from any other service"; "You can't scale a service to multiple instances if it has a disk attached." All as the research says.
- Specs (render.com/docs/compute-plans, fetched 2026-10-15): plan "0.5c-512mb" (legacy name "starter") = 0.5 CPU / 512 MB; next size up is "1c-2g" (legacy "standard", 1 CPU / 2 GB). NEW, missed by the research: "Render introduced new compute plan IDs in August 2026"; legacy names stay valid "with the same specs and pricing". So "Starter" is now 0.5c-512mb in the dashboard/Blueprints - same thing, new label.
- Prices: the pricing page is JavaScript-rendered for this verifier too (only headings came back). The $7/month Starter price comes from Render-authored articles (render.com/articles, one ~70 days old, per search results, not fetched) and $0.25/GB-month from an excerpt of render.com/pricing in search results. Render's changelog (23 April 2026, fetched) says "There are no changes to Render's existing compute pricing", and the compute-plans page says the renamed plans keep the same pricing. Net: the figures agree with everything Render publishes that could be read, but not with a readable price table. Treat as confirmed-with-caveat; check the dashboard's price before paying.
- Changelog (render.com/changelog/updated-plans-for-render-workspaces, fetched): dated "April 23, 2026"; "Hobby (free) replaces the legacy Hobby plan"; Pro "$25/month flat" (was $19 per member); Scale "$499/month flat" (was $29 per member); overage "$0.15 for each additional GB"; legacy workspaces move automatically "On August 1". It gives NO bandwidth amounts per plan - so the research's Unknown stays unknown. All confirmed.
- Not re-fetched: the free-instance page (15-minute spin-down, 750 hours). The no-disk half of "free is fatal" is independently confirmed by the disks page (paid only), which is enough for the conclusion.
- Bot note: confirmed in code that the bot needs no disk (it calls the app over HTTP), so running it inside the web service's start command, as the research suggests, is viable; a separate worker could not share the disk but does not need to.
- Sources: https://render.com/docs/disks - https://render.com/docs/compute-plans - https://render.com/changelog/updated-plans-for-render-workspaces (all fetched 2026-10-15) - https://render.com/pricing (fetched; unreadable) - render.com/articles/* (search results only).

### F3. Oracle Always Free: idle rule (7 days, CPU p95 < 20%, network < 20%, memory < 20% on A1) and the A1 allowance halved to 2 OCPU / 12 GB on 15 June 2026 - CONFIRMED (now from Oracle's own page); CORRECTED on "stops" and on the pay-as-you-go escape

- Idle rule, primary (docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm, fetched 2026-10-15, "Copyright (c) 2026"; the URL the researcher tried was a different one): "Idle Always Free compute instances may be reclaimed by Oracle. Oracle will deem virtual machine and bare metal compute instances as idle if, during a 7-day period, the following are true: CPU utilization for the 95th percentile is less than 20%; Network utilization is less than 20%; Memory utilization is less than 20% (applies to A1 shapes only)". The rule exists as stated; an app that idles between checks meets all three.
- Correction 1: the page says "may be reclaimed"; it does not say "stopped", and it names no action. Older reports describe stopping; the current text is vaguer, and "reclaimed" could be worse than a stop. Either way the bots would go silent.
- Correction 2: the page does not say that converting to pay-as-you-go prevents reclamation. That "older guidance" is not shown anywhere the researcher or this verifier could read, so the Options-table line "Acceptable only after upgrading to pay-as-you-go" rests on an unverified premise - UNCERTAIN.
- A1 allowance, primary (same page): "All tenancies get the first 1,500 OCPU hours and 9,000 GB hours per month for free ... For Always Free tenancies, this is equivalent to 2 OCPUs and 12 GB of memory." Confirmed. Note "All tenancies": per the doc, a pay-as-you-go tenancy gets the same free hours and pays for anything above them, which contradicts the support-email reports (quoted by InfoQ) that the new limit applies "only to free-tier accounts". The doc gives no change date.
- InfoQ (fetched; "Oracle Quietly Halves Free Tier Ampere A1 Compute Limits with No Public Announcement", Steef-Jan Wiggers, Jul 03, 2026): old 4 OCPU / 24 GB (3,000 / 18,000 hours), new 2 / 12 (1,500 / 9,000), effective June 15, 2026, no announcement, free-only instances above the limit shut down. Matches the research; secondary for the date, primary-confirmed for the numbers.
- Also confirmed on the same page (the research marked them "not re-verified"): 200 GB of block volume storage (boot + block combined) with five volume backups, and 10 TB/month outbound data; AMD VM.Standard.E2.1.Micro: up to two instances, 1/8 OCPU, 1 GB.
- Sources: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm (fetched 2026-10-15) - https://www.infoq.com/news/2026/07/oracle-cloud-free-tier-limits/ (Jul 3, 2026; fetched).

### F4. Hetzner price rise from 15 June 2026: Singapore CPX12 EUR 7.99 -> 15.49; DE/FI CX23 3.99 -> 5.49, CAX11 4.49 -> 5.99, CPX22 7.99 -> 19.49 (excl. VAT and IPv4) - CONFIRMED

- Evidence (docs.hetzner.com price-adjustment page, "Created on 2026-06-15", "Last change on 2026-07-08", fetched 2026-10-15): "The price adjustment took effect for new orders and cloud instance rescales starting on the 15 June 2026; 8 AM CEST." Table (EUR, excl. VAT, headers "excl. IPv4"): CAX11 DE/FI 4.49 -> 5.99; CX23 DE/FI 3.99 -> 5.49; CPX22 DE/FI 7.99 -> 19.49; CPX12 SIN 7.99 -> 15.49; also CPX22 SIN 15.99 -> 26.49. USD equivalents: CPX12 SIN $9.49 -> $17.99, CX23 $4.99 -> $6.49.
- Additions: "For orders placed before 15 June 2026, but delivered after 15 June 2026, the previous prices will apply", and "certain changes to servers with legacy pricing may trigger a switch to the current pricing" (so even an old server can be repriced by a rescale). No reason is given on the page.
- Not checked (low impact; Hetzner is not recommended): the Singapore product page's traffic figures and 'CPX02', the payment FAQ, the IPv4 add-on price.
- Source: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ (fetched 2026-10-15).

### F5c. (Implicit premise of the first choice) Lightsail is bought through AWS India, so the rupee rails apply to it - UNCERTAIN

- The recommendation joins two facts: Lightsail's USD price list (F5a) and AWS India's rupee payment rails (F5b). Nothing the researcher cited, and nothing this verifier found, says Lightsail is sold by AWS India (AISPL) to an India-address account. AISPL accounts are known to lack some services (Amazon Connect per a re:Post reply; some AWS-sold Marketplace items), so this is not automatic.
- What was found: AWS's "Setting up your India billing" page (search summary) says an India contact/billing country routes the agreement to AWS India with rupee invoices; a re:Post answer says older India-address accounts may sit under either AWS Inc. or AWS India depending on when they were opened; once on AWS India the contact country cannot be changed. An Indian reseller listing (Techjockey) prices Lightsail from INR 245 + GST, which hints at rupee billing but is secondary and names no plan.
- No contrary evidence either (nothing says Lightsail is excluded). Cheap way to settle it before committing: open the account, check Billing > seller of record = AWS India, launch the instance, and look at the first (prorated, hourly-billed) invoice line - all for a few rupees.
- Sources: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/manage-account-payment-aispl.html (search summary, not fetched) - https://repost.aws/questions/QUxKAuMaP8SCms8UR4dTBw-w/how-can-i-view-my-bills-and-receive-in-inr-currency (search summary) - https://www.techjockey.com/detail/amazon-lightsail (search summary; secondary).

### F7. Koyeb volumes unsuitable: public preview "only suitable for testing", 1-10 GB, Washington and Frankfurt only, standard instances only (not eco/free) - CONFIRMED

- Evidence (koyeb.com/docs/reference/volumes, "Last updated on May 27, 2026", fetched 2026-10-15): "Volumes are in public preview and are currently only suitable for testing"; "volumes must be between 1 and 10 Gigabytes in size"; "Volumes are currently only available in the Washington, D.C. (was) and Frankfurt (fra) regions"; "Volumes can only be attached to standard and GPU Services" (not eco-* or free); "bound to a single machine" and "there is no redundancy here and fault-tolerance is on you".
- Not checked: instance prices, the $29 pre-authorisation hold, the free instance's 1-hour sleep, and the "joining Mistral AI" claim. None changes the "avoid" verdict, which rests on the volume facts above.
- Source: https://www.koyeb.com/docs/reference/volumes (fetched 2026-10-15).

### F8. Fly.io: no free allowance for new organisations; trial 2 machine-hours or 7 days; shared-cpu-1x 512 MB $3.69 / 1 GB $6.70 (US), Singapore x1.269; volumes $0.15/GB-month; IPv4 $2; India egress $0.12/GB; no Mumbai region - CONFIRMED (pricing parts)

- Evidence (docs.fly.io/about/pricing - fly.io/docs/about/pricing/ now 301-redirects there - fetched 2026-10-15, undated): "New organizations don't have a free tier or a monthly free usage allowance"; trial "lasts for up to 2 hours of Machine runtime or 7 days, whichever comes first"; 512MB $3.69, 1GB $6.70 in iad/ewr; "Machine prices vary by region", sin multiplier 1.269 (1 GB about $8.50); volumes "$0.15/GB per month of provisioned capacity"; "Starting January 1st 2026, we're introducing charges for volume snapshot storage" at $0.08/GB with the first 10 GB free; "Dedicated IPv4 addresses are $2/mo"; "$0.12/GB in Africa and India" ($0.04/GB rest of Asia Pacific); no India region listed.
- Not checked: Fly-Client-IP (request-headers doc), the proxy idle timeout (forum posts, secondary by nature), Indian-card threads.
- Source: https://docs.fly.io/about/pricing (fetched 2026-10-15).

### F11. Client-IP headers per platform; "a plain VM with no proxy sees the real client IP" - PARTLY CONFIRMED, PARTLY CORRECTED

- Railway: X-Real-IP is the documented client-IP header (confirmed, see F2). Whether Railway overwrites a client-supplied X-Real-IP is undocumented - UNCERTAIN; the research's assumption must be tested on the platform before the limiter trusts it.
- Render (CF-Connecting-IP via Cloudflare) and Fly (Fly-Client-IP): not re-checked this session.
- VM path, CORRECTED: the recommendation itself puts Caddy in front of uvicorn for HTTPS, so "no proxy sits in front" is false. The outcome still holds by default, for two documented reasons: Caddy's reverse_proxy "sets or augments the X-Forwarded-For header field" and ignores client-supplied X-Forwarded-* values "to prevent spoofing" unless the sender is in trusted_proxies (caddyserver.com docs, fetched 2026-10-15); and uvicorn trusts proxy headers only from 127.0.0.1 by default (uvicorn 0.51 config, per this repo's audit-ops.md). So app/api/limits.py:119 (request.client.host) gets the real client - provided FORWARDED_ALLOW_IPS stays at its default and is NEVER set to '*'. The correct instruction is "leave the default (127.0.0.1)", not "no proxy".
- Side effect the research did not mention: app/api/dashboard.py returns 404 for any request carrying a proxy header (lines 40-59), so behind Caddy the spend dashboard is unreachable from the internet (good) and the owner reaches it by SSH port-forward (ssh -L 8000:127.0.0.1:8000), which arrives from loopback with no proxy header. On Railway/Render there is no loopback path at all without a platform shell.
- Source: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy (fetched 2026-10-15); repo files app/api/limits.py, app/api/dashboard.py, docs/research/2026-10-15/audit-ops.md (read 2026-10-15).

### Not checked (budget: 25 web calls used)

- F9 Azure, F10 Google Cloud, F13 Hostinger / E2E: no recommendation rests on them; their Options-table rows remain as unverified as the researcher left them.
- F12 Indian-card declines (Railway 2021-25, Fly 2021-23): forum evidence by nature; no primary source can confirm or refute it. The fairness problem is noted under F6: the same risk class applies to every USD auto-charging provider (DigitalOcean, Render, Hetzner), not only the two named.
- WhatsApp webhook TLS (a researcher Unknown): Meta's general Graph API and Messenger webhook docs say self-signed certificates are not supported (search summary; one page sits under an old v2.5 path); no WhatsApp-specific statement found. Leaning confirmed, still uncertain. Search: https://developers.facebook.com/docs/graph-api/webhooks/v2.5 and https://developers.facebook.com/documentation/business-messaging/messenger-platform/webhooks (not fetched).

## Tally

Of the 6 decision-critical findings and the price/plan/timeout claims the recommendation uses: **none refuted**. Confirmed against primary pages: F1 (behaviour, specs; prices only via Render's own secondary pages), F2, F3 (rule and allowance), F4, F5a, F5b, F6 (prices), F7, F8. Corrected: F3 ("may be reclaimed", not "stops"; the pay-as-you-go escape is undocumented), F6 (sourcing, the v5-vs-Bundled trap, payment-risk parity), F11 (Caddy is a proxy). Uncertain: F5c (is Lightsail billed through AWS India?), Railway's handling of a forged X-Real-IP, AISPL's rupee invoicing on the cited page, the WhatsApp TLS rule. Not checked: F9, F10, F12, F13.

## Recommendation check

**The first choice follows from the evidence, with one link to verify before paying.**

- Lightsail Mumbai $7 is supported: the price, bundle and Mumbai's halved transfer allowance are confirmed on AWS's page. The AWS India rupee rails are confirmed in AWS's docs. Being a plain VM, it has no sleep and no platform timeouts.
- The one unproven link is that Lightsail is actually sold through AWS India (F5c). If it is not, Lightsail is still the best price-and-location pick, but its "lowest payment risk" edge falls to DigitalOcean's level.
- Settle F5c for a few rupees: open the account, confirm the seller of record is AWS India, run the instance for an hour and read the invoice line.
- Prefer UPI AutoPay to card AutoPay. Card e-mandates depend on the issuing bank (F5b).
- ₹730/month is the instance alone. Automatic snapshots, if switched on, add $0.05/GB-month of stored snapshot data. That is small for a mostly empty 40 GB disk, but it is not zero.

**DigitalOcean "equivalent" is overstated.** The prices are confirmed, and it is a fair second, but not an equal one:
- It bills in USD only.
- RuPay is not listed. Indian cards need international transactions switched on.
- It auto-charges a card every month. That is the same failure class the research counted against Railway and Fly but not against DigitalOcean.
- The owner must pick the Basic Bundled $6 plan. A "v5" configuration costs about 2-3x as much and its IPv4 line item "is subject to change".

**The Railway fallback stands, with two corrections:**
- A Railway service with a volume also has "a small amount of downtime" on every redeploy and cannot use replicas. The research's Render-vs-Railway contrast, which counted deploy downtime against Render only, is therefore tilted. (One instance is what this app requires anyway.)
- Railway volumes do have manual and automated backups.
- Before the limiter relies on X-Real-IP, test on the platform, at no cost, that a client-forged X-Real-IP is overwritten.

**Render as the alternative PaaS stands.** Two fixes:
- The line "Render Starter ($7.25 + disk)" double-counts: $7.25 already includes a 1 GB disk.
- "Starter" is now plan "0.5c-512mb" (renamed August 2026).

**The Avoid list holds.** Every entry checked is confirmed: Render free has no disk; Koyeb volumes are test-only; Hetzner Singapore costs EUR 15.49; Fly has no free tier; Railway Free is $1 and 0.5 GB. Two caveats:
- Oracle's "acceptable after a pay-as-you-go upgrade" is unproven. Oracle's page documents no exemption from idle reclamation, and it gives all tenancies the same free A1 hours.
- E2E Networks was not checked.

**The rate-limiter bullet has the right outcome for the wrong reason.**
- Caddy is a reverse proxy. The limiter still sees real clients for two reasons: Caddy ignores client-sent X-Forwarded-* by default, and uvicorn trusts proxy headers only from 127.0.0.1 by default.
- The instruction should read: "keep FORWARDED_ALLOW_IPS at uvicorn's default; never '*'; pin it with a test".

**Overall:** the ranking Lightsail > DigitalOcean > Railway > Render is consistent with the verified evidence. No decision-critical figure was wrong. The gaps are about payment-risk fairness and deployment details, not prices.

## Missed

1. **Lightsail through AWS India is assumed, not shown** (F5c). Check it before relying on rupee billing.
2. **AWS India payment details:**
   - Net banking cannot auto-pay.
   - Card AutoPay needs the bank's e-mandate support.
   - UPI AutoPay is the robust automatic route.
   - Manual payment is blocked for up to 96 h while an automatic charge is attempted.
   - Failed automatic charges are retried, with an email each time.
3. **DigitalOcean's v5-vs-Bundled split** (Jan 2026 page). Only the Bundled plans have the flat $6 price with IPv4 included.
4. **Railway volume behaviour:** redeploy downtime and no replicas, but backups exist.
5. **Render plan rename** (August 2026): 0.5c-512mb = Starter, 1c-2g = Standard.
6. **Oracle's current wording** is "may be reclaimed". No pay-as-you-go exemption is documented. "All tenancies" get the same 1,500 OCPU-h / 9,000 GB-h, which contradicts the support-email claim InfoQ reports. The 200 GB block storage and 10 TB egress are now confirmed from the primary page.
7. **Hetzner repricing:** a rescale can move a legacy-priced server onto the new prices. Orders placed before 15 June 2026 keep the old prices.
8. **Operator access on a VM.** The spend dashboard 404s behind Caddy (any proxy header). The owner reaches it by `ssh -L 8000:127.0.0.1:8000`. On Railway or Render there is no loopback path, so the spend truth is unreachable without a platform shell.
9. **Lightsail bundles are burstable** (a CPU baseline with credits). That is harmless for an idle app, but long ffmpeg runs spend credits. This is from Lightsail's docs as known to the verifier, not re-fetched.
10. **Checked and fine, not missed:** the daily cap's "India's day" is computed from UTC plus a configured IST offset (app/store/repository.py:32-41, app/config.py:89), so a cloud VM on UTC does not shift the cap's day boundary. The bot calls the app over HTTP and needs no disk on any platform.
11. **Still open from the research's Unknowns:**
    - Render's bandwidth allowance per plan (the 23 April 2026 changelog gives no number).
    - Whether new accounts get a Lightsail trial (the pricing page says only "get started ... for free").
    - The INR/USD rate (₹88 assumed, unverified).
