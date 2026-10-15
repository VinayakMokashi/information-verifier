# Cloud hosts for running the app 24/7

Researched 2026-10-15 by a research agent (web sources dated in each finding). **Verification: 0 of 1 verifier(s) finished; the rest are still running or died (usage limit / network) - treat the unverified parts as unverified.** This file is the durable copy of the agent's result (the raw journals are session-internal and not kept).

## Summary

I compared 12 places to run the app 24/7 as of 15 October 2026, using 33 web calls. I resumed from the source trail of the killed attempt and fetched its primary pages directly.

**The free tiers don't work for this app.** Each one fails on at least one hard requirement:
- **Render free:** sleeps after 15 minutes idle and cannot have a disk.
- **Koyeb free:** sleeps after 1 hour idle, has no volumes, and runs only in Frankfurt or Washington.
- **Fly.io:** new accounts get no free tier (only a 2-hour or 7-day trial).
- **Oracle Always Free:** stops instances that stay under 20% CPU, network and memory use for 7 days. This app idles almost all the time. Oracle also cut the Ampere A1 allowance on 15 June 2026.
- **Google e2-micro:** free only in three US regions, with 1 GB of free egress a month.
- **Railway Free:** only $1 a month of usage and 0.5 GB of RAM.

**The cheapest options that fit cost $5–10 a month (about ₹450–900 plus 18% GST):**
- AWS Lightsail in Mumbai: $7 for 1 GB.
- DigitalOcean in Bangalore: $6 for 1 GiB, plus $1.20 for weekly backups.
- Azure Central India B2ats v2: $4.49 a month for compute, plus disk and public IP.
- Railway Hobby in Singapore: a $5 fee that includes $5 of usage.
- Render Starter in Singapore: $7, plus $0.25 per GB of disk.

**Prices that moved recently:**
- Hetzner raised prices from 15 June 2026. Singapore CPX12 went from €7.99 to €15.49, so it is no longer a budget choice in Asia.
- E2E Networks' smallest listed VM is about $32 a month.
- Hostinger KVM 1 is ₹599 a month introductory, paid upfront for 24 months, then ₹999 on renewal. Its official page does not name an India data centre.

**Long checks, live updates and the client-IP problem:**
- The app's SSE heartbeat is every 15 s (`app/api/stream.py:29`). That stays under every platform's idle cut-off: Fly about 60 s (some reports say 30 s), Railway 5 minutes with no data, and Railway's hard limit of 15 minutes per request.
- Background work runs inside the app process, so no platform's request timeout reaches it.
- On a PaaS the per-IP limiter must read a header the platform overwrites:
  - **Render:** `CF-Connecting-IP`. The leftmost `X-Forwarded-For` value can be forged.
  - **Fly.io:** `Fly-Client-IP`.
  - **Railway:** `X-Real-IP`.
- None of the three documents a stable proxy IP range. So `FORWARDED_ALLOW_IPS` cannot be narrowed to the proxy, and the header has to be read explicitly.
- A plain VM with no proxy in front sees the real client IP directly.

**Paying with an Indian card:**
- Railway (2021–25 forum reports) and Fly.io (2021–23) have both had Indian cards declined. Railway moved one such account straight to its trial plan, with no grace period.
- AWS India (AISPL) bills in rupees. It accepts RuPay, net banking and UPI AutoPay, and automatic card payments work up to ₹15,000 a bill. That makes Lightsail the lowest payment risk.

**Sources:** Render: changelog (23 Apr 2026), free-instance and disk docs. Railway: pricing page, limits and regions docs. Fly.io: pricing docs. Koyeb: pricing, instance, volume and FAQ docs. DigitalOcean: Droplet pricing page and tax docs. Lightsail: pricing page. Hetzner: price-adjustment page. Oracle: InfoQ (3 Jul 2026); the idle-reclaim rule comes from a search snippet of Oracle's docs, which I could not fetch. Google Cloud: free-tier page (updated 13 Oct 2026). Azure: Retail Prices API. AWS India: payment docs. Hostinger: official India VPS page.

## Findings

### F1. Render: the free web service cannot run this app; the paid minimum is a Starter instance at $7/month (512 MB, 0.5 CPU) plus a disk at $0.25/GB-month. A disk turns off zero-downtime deploys, and a background worker cannot share the web service's disk.
*Confidence: high — **decision-critical***

render.com/docs/free:
- Free web services spin down after 15 minutes with no inbound traffic.
- 750 free instance hours a month.
- Free services cannot use persistent disks.
- Local filesystem changes are lost on spin-down or redeploy.

render.com/docs/disks:
- Disks attach only to paid services.
- One snapshot every 24 hours, kept at least 7 days.
- With a disk, Render stops the old instance before starting the new one, so each deploy has a few seconds of downtime.
- A disk serves one instance only.
- "You can't access a service's disk from any other service."

Prices: the pricing page renders with JavaScript and could not be read. Starter $7 (512 MB / 0.5 CPU) and disk $0.25/GB come from several 2026 third-party write-ups, one of them a pricing table dated 15 July 2026.

Render changelog, 23 April 2026:
- Hobby workspace is free; Pro is $25/month flat; Scale is $499.
- Hobby gets less included bandwidth than before; overage is $0.15/GB.
- "No changes to Render's existing compute pricing."
- Legacy workspaces migrated automatically on 1 August 2026.

Telegram bot: it needs no disk. It can run as a second Starter worker (another $7) or alongside uvicorn in the same service's start command, which costs nothing extra.

Sources: https://render.com/docs/free · https://render.com/docs/disks · https://render.com/changelog/updated-plans-for-render-workspaces · https://render.com/pricing

### F2. Railway Hobby costs $5/month and includes $5 of usage. Usage is about $10 per GB of RAM a month, $20 per vCPU a month and $0.15 per GB of volume a month; Hobby volumes are capped at 5 GB. A request may last 15 minutes while data keeps flowing, or 5 minutes with none. The client IP is in X-Real-IP. Singapore is the only Asian region.
*Confidence: high — **decision-critical***

Pricing (railway.com/pricing):
- Free plan: $1/month of usage, 0.5 GB RAM, 500 MB volume.
- Trial: $5 one-time credit, lasts 30 days.
- Hobby: $5/month including $5 of usage, up to 48 GB per service, volume up to 5 GB.
- Billed per second: RAM $0.00000386/GB-s, CPU $0.00000772/vCPU-s, volume $0.00000006/GB-s, egress $0.05/GB.

Limits (docs.railway.com specs-and-limits):
- "HTTP requests can run for up to 15 minutes if data keeps transferring."
- A request with no data transferred closes after 5 minutes.
- Uploads must finish within 5 minutes.
- Idle HTTP/1.1 keep-alive connections close after 60 s.
- X-Real-IP carries the client IP. No proxy IP range is documented.

Regions: US West, US East, EU West (Amsterdam), Southeast Asia (Singapore). None in India.

An always-on service with about 0.5 GB of RAM is roughly $5/month for memory alone, before CPU. A realistic total for app plus bot is $5–10.

Sources: https://railway.com/pricing · https://docs.railway.com/networking/public-networking/specs-and-limits.md · https://docs.railway.com/reference/regions

### F3. Oracle Cloud Always Free is unsafe for a mostly-idle 24/7 bot. Oracle stops an instance that, over 7 days, stays under 20% CPU (95th percentile) and under 20% network, plus under 20% memory on A1 shapes. On 15 June 2026 Oracle also halved the A1 allowance to 2 OCPUs / 12 GB (1,500 OCPU-hours and 9,000 GB-hours a month).
*Confidence: medium — **decision-critical***

The A1 cut is from InfoQ, 3 July 2026:
- From 4 OCPUs / 24 GB down to 2 / 12.
- Changed in the docs with no announcement.
- Free-only accounts above the limit were shut down.
- Pay-as-you-go accounts may be exempt per support replies; Oracle has published nothing on this.

The idle rule is from a search-result snippet of Oracle's 'Always Free Resources' page (docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm). I could not fetch the page itself; three URLs returned 404 or 403.

Third-party write-ups say the threshold rose from 10% (early 2023) to 15% (19 April 2023), and Oracle's own docs now say 20%. Oracle's older guidance is that converting to pay-as-you-go prevents idle reclamation.

This app idles near 0% CPU between checks, so a free-only account would see its instance stopped. Stopped means the bots and the future WhatsApp webhook go silent.

Sources: https://infoq.com/news/2026/07/oracle-cloud-free-tier-limits/ · https://docs.oracle.com/en-us/iaas/Content/FreeTier/resourceref.htm

### F4. Hetzner raised cloud prices for new orders from 15 June 2026. Singapore CPX12 went from €7.99 to €15.49 a month. In Germany and Finland, CX23 went from €3.99 to €5.49 and CAX11 from €4.49 to €5.99 (excluding VAT and IPv4).
*Confidence: high — **decision-critical***

docs.hetzner.com price-adjustment page: "took effect for new orders and cloud instance rescales starting on the 15 June 2026; 8 AM CEST." Germany/Finland CPX22: €7.99 → €19.49.

The Singapore product page lists 0.5–5 TB of included traffic depending on plan, with extra traffic at $8.49/TB. It also shows a plan called 'CPX02' (1 vCPU / 1 GB / 20 GB) with no price visible.

Payment (Hetzner payment FAQ, Nov 2025): credit cards are charged automatically. One March 2025 anecdote reports an Indian account closed after the bank blocked the automatic charge.

Result: Hetzner Singapore is no longer cheap. Germany's CX23 is still good value but about 130–150 ms from India, which does not matter for SSE.

Sources: https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/ · https://www.hetzner.com/cloud-singapore/ · https://docs.hetzner.com/accounts-panel/accounts/payment-faq

### F5. AWS Lightsail in Mumbai: $7/month gets 1 GB RAM, 2 vCPU, 40 GB SSD and a public IPv4 address. Mumbai plans include half the usual transfer, so 1 TB instead of 2. Snapshots cost $0.05/GB-month. AWS India accounts are billed in rupees and can pay by RuPay, net banking or UPI AutoPay; automatic card payment (e-mandate) covers bills up to ₹15,000.
*Confidence: high — **decision-critical***

Lightsail pricing page (© 2026):
- With public IPv4: $5 for 512 MB / 20 GB / 1 TB; $7 for 1 GB / 40 GB / 2 TB; $12 for 2 GB / 60 GB / 3 TB.
- IPv6-only plans are cheaper ($3.50 / $5 / $10), but some APIs and sites the app reaches may not support IPv6, so I would avoid them.
- Mumbai, Sydney, Jakarta and others get "half the data transfer allowances".

AWS India payment docs:
- Visa, Mastercard, Amex and RuPay; net banking; UPI; UPI AutoPay.
- "You can only use e-mandates for charges up to INR 15,000."
- Saving a card triggers a ₹2 verification charge, refunded.

Free trial: the sources conflict. The Lightsail billing FAQ (about August 2026) says the short-term trials were replaced by AWS Free Tier credits of up to $200. A campaign page still advertises 3 months free. Treat any free period as unconfirmed.

Sources: https://aws.amazon.com/lightsail/pricing/ · https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/edit-aispl-payment-method.html · https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-frequently-asked-questions-faq-billing-and-account-management.html

### F6. DigitalOcean Basic droplets cost $4/month for 512 MiB (10 GiB SSD, 500 GiB transfer) and $6/month for 1 GiB (25 GiB SSD, 1,000 GiB transfer). Backups cost 20% of the droplet price weekly or 30% daily; snapshots $0.06/GB-month. Billing is in USD only, with 18% GST added for Indian customers.
*Confidence: high — **decision-critical***

digitalocean.com/pricing/droplets gives the plan prices, backup percentages and snapshot rate.

docs.digitalocean.com India tax page:
- 18% GST since 1 July 2017, unless a GSTIN is added.
- USD is the only currency accepted.
- Debit and credit cards are accepted, charged on the 1st of each month.
- Per-second billing from 1 January 2026.

Bangalore (BLR1) exists. A single worldwide price was promised at its launch; I found no current page confirming BLR1 prices.

For app + bot + ffmpeg, the realistic choice is the $6 1 GiB droplet with $1.20 weekly backups: $7.20 + GST, about ₹750.

Sources: https://www.digitalocean.com/pricing/droplets · https://docs.digitalocean.com/platform/billing/taxes/ind/ · https://www.digitalocean.com/blog/introducing-our-bangalore-region-blr1

### F7. Koyeb volumes don't suit a SQLite database that must not be lost. Volumes are in public preview, "currently only suitable for testing", 1–10 GB, available only in Washington and Frankfurt, and only on standard instances (not eco or free). The free instance sleeps after 1 hour with no traffic.
*Confidence: high*

Koyeb docs:
- Free instance: 512 MB, 0.1 vCPU, one per organisation, Frankfurt or Washington only, scales to zero after 1 hour idle, no volumes, no workers.
- Eco instances (also in Singapore): eco-micro 512 MB $2.68; eco-small 1 GB $5.36.
- Standard instances: micro 512 MB $5.36; small 1 GB $10.71.
- Volumes: one service, scale of one, "bound to a single machine with no built-in redundancy".
- Signing up with a card places a $29 pre-authorization hold.
- The pricing page lists Pro at $29/month and Scale at $299, and says Koyeb is joining Mistral AI.

Sources: https://www.koyeb.com/docs/reference/instances · https://www.koyeb.com/docs/reference/volumes · https://www.koyeb.com/docs/faqs/pricing · https://www.koyeb.com/pricing

### F8. Fly.io has no free allowance for new organisations. Prices: shared-cpu-1x with 512 MB is $3.69/month and 1 GB is $6.70 in the cheapest (US) regions; Singapore carries a 1.269 markup (1 GB about $8.50). Volumes cost $0.15/GB-month and dedicated IPv4 $2/month. Traffic out to India costs $0.12/GB. Mumbai is not a listed region.
*Confidence: high*

docs.fly.io/about/pricing:
- "New organizations don't have a free tier or a monthly free usage allowance."
- Trial: 2 machine-hours or 7 days, whichever ends first.
- Volume snapshots billed from 1 January 2026 at $0.08/GB, first 10 GB free.
- A card is required.

Fly.io proxy:
- Sets Fly-Client-IP (from the request-headers doc).
- Staff on the forum describe a fixed 60 s idle timeout. A forum post about 9 days old (around 6 October 2026) reports about 30 s on some hops, and says `idle_timeout` had no effect.
- The app's 15 s SSE heartbeat stays under both.

Cards: a 2021 forum thread says Indian card charges can fail on tokenised post-paid billing, and a later thread reports a Stripe decline.

Sources: https://docs.fly.io/about/pricing · https://fly.io/docs/networking/request-headers/ · https://community.fly.io/t/fly-proxy-resets-a-stalled-http-stream-after-30s-on-edge-and-flycast-hops-http-options-idle-timeout-has-no-effect/28755 · https://community.fly.io/t/billing-to-customers-in-india-may-fail/2792

### F9. Azure Central India Linux, pay-as-you-go: B2ats v2 (2 vCPU, 1 GiB) is $0.00615/hour, about $4.49/month; B1s is $0.0112/hour, about $8.18/month, effective 1 October 2025. Disk and public IP are charged on top. The free account's 12-month, 750-hour VM offer is often blocked by zero quota on trial subscriptions.
*Confidence: medium*

Figures are from the Azure Retail Prices API, filtered to centralindia.

The free account gives 750 hours each of B1s, B2pts v2 and B2ats v2 for 12 months. Microsoft Q&A threads from 2026 report:
- trial subscriptions with zero VM quota in many regions;
- B1s in limited supply, with the B-series v1 retiring on 15 November 2028.

A managed disk and a standard public IP (about $3.65/month at $0.005/hour, not verified for Azure specifically) bring a realistic paid total to about $8–10/month.

Sources: https://prices.azure.com/api/retail/prices?$filter=armRegionName eq 'centralindia' and serviceName eq 'Virtual Machines' · https://azure.microsoft.com/en-us/pricing/purchase-options/azure-account/ · https://learn.microsoft.com/en-us/answers/questions/5697409/no-free-tier-vm-available-in-any-azure-region

### F10. Google Cloud's always-free e2-micro is only free in us-west1, us-central1 or us-east1, with 30 GB-months of standard disk and 1 GB a month of free egress from North America. External IPv4 addresses on VMs are billed at $0.005/hour (about $3.65/month), and the free-tier page does not say they are covered.
*Confidence: medium*

The free-tier page was last updated 2026-10-13 UTC. The $300 trial lasts 90 days.

The external-IP price rose from $0.004 to $0.005/hour on 1 February 2024 (VPC pricing announcement).

For India: the VM sits in the US, about 200–250 ms away. That is fine for this app, but every answer streamed beyond 1 GB a month is billed egress. In practice it is about $3.65/month rather than free.

Sources: https://docs.cloud.google.com/free/docs/free-cloud-features · https://cloud.google.com/vpc/pricing-announce-external-ips · https://cloud.google.com/vpc/network-pricing

### F11. On Render, X-Forwarded-For can be forged: Render's proxy appends to whatever the client sent instead of replacing it. Render's own guidance is to key on CF-Connecting-IP, which Cloudflare overwrites on every request. None of Render, Railway or Fly documents a stable proxy IP range.
*Confidence: medium*

Render's own articles (PocketBase guide, DDoS article) and a community thread say traffic passes through Cloudflare and then Render's load balancer.

So with FORWARDED_ALLOW_IPS='*', uvicorn takes a client-chosen leftmost address. The app should instead read the one platform-overwritten header:
- CF-Connecting-IP on Render;
- X-Real-IP on Railway;
- Fly-Client-IP on Fly.io.

On a plain VM with no proxy in front (Lightsail, DigitalOcean, Azure, Hetzner, Oracle), the socket's peer address is the real client and nothing changes. If Cloudflare Tunnel is used for HTTPS, the same issue returns and CF-Connecting-IP must be read.

Sources: https://render.com/articles/host-pocketbase-on-render · https://render.com/articles/how-render-handles-ddos-attacks · https://docs.railway.com/networking/public-networking/specs-and-limits.md · https://fly.io/docs/networking/request-headers/

### F12. Railway and Fly.io have both had Indian cards decline on automatic charges, and Railway moved one such account straight to its trial plan.
*Confidence: medium*

Railway forum ('Issue with billing with Indian Cards and Services Stopping'):
- A user's automatic charges on an Indian Visa debit card failed.
- They were "immediately moved to the trial plan with no grace period".
- Paying manually with an OTP worked.

RBI e-mandate rules (since 1 October 2021) require a registered mandate and extra authentication above ₹15,000; Adobe's help page, updated February 2026, repeats this.

Providers paid upfront (Hostinger) or with domestic Indian payment rails (AWS India) avoid the problem. I found nothing India-specific for Render.

Sources: https://station.railway.com/questions/issue-with-billing-with-indian-cards-and-ca3b9ba4 · https://community.fly.io/t/billing-to-customers-in-india-may-fail/2792 · https://helpx.adobe.com/in/account/individual/subscriptions-and-plans/renewals-and-cancellations/payment-declined-reserve-bank-of-indias-mandate.html

### F13. Hostinger KVM 1 is ₹599/month introductory and renews at ₹999/month; KVM 2 is ₹799, renewing at ₹1,199. KVM 1 has 1 vCPU, 4 GB RAM, 50 GB NVMe and 4 TB bandwidth. Plans are paid upfront and include free weekly backups. E2E Networks' cheapest listed VM is about $32/month.
*Confidence: medium*

Hostinger (official India VPS page):
- "All plans are paid upfront." Renewal is for 2 years. Third-party sites say the intro price needs a 24-month term.
- The page says "10 data centers across 4 continents" and names no Indian location; a Mumbai/India location is only claimed by third parties.
- GST is not shown.

E2E Networks pricing page: the cheapest listed plan is E1LC-2.6GB at $32.32/month. A competitor's blog claims E2E changed prices on 1 July 2026; I could not verify that. Either way, E2E is overkill for 512 MB–1 GB.

Sources: https://www.hostinger.com/in/vps-hosting · https://www.e2enetworks.com/pricing

## Options

| Option | Monthly cost | Fits | For | Against |
|---|---|---|---|---|
| AWS Lightsail – Mumbai (ap-south-1), $7 plan | $7 (about ₹620) + 18% GST, about ₹730. The $5 plan (512 MB) is too tight for app + bot + ffmpeg. | Yes; strong fit. 1 GB RAM, 2 vCPU, 40 GB SSD and 1 TB transfer (Mumbai gets half), in the region nearest the users. Plain VM run with systemd, with the app and the Telegram bot as two units on the same box at no extra cost. Never sleeps. | Billed in rupees by AWS India: RuPay, net banking, UPI AutoPay, and automatic card payment up to ₹15,000 a bill. Lowest Indian-payment risk of any option.; No proxy in front, so the per-IP limiter sees real client IPs and FORWARDED_ALLOW_IPS can stay unset.; No request or SSE timeout of any kind.; Snapshots $0.05/GB-month; manual or automatic daily snapshots.; Fixed bundle price makes the bill predictable; the static IP is free while attached.; HTTPS: point a domain at the static IP and run Caddy or certbot (Let's Encrypt). This gives the stable public HTTPS URL a WhatsApp webhook needs. | The owner patches the OS (Ubuntu unattended-upgrades helps) and sets up systemd, Caddy and ffmpeg via apt over SSH from Windows.; Needs a domain for a trusted TLS certificate (about ₹100–900 a year); sslip.io or a free subdomain service can work.; Datacenter IP, which hurts yt-dlp (already established).; Free-trial status for new accounts is unclear: either credits of up to $200, or no free months. |
| DigitalOcean – Bangalore (BLR1), Basic 1 GiB droplet | $6 + $1.20 weekly backups = $7.20, + 18% GST ≈ $8.50 (about ₹750). The 512 MiB plan is $4. | Yes; strong fit. 1 GiB, 1 vCPU, 25 GiB SSD and 1,000 GiB transfer, in Bangalore. Plain VM with systemd running both processes. Never sleeps. | Located in India.; Simple, well-documented VM; per-second billing since 1 January 2026.; Weekly (20%) or daily (30%) backups; snapshots $0.06/GB-month; block volumes available.; Real client IPs with no proxy, and no timeouts on SSE or long checks.; Accepts debit and credit cards plus PayPal and Google Pay. | Billed in USD only, with card FX fees and 18% GST.; The owner patches the OS.; HTTPS needs a domain plus Caddy or certbot.; Datacenter IP for yt-dlp.; No current page confirms BLR1 prices; the single worldwide price was promised at its launch. |
| Railway – Hobby plan, Singapore | $5 fee including $5 of usage. Realistic total $5–10 (RAM about $10/GB-month, CPU by actual use, volume $0.15/GB-month, egress $0.05/GB). About ₹450–900 + GST. | Yes, with caveats. Runs as a managed PaaS that never sleeps. A volume of up to 5 GB holds the SQLite file; the Telegram bot is a second service in the same project and costs only its own RAM and CPU. | No OS patching. Deploy from GitHub with git push; the builder can add apt packages such as ffmpeg, or use a Dockerfile, built remotely with no local Docker.; Platform subdomain with HTTPS, plus free custom-domain TLS. Gives the WhatsApp webhook a stable URL.; SSE fits: the request cap is 15 minutes while data flows, 5 minutes with none, and the app's heartbeat is every 15 s. Background work is unaffected.; Client IP arrives in X-Real-IP. | Indian cards have failed automatic charges, and one account was moved straight to the trial plan with no grace period.; Proxy IP range is undocumented, so the limiter must read X-Real-IP explicitly rather than trusting FORWARDED_ALLOW_IPS='*'.; Nearest region is Singapore, not India.; Usage-based bill is less predictable; volume backups were not verified in this research.; Datacenter IP for yt-dlp. |
| Render – Hobby workspace (free) + Starter web service, Singapore | $7 Starter (512 MB / 0.5 CPU) + $0.25 for a 1 GB disk = $7.25 (about ₹640 + GST). Running the bot as a separate worker adds another $7, or it can share the web service's start command for free. | Yes on paid only. Free is fatal: it sleeps after 15 minutes idle and has no disk. 512 MB is tight with ffmpeg plus the bot; the next instance size up is the Standard tier. | Managed PaaS: git push, native Python runtime or a remotely built Dockerfile (the Dockerfile route installs ffmpeg).; Daily disk snapshots, kept at least 7 days.; onrender.com subdomain with HTTPS plus free custom-domain TLS; suits the WhatsApp webhook.; Long HTTP requests allowed (Render articles say 100 minutes; I could not confirm this in the docs). | A disk turns off zero-downtime deploys (a few seconds down per deploy) and limits the service to one instance. A worker cannot read the disk.; Behind Cloudflare: X-Forwarded-For can be forged (the proxy appends rather than replaces), so the limiter must key on CF-Connecting-IP. No stable proxy range is documented.; The 23 April 2026 plan change cut Hobby's included bandwidth; overage is $0.15/GB.; Pricing page renders with JavaScript; instance prices came from 2026 third-party write-ups.; Datacenter IP for yt-dlp. |
| Fly.io – shared-cpu-1x, Singapore (sin) | 512 MB about $4.69 or 1 GB about $8.50 in Singapore (1.269 markup on US prices of $3.69 / $6.70). Volume $0.15/GB-month. Dedicated IPv4 $2 (optional). Egress to India $0.12/GB. A second machine for the bot is about $2.8–4.7, or both can run on one machine. | Yes, as a pay-as-you-go micro-VM. Set auto-stop off and keep one machine running so it never sleeps. | `fly deploy` builds the Dockerfile on Fly's remote builders, so no local Docker is needed.; Volumes with snapshots (first 10 GB free, then $0.08/GB).; fly.dev subdomain with HTTPS plus custom-domain certificates.; Fly-Client-IP header carries the client IP. | No free allowance for new organisations; only a 2-hour or 7-day trial.; Proxy idle timeout about 60 s (one ~October 2026 report says ~30 s); the 15 s heartbeat covers it.; Indian-card failures reported historically (2021–23 threads).; No Mumbai region in the pricing list, and Indian egress is the most expensive rate.; More operational knobs (fly.toml, machines) than Render or Railway. |
| Azure – Central India, B2ats v2 VM (pay-as-you-go) | Compute $4.49 (B2ats v2, 2 vCPU / 1 GiB, Linux) + managed disk + public IP (about $3.65) ≈ $8–10. B1s is $8.18 for compute alone. The free account covers 750 hours of B2ats v2 for 12 months, if the subscription gets quota. | Yes, as a plain VM in India. | Located in Central India (Pune).; Cheapest per-vCPU compute here.; No proxy in front, so real client IPs reach the app.; Possibly free for the first year. | Many free-trial subscriptions get zero VM quota (2026 Q&A reports).; Pricing has many separately billed parts (disk, IP, bandwidth), so it is harder to predict.; The owner patches the OS and sets up HTTPS.; Datacenter IP for yt-dlp. |
| Hetzner Cloud – CX23 (Germany/Finland) or Singapore | CX23 €5.49 (EU) + IPv4. Singapore CPX12 €15.49 (prices from 15 June 2026). Backups are a percentage add-on (not verified). | Yes in the EU, as a plain VM; Singapore is now poor value. | Lots of RAM for the price in the EU.; Simple VM with snapshots and backups.; No proxy, so real client IPs reach the app. | 15 June 2026 price rise: Singapore nearly doubled.; EU is about 130–150 ms from Indian users (fine for SSE).; Cards are charged automatically, and one 2025 anecdote reports an Indian account closed after a failed automatic charge.; The owner patches the OS.; Datacenter IP for yt-dlp. |
| Oracle Cloud Always Free – Mumbai/Hyderabad (A1 or AMD micro) | $0 (Always Free); converting to pay-as-you-go still bills $0 if usage stays within the free limits. | Not reliably on a free-only account: the idle rule would stop this mostly-idle app. Acceptable only after upgrading to pay-as-you-go. | A1 up to 2 OCPU / 12 GB (since 15 June 2026); 200 GB block storage and 10 TB egress were free historically (not re-verified).; India regions.; Plain VM, so real client IPs reach the app. | Idle reclamation: under 20% CPU (95th percentile), network and memory for 7 days means the instance is stopped.; Allowance cut on 15 June 2026 with no announcement.; A1 capacity in Indian regions often unavailable (anecdotal; not verified).; Locked to the home region.; Card verification for Indian cards not verified. |
| Google Cloud – e2-micro free tier (US regions only) | Compute free (one e2-micro in us-west1, us-central1 or us-east1, plus 30 GB standard disk). External IPv4 about $3.65/month. Egress beyond 1 GB/month billed. | Marginal. 1 GB RAM with shared (burst) CPU. Only US regions, about 200–250 ms from India. | Free compute that does not expire.; $300 credit for 90 days.; Plain VM, so real client IPs reach the app. | Not in India.; IPv4 address and egress costs make it about $4/month in practice.; Shared-core CPU may be slow for ffmpeg.; The owner patches the OS. |
| Koyeb – Starter (pay-as-you-go) | eco-micro 512 MB $2.68 / eco-small 1 GB $5.36 (Singapore available, but no volumes). Standard micro $5.36 / small $10.71 with a preview volume in Frankfurt or Washington only. $29 card pre-authorization hold at signup. | No. Volumes are a preview "only suitable for testing", unavailable in Singapore and on eco instances. The free instance sleeps after 1 hour. | Managed PaaS with remote builds and HTTPS subdomains. | No production-grade persistent disk, which rules it out for the spend ledger.; Free instance scales to zero after 1 hour idle.; Company joining Mistral AI, so its direction is uncertain. |
| Hostinger VPS – KVM 1 (Indian provider page) | ₹599/month introductory (paid upfront, 24-month term per third parties), ₹999/month on renewal; GST not shown. About $7, then $11. | Yes on resources (1 vCPU, 4 GB RAM, 50 GB NVMe, 4 TB bandwidth); a plain VM. | Paid upfront in rupees, so no recurring-charge e-mandate problems.; 4 GB RAM is plenty.; Free weekly backups.; Real client IPs reach the app. | Commits about ₹14,000 upfront for 2 years.; The official page does not confirm an India data centre.; Renewal price is 67% higher than the introductory price.; The owner patches the OS; datacenter IP. |
| E2E Networks (Indian cloud) | Cheapest listed VM: E1LC-2.6GB at $32.32/month (2 vCPU, 6 GB). | Over-sized and about 5× the cost of the alternatives. | Indian company with Indian data centres and rupee billing (not verified on the pricing page). | No 512 MB–1 GB plan listed.; A competitor claims a price update on 1 July 2026 (not verified). |

## Recommendation (the researcher's)

**First choice: a $7 AWS Lightsail plan in Mumbai** (1 GB RAM, 2 vCPU, 40 GB SSD, about ₹730 a month with GST).
- **Why:** it is the only option that is in India, never sleeps, has no request or SSE timeouts, and runs the app and the Telegram bot as two systemd services on one box for one flat price. SQLite sits on the local SSD, with Lightsail snapshots at $0.05/GB.
- **Payment:** AWS India bills in rupees and supports RuPay, net banking and UPI AutoPay. That avoids the Indian-card declines seen on Railway and Fly.io.
- **Rate limiter:** no proxy sits in front, so the per-IP limiter sees real client addresses and FORWARDED_ALLOW_IPS can stay unset.
- **HTTPS and WhatsApp:** a domain pointed at the free static IP, with Caddy, gives the stable trusted-certificate URL the WhatsApp webhook needs.
- **Backup copy:** add a nightly offsite copy of the spend ledger, for example a `sqlite3 .backup` to another location.

**Close second: DigitalOcean in Bangalore** ($6 + $1.20 weekly backups, about ₹750 with GST). It is equivalent, but bills in USD to the card.

**If the owner refuses to patch a server:** use Railway Hobby in Singapore (about $5–10 a month).
- Use a volume for SQLite and a second service for the bot.
- Change the limiter to read X-Real-IP rather than setting FORWARDED_ALLOW_IPS='*'.
- Accept the risk of Indian-card decline.

Render Starter ($7.25 + disk) is the alternative PaaS. It has a few seconds of downtime per deploy when a disk is attached, and the limiter must use CF-Connecting-IP.

**Avoid:**
- Every free tier: Render free, Koyeb free, Railway Free, Fly trial, and Oracle Always Free without a pay-as-you-go upgrade (its idle rule stops the app).
- Koyeb volumes: a preview Koyeb itself calls test-only.
- Hetzner Singapore: about €15.49 since 15 June 2026.
- E2E Networks: about $32 or more.

**Not decided here:** every option has a datacenter IP, so the yt-dlp restriction already established applies equally everywhere.

## Unknowns

- Render's current instance and disk prices: the official pricing page renders with JavaScript and could not be read, so Starter $7 and disk $0.25/GB come from 2026 third-party tables. The 100-minute request limit comes from Render articles, not docs.
- How much bandwidth Render's Hobby workspace includes since the 23 April 2026 plan change. A third party calls it a '20x bandwidth cut'; the amount was not found.
- Oracle's idle-reclamation wording comes from a search snippet of docs.oracle.com, because the page itself returned 404/403. Also unverified: whether pay-as-you-go accounts keep 4 OCPU / 24 GB, A1 capacity in Mumbai and Hyderabad, and Indian-card verification at signup.
- Whether Railway volumes have built-in backups, and whether Railway's proxy strips a client-supplied X-Real-IP (I assumed it overwrites it).
- Whether new Lightsail accounts currently get a free trial: the Lightsail FAQ (about August 2026) says it was replaced by up to $200 in AWS credits, while a campaign page still shows 3 months free.
- Hetzner Singapore's 'CPX02' (1 GB) price, Hetzner's IPv4 and backup prices, and whether Hetzner's signup ID checks block Indian individuals.
- Whether Google Cloud's free tier covers the e2-micro's external IPv4 (the free-tier page is silent; VPC pricing is $0.005/hour). Also how Google Cloud India bills individuals.
- Azure: the managed-disk price and whether new free accounts actually get quota in Central India.
- Hostinger: whether KVM 1 can be placed in Mumbai, whether GST is added, and the exact upfront term.
- INR conversions assume about ₹88 per USD (not checked against a live October 2026 rate). An 18% GST applies to foreign cloud services billed to Indian individuals.
- Not re-verified this session: that Meta's WhatsApp Cloud API webhook needs a publicly trusted TLS certificate (not self-signed) on a stable HTTPS URL. A platform subdomain, or Caddy with Let's Encrypt on a VM, satisfies this.

