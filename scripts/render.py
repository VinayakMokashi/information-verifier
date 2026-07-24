"""Pretty-print a TruthReport to the console (ASCII-only, Windows-safe)."""
from app.models.report import TruthReport

_BAR = 28


def _confbar(c: int) -> str:
    filled = round(_BAR * c / 100)
    return "[" + "#" * filled + "-" * (_BAR - filled) + f"] {c}%"


def render_report(report: TruthReport) -> str:
    L: list[str] = []
    L.append("=" * 66)
    L.append(f"TRUTH REPORT   job={report.job_id[:12]}   status={report.status.value}")
    if report.input_language:
        L.append(f"Detected language : {report.input_language}")
    if report.overall_rating:
        L.append(f"OVERALL RATING    : {report.overall_rating.value}")
    if report.summary:
        L.append(f"Summary           : {report.summary}")
    if report.error:
        L.append(f"ERROR             : {report.error}")
    L.append("=" * 66)

    for i, cv in enumerate(report.claim_verdicts, 1):
        v = cv.verdict
        tag = "  (served from cache)" if cv.cache_hit else ""
        L.append("")
        L.append(f"CLAIM {i}{tag}")
        L.append(f"  {cv.claim.text}")
        L.append(f"  Rating     : {v.rating.value}")
        L.append(f"  Confidence : {_confbar(v.confidence)}")
        L.append(f"  Why        : {v.reasoning}")
        if v.correction:
            L.append(f"  Correction : {v.correction}")
        if v.citations:
            L.append("  Sources    :")
            for c in v.citations:
                L.append(f"    - {c.publisher}: {c.title}")
                L.append(f"      {c.url}")
    L.append("")
    return "\n".join(L)
