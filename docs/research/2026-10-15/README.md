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
| [cloud-hosting.md](cloud-hosting.md) | Cloud hosts for running it 24/7 | pending (verifier killed by the network drop) |
| [home-tunnel.md](home-tunnel.md) | Staying on the home PC behind a tunnel | pending (verifier killed) |
| [limits-budget.md](limits-budget.md) | Budget, per-person limits, a bot shield for strangers | pending (verifier killed) |
| [policy-legal.md](policy-legal.md) | Policy and compliance for a free public service in India | pending (verifier killed) |
| [pwa-app.md](pwa-app.md) | The cheap "app": installable PWA, Play Store route | verified |
| whatsapp.md | Starting a WhatsApp bot on Meta's Cloud API | **not yet** — both attempts killed; re-running |

Each file states its own verification status at the top, and a finding a
verifier corrected carries the verdict inline. Treat anything unverified as
unverified.

Already acted on from this research (each with its own commit and tests):
the Facebook reel/share-link bug (ca76538) and the bot-token leak (63f8049).
