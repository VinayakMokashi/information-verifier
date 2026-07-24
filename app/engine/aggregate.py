"""Overall rating + summary from per-claim verdicts.

Deterministic on purpose — the overall rating is a mechanical roll-up of
the individual verdicts, not a fresh LLM judgment. A single FALSE claim
in a message makes the whole message misleading.

Phase 2 TODO: back-translate the summary into the user's input_language
(Haiku). Phase 1 keeps the report in English.
"""
from app.models.report import ClaimVerdict
from app.models.verdict import Rating

# Worst-first precedence for the roll-up.
_PRECEDENCE = [Rating.FALSE, Rating.MISLEADING, Rating.UNVERIFIED, Rating.MOSTLY_TRUE, Rating.TRUE]


def overall_rating(verdicts: list[ClaimVerdict]) -> Rating | None:
    if not verdicts:
        return None
    present = {cv.verdict.rating for cv in verdicts}
    for rating in _PRECEDENCE:
        if rating in present:
            return rating
    return Rating.UNVERIFIED


def build_summary(verdicts: list[ClaimVerdict], overall: Rating | None) -> str:
    if not verdicts:
        return "No checkworthy factual claims were found in the submission."
    n = len(verdicts)
    false_like = sum(cv.verdict.rating in (Rating.FALSE, Rating.MISLEADING) for cv in verdicts)
    unverified = sum(cv.verdict.rating is Rating.UNVERIFIED for cv in verdicts)
    parts = [f"{n} claim(s) checked. Overall rating: {overall.value if overall else 'N/A'}."]
    if false_like:
        parts.append(f"{false_like} found false or misleading.")
    if unverified:
        parts.append(f"{unverified} could not be verified against trusted sources.")
    return " ".join(parts)
