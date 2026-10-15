# Public-launch research, 2026-10-15

Vinayak asked (PROJECT_PLAN §11 A–C) for the choices behind making the app
public — where it runs 24/7, the budget and limits for strangers, what must
be fixed before any public URL — and for what a WhatsApp bot needs to start,
**before anything is built**. Research agents gathered this; independent
verifier agents then tried to refute each decision-critical finding, and the
audits' findings were reproduced with free scripts (scratch databases, dummy
keys, never the real one).

**These are research notes, not decisions.** Decisions go into PROJECT_PLAN
§7 and §11 once Vinayak makes them.

Twice an interruption killed agents mid-run and everything they had found was
lost — a usage limit (04:40 IST), then a network drop ("Can't reach the API
server … ENOTFOUND", ~21:45 IST). So every finished result is now written
here and committed the moment it exists; see CLAUDE.md, "Interruptions".

| File | What | Verification |
|---|---|---|
| [audit-security.md](audit-security.md) | Code audit — security and abuse once strangers can reach it | verified: 12 verdicts, severities corrected, 4 new findings |
| [audit-ops.md](audit-ops.md) | Code audit — operations, reliability, privacy, 24/7 for strangers | verified: 28 findings, 3 severities lowered |
| [ytdlp-cloud-ips.md](ytdlp-cloud-ips.md) | Do reel/Shorts links still resolve from a datacenter IP? | verified: all confirmed, one price corrected |
| [cloud-hosting.md](cloud-hosting.md) | Cloud hosts for running it 24/7 | verified ([cloud-hosting.verification.md](cloud-hosting.verification.md)): ranking holds; Lightsail's billing via AWS India unconfirmed; DigitalOcean $6 only on "Bundled" plans |
| [home-tunnel.md](home-tunnel.md) | Staying on the home PC behind a tunnel | verified ([home-tunnel.verification.md](home-tunnel.verification.md)): tunnel facts hold; Cloudflare Registrar may decline Indian cards (3D Secure) |
| [limits-budget.md](limits-budget.md) | Budget, per-person limits, a bot shield for strangers | verified ([limits-budget.verification.md](limits-budget.verification.md)): numbers hold; adds credit-exhaustion handling and two cache/budget code gaps |
| [policy-legal.md](policy-legal.md) | Policy and compliance for a free public service in India | verified ([policy-legal.verification.md](policy-legal.verification.md)): DPDP dates from the gazette; one-year retention duties from May 2027; Anthropic AUP high-risk categories |
| [pwa-app.md](pwa-app.md) | The cheap "app": installable PWA, Play Store route | verified |
| [whatsapp.md](whatsapp.md) | Starting a WhatsApp bot on Meta's Cloud API | **in progress** — third attempt writing as it goes; this is a checkpoint |

Each file states its own verification status at the top, and a finding a
verifier corrected carries the verdict inline. Treat anything unverified as
unverified.

Already acted on from this research (each with its own commit and tests):
the Facebook reel/share-link bug (ca76538) and the bot-token leak (63f8049).
