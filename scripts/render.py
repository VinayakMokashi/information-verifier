"""Pretty-print a TruthReport to the console.

The frame is ASCII (box-drawing characters are unreliable across Windows
code pages), but the CONTENT no longer is: a localized report is Devanagari,
Tamil or Bengali. Print that through a redirected stdout on Windows and
Python falls back to the ANSI code page — measured here as cp1252, where
`demo_offline.py > out.txt` dies with UnicodeEncodeError while the same
command on a console succeeds. `print_report()` exists to make that
impossible; use it rather than `print(render_report(...))`.
"""
import sys

from app.models.report import TruthReport

_BAR = 28


def _confbar(c: int) -> str:
    filled = round(_BAR * c / 100)
    return "[" + "#" * filled + "-" * (_BAR - filled) + f"] {c}%"


def _localized_block(report: TruthReport) -> list[str]:
    loc = report.localized
    if loc is None:
        return []
    L = ["", "=" * 66,
         f"IN THE READER'S LANGUAGE ({loc.language})"
         "  -- machine translation; the English above is what was checked",
         "=" * 66]
    if loc.summary:
        L.append(f"Summary           : {loc.summary}")
    for i, lc in enumerate(loc.claims, 1):
        L.append("")
        if lc is None:
            # An untranslated claim is stated, not skipped: a reader scanning
            # this must not think claim 2's answer belongs to claim 3.
            L.append(f"CLAIM {i}  (not translated - see the English above)")
            continue
        L.append(f"CLAIM {i}")
        L.append(f"  {lc.claim}")
        L.append(f"  Why        : {lc.reasoning}")
        if lc.correction:
            L.append(f"  Correction : {lc.correction}")
    return L


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

    L.extend(_localized_block(report))
    L.append("")
    return "\n".join(L)


def print_report(report: TruthReport) -> None:
    """Render and print, forcing UTF-8 on stdout first. See the module docstring.

    Whatever is sitting on sys.stdout is arbitrary — a StringIO (no
    `reconfigure` at all), a pytest capture, an editor's console shim — and
    printing the report matters more than the encoding nicety, so every way
    this can go wrong degrades to "print it anyway".
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass  # detached, or a stream that refuses to be re-encoded
    print(render_report(report))
