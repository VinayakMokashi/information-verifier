# Taking it public — the decision brief (2026-10-15)

For Vinayak, to decide before anything is built (PROJECT_PLAN §11 A–C).
Built from the research files in this folder; figures from the four topics
whose verifiers were still running when this was written (hosting, tunnel,
budget, policy) are marked † and will be corrected here if a verifier
overturns one.

---

## 1. Where it runs 24/7

| | **Your PC + Cloudflare named tunnel** | **Cloud VM: AWS Lightsail, Mumbai** |
|---|---|---|
| Cost a month | ~₹75 for a .com (+ electricity ₹40–350)† | ~₹730 ($7 + 18% GST), billed in rupees — UPI, RuPay† |
| Up when | only while the PC is on — Windows Update restarts unattended PCs, power cuts, laptops rarely power back on by themselves | always |
| Reel / Shorts links | **work** — a home IP, measured working since July | **break**: YouTube blocks datacenter IPs at the very first request; Instagram and Facebook fail intermittently. Fix: link traffic through your PC ($0, needs it on) or a residential proxy (~$5 one-off, lasts months, needs its own byte budget) |
| WhatsApp webhook | works while the PC is on | always |
| Setup | cloudflared as a Windows service + Task Scheduler auto-start | a VM to patch (unattended upgrades), systemd, cloudflared |

Everything else researched is worse for this app: every free tier sleeps,
lacks a disk, or reclaims idle machines (Render, Koyeb, Fly, Oracle, Google,
Railway free); Hetzner Singapore doubled in June 2026; Railway and Fly have
declined Indian cards. A PaaS also hides the visitor's IP behind its proxy.

**Recommendation: start on your PC behind a Cloudflare named tunnel; move to
the Mumbai VM when uptime starts to matter.** Run cloudflared on the VM too,
and the move is a copy of the setup — the same client-IP handling,
Turnstile and rules — not a rewrite. The `trycloudflare` link used today for
demos cannot carry a public site: Cloudflare's quick tunnels do not support
live streaming (the page only works because it falls back to polling) and
change URL on every restart.

## 2. Budget and limits for strangers

Measured cost per check: $0 repeats and "hi" · $0.0084 when Google's
fact-check database covers it · $0.05–0.06 covered by a fact-checker ·
$0.15–0.17 open web · $0.08–0.26 a reel. At a plausible mix the average is
**~$0.066**:

| Daily ceiling | Most a month | Checks a day (typical / a day of fresh rumours) |
|---|---|---|
| $0.50 | ~₹1,300 | ~7 / ~4 |
| **$1** | **~₹2,600** | **~15 / ~8** |
| $2 | ~₹5,300 | ~30 / ~17 |
| $5 | ~₹13,000 | ~75 / ~43 |

The ceiling bounds a bad day; a quiet day costs what it uses.

The scheme (each layer stops a different failure; every number adjustable):
- **Outside the app (you, in the consoles, free):** a separate Anthropic
  workspace for the public key with a monthly spend limit (~30× the daily
  ceiling), prepaid credits with auto-reload OFF; a small prepaid Sarvam
  balance; Sarvam data retention set to 0 days (it keeps audio until told).
- **A dollar budget in the app,** replacing the 5-checks count: each check
  reserves its worst case and settles at what it really cost. As the day
  runs low it gets cheaper instead of stopping — skip the open-web pass, then
  only the free/cached paths; at zero, "back at midnight", repeats still free.
- **Per person:** web 3 a day per device (a signed cookie, issued only after
  Cloudflare Turnstile — free, usually invisible); Telegram 5 a day per user;
  WhatsApp 5 a day per number; at most one check in flight per person; nobody
  more than a quarter of the day.
- **Network brakes, loose:** per IPv6 /64 (Jio and Airtel are 90%+ IPv6, so
  that is per phone) and per IPv4 (shared by many under carrier NAT).
- Not SMS OTP: one OTP costs about as much as a check.
- Translating Hindi forwards for the Google lookup (measured: 3/12 → 7/12
  matches) makes each rupee go ~35–45% further.

## 3. Must be fixed before ANY public URL

**Done today:** no API key in any printed `Settings` (§11 17); the Telegram
token no longer reaches a log line; Facebook reel/share links now resolve in
the app (they never did — the probe hid it); an over-20 MB Telegram file gets
the real reason.

**Blockers — reproduced by independent verifiers, all free to fix:**
1. One stranger can spend the whole day's cap in five messages and lock out
   the page and the bot until midnight (the per-IP limit, 10/h, is above the
   cap, 5/day). → the budget and per-person limits of §2.
2. One 25 MB text post freezes the whole server for 10–19 s and ~2 GB of RAM,
   before any limit — and it is refunded, so it is free to repeat.
3. The Telegram bot answers anyone, **today**, with no public URL needed
   (§11 18).
4. Any website can make its visitors' browsers submit paid image and voice
   checks to the app (cross-site form posts are not blocked). Reproduced in
   real Chrome.
5. Five concurrent long-video links hold all the day's slots while they
   resolve, then are refunded: a free, repeatable lockout that leaves no
   trace.

**Should-fix before inviting people** (audit-ops.md, audit-security.md): a
check killed by a restart vanishes from the ledger and is paid twice; a
second copy of the app fails the first one's checks; the bot forgets
in-flight checks on restart; five reel downloads stall everyone's answers on a
1-CPU machine; junk images burn slots at $0 with no record; once the cap is
reached even free cached answers are refused; no wall-clock bound on a check;
`/health` cannot tell a broken or demo server; no monitoring at all; logs are
block-buffered on a host; unpinned dependencies (a fresh install pulls an
untested major version); no yt-dlp update path; nothing restarts the app,
bot or tunnel after a reboot; a privacy notice, terms, an "AI can be wrong"
line and an 18+ line are missing (§5).

## 4. WhatsApp — what to know now

**The big risk first.** Meta's WhatsApp Business terms §4.7 (last modified
23 Sep 2026) bar providers of LLMs and AI assistants where AI is the
*primary* function — Meta decides what counts — and India is not among the
markets where AI providers are let in (Brazil is the only one listed).† A
fact-check tipline is arguably a specific service rather than an AI
assistant, but Meta can refuse it. Do not pay for or build WhatsApp until
that is settled. The full requirements, the pricing change of 1 Oct 2026
(service replies are now charged), verification documents and a "start
today" list are in `whatsapp.md` (research still running).

## 5. Policy, and the cheap "app"

- **Before launch (free):** a Privacy Notice (who runs it and a contact; what
  is collected; that messages go to Anthropic, Google, Sarvam and the video
  platforms; 30-day deletion; how to ask for deletion) and Terms (AI answers
  can be wrong, not advice, 18+, best-effort, Indian law). India's DPDP duties
  start 13 May 2027†; one of them (keep processing logs a year) conflicts
  with the 30-day deletion and needs a decision before then.
- **The "app" costs $0:** a manifest and icons make the page installable on
  Android and iOS — no service worker needed — and a share target lets a reel
  shared from Instagram or YouTube land in the box. It needs the stable domain
  of §1. The Play Store ($25, 12 testers for 14 days) can wait.

## 6. What happens after you decide

Built in this order, each step committed with tests, nothing paid without
asking: (1) the five blockers; (2) budget, per-person limits and Turnstile;
(3) the bot policy; (4) restarts, the ledger and monitoring; (5) running it
24/7 where you chose; (6) privacy, terms, the app manifest; then WhatsApp.
