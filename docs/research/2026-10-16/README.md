# Reviews of the public launch, 2026-10-16/17

Two adversarial reviews of the launch's step 5 (privacy notice, terms, the
AI line, deletion, the installable app) and of step 4's runner and
runbook. Each finding was reproduced in a scratch folder (no `.env`, dummy
keys, never the real database), then fixed with a test that failed first
(PROJECT_PLAN §7, 2026-10-16 late night and 2026-10-17).

| File | What | Status |
|---|---|---|
| [review-step5.md](review-step5.md) | The review of step 5: 18 findings (7 medium, 11 low) | complete; all 18 fixed by ae85077 |
| [review-fixes-step5.md](review-fixes-step5.md) | The re-check of those fixes, plus `serve_forever.py` and `docs/go-live.md`: 13 findings (4 medium, 9 low) | complete; all 13 fixed by 09dc74d; one example in its closing notes corrected 2026-10-17 |

The third round of fixes (1ae3cc3 … 09dc74d) was proven by failing-first
tests, mutants and 6,000 explorer seeds. No reviewer has read it yet;
HANDOFF §0 lists that as an offer.
