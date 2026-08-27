"""What the reader actually sees: the console report and the web page.

Free. The page's JavaScript can't be executed here (no Node), so it is
checked as text — but the checks are the load-bearing ones: that localized
strings go through the escaper, and that the page indexes the translation by
claim position instead of zipping two lists together.
"""
import io
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.models.claim import Claim
from app.models.report import (
    ClaimVerdict, JobStatus, LocalizedClaim, LocalizedReport, TruthReport,
)
from app.models.verdict import Citation, Rating, Verdict
from scripts.render import print_report, render_report

_PAGE = (Path(__file__).resolve().parent.parent / "static" / "index.html").read_text(
    encoding="utf-8"
)

HINDI_SUMMARY = "2 दावों की जाँच की गई। कुल नतीजा: FALSE।"
HINDI_CLAIM = "5जी से कोरोना वायरस फैलता है।"


def _report(with_hole=False) -> TruthReport:
    def cv(i):
        return ClaimVerdict(
            claim=Claim(text=f"5G spreads coronavirus ({i}).", subject="5G",
                        claim_type="causal", checkworthy=True),
            verdict=Verdict(rating=Rating.FALSE, confidence=97,
                            reasoning="Trusted sources say this is false.",
                            correction="Corona spreads by droplets.",
                            citations=[Citation(url="https://altnews.in/x",
                                                title="No link", publisher="AltNews")]),
        )

    localized = LocalizedClaim(claim=HINDI_CLAIM,
                               reasoning="भरोसेमंद स्रोतों के अनुसार यह दावा झूठा है।",
                               correction="कोरोना साँस की बूँदों से फैलता है।")
    return TruthReport(
        job_id=uuid.uuid4().hex, status=JobStatus.COMPLETE,
        created_at=datetime.now(timezone.utc),
        input_language="hi", overall_rating=Rating.FALSE,
        summary="2 claim(s) checked. Overall rating: FALSE.",
        claim_verdicts=[cv(0), cv(1)],
        localized=LocalizedReport(
            language="hi", summary=HINDI_SUMMARY,
            claims=[None, localized] if with_hole else [localized, localized],
        ),
    )


# -- console -----------------------------------------------------------------

def test_console_shows_both_languages_and_labels_which_was_checked():
    out = render_report(_report())
    assert "2 claim(s) checked" in out          # the English is still the record
    assert HINDI_SUMMARY in out
    assert HINDI_CLAIM in out
    assert "the English above is what was checked" in out


def test_console_states_an_untranslated_claim_instead_of_skipping_it():
    """Skipping it silently would make claim 2's answer look like claim 1's."""
    out = render_report(_report(with_hole=True))
    localized_block = out.split("IN THE READER'S LANGUAGE")[1]
    assert "CLAIM 1  (not translated" in localized_block
    assert "CLAIM 2" in localized_block


def test_console_numbers_by_claim_even_if_the_translation_list_is_short():
    """A truncated list must not renumber — claim 2's answer relabelled as
    claim 1's is the same harm as serving a cached verdict for another claim."""
    report = _report()
    report.localized.claims = report.localized.claims[:1]

    block = render_report(report).split("IN THE READER'S LANGUAGE")[1]
    assert "CLAIM 1" in block
    assert "CLAIM 2  (not translated" in block


def test_console_omits_the_block_entirely_for_an_english_report():
    report = _report()
    report.localized = None
    assert "IN THE READER'S LANGUAGE" not in render_report(report)


def test_console_shows_machine_read_text_back():
    """Invariant 4 on the console surface — found missing when the first real
    reel run produced a transcript nowhere in the printed report."""
    report = _report()
    report.source_text = "यू गाइज़ से कि ये वो लड़की है (transcript)"
    out = render_report(report)
    assert "WHAT THE MACHINE READ" in out
    assert "यू गाइज़ से" in out

    report.source_text = None
    assert "WHAT THE MACHINE READ" not in render_report(report)


def _cp1252_stdout():
    buf = io.BytesIO()
    return buf, io.TextIOWrapper(buf, encoding="cp1252", errors="strict")


def test_a_plain_print_to_a_windows_ansi_stdout_would_have_died():
    """The measured bug: `demo_offline.py > out.txt` on Windows gets cp1252,
    and Devanagari raises there while the same command on a console works."""
    _, stream = _cp1252_stdout()
    with pytest.raises(UnicodeEncodeError):
        stream.write(render_report(_report()))
        stream.flush()


def test_print_report_forces_utf8_so_a_hindi_report_survives_redirection(monkeypatch):
    buf, stream = _cp1252_stdout()
    monkeypatch.setattr(sys, "stdout", stream)

    print_report(_report())
    sys.stdout.flush()

    assert HINDI_SUMMARY in buf.getvalue().decode("utf-8")


@pytest.mark.parametrize("stream_factory", [
    io.StringIO,                                     # has no reconfigure at all
    lambda: type("Shim", (io.StringIO,), {"reconfigure": None})(),   # has a dud one
    lambda: type("Shim", (io.StringIO,), {
        "reconfigure": lambda self, **kw: (_ for _ in ()).throw(OSError("detached"))
    })(),
])
def test_print_report_tolerates_any_stdout_it_is_handed(monkeypatch, stream_factory):
    """sys.stdout is whatever the caller left there. Printing the report
    matters more than the encoding nicety, so every failure prints anyway."""
    stream = stream_factory()
    monkeypatch.setattr(sys, "stdout", stream)
    print_report(_report())
    assert HINDI_SUMMARY in stream.getvalue()


# -- web page ----------------------------------------------------------------

def test_every_localized_field_goes_through_the_escaper():
    """Translated text is model output about attacker-supplied text; it lands
    in innerHTML exactly like the English does, so it needs the same escape."""
    interpolations = re.findall(r"\$\{[^}]*\blc\.[^}]*\}", _PAGE)
    assert interpolations, "the page no longer reads localized claim fields"
    unescaped = [x for x in interpolations if "esc(" not in x]
    assert unescaped == [], f"unescaped localized interpolation: {unescaped}"

    summary = re.findall(r"\$\{esc\(summary\)\}", _PAGE)
    assert summary, "the summary must be escaped whichever language it is in"


def test_the_page_indexes_the_translation_by_claim_position():
    """Zipping two lists would shift every answer after a failed translation."""
    assert "loc.claims[i]" in _PAGE
    assert "forEach((cv, i)" in _PAGE


def test_the_page_falls_back_to_english_per_claim():
    assert "lc ? lc.reasoning : v.reasoning" in _PAGE
    assert "lc ? lc.claim : cv.claim.text" in _PAGE
    assert "could not be translated" in _PAGE


def test_the_english_stays_one_tap_away():
    assert "langToggle" in _PAGE
    assert "The English is what we checked." in _PAGE


def test_ratings_and_citations_are_never_taken_from_the_translation():
    """They have no localized counterpart; the page must not invent one."""
    assert "lc.rating" not in _PAGE
    assert "lc.citations" not in _PAGE
    assert "lc.confidence" not in _PAGE


def test_a_long_check_is_never_orphaned():
    """The audit found a paid report could become unreachable: the page gave
    up polling and the job id was shown nowhere. The id now lives in the URL
    hash and a reload resumes watching the same job."""
    assert 'location.hash = "job=" + jobId' in _PAGE
    assert "function jobFromHash()" in _PAGE
    assert "resumeFromHash" in _PAGE
    # The timeout message must carry the id and say a refresh resumes.
    assert "refresh karke" in _PAGE
    assert "jobId.slice(0, 12)" in _PAGE
    # And a resumed COMPLETE job must render immediately, not after a sleep.
    assert "if (i > 0) await new Promise" in _PAGE


def test_a_dead_job_link_does_not_trap_the_page():
    """A bookmarked #job= from a reset database used to show 'Connection lost
    — retrying…' for four minutes (wrong: the server ANSWERED), then invite a
    refresh that restarted the identical doomed loop."""
    assert "class GoneError" in _PAGE
    assert "resp.status === 404" in _PAGE
    assert "history.replaceState" in _PAGE          # the dead hash is cleared
    assert "ab available nahi hai" in _PAGE


def test_a_submission_while_busy_is_never_swallowed_silently():
    """The file pickers clear their input BEFORE submitting, so a silent
    early return discarded the user's pick with no feedback at all."""
    busy_guard = _PAGE.split("async function submit(makeRequest)")[1][:400]
    assert "if (busy)" in busy_guard
    assert "setStatus(" in busy_guard.split("if (busy)")[1][:300], (
        "the busy branch returns without telling the user anything")


def test_language_button_uses_the_endonym():
    """A reader who needs the Hindi version cannot read a button saying 'Hindi'."""
    assert 'hi: "हिंदी"' in _PAGE
    assert 'ta: "தமிழ்"' in _PAGE
    assert "langLabel" in _PAGE


def test_the_language_lookup_cannot_return_an_inherited_property():
    """`constructor` passes the server's tag check, and a plain object lookup
    would render Object's constructor as the button label."""
    assert "hasOwnProperty.call(LANG_NAMES" in _PAGE


def test_reader_language_text_is_direction_aware():
    """Urdu and Sindhi are right-to-left; without dir="auto" their punctuation
    lands on the wrong end inside this LTR page."""
    for anchor in ['<h3 dir="auto">', 'style="margin-top:6px" dir="auto"']:
        assert anchor in _PAGE, anchor


def test_dir_auto_is_not_defeated_by_a_hardcoded_english_label():
    """dir="auto" resolves from the first STRONG character in the element. On
    the two blocks that carry an English label first, putting it on the block
    made it inert — it must sit on a span wrapping only the reader's text."""
    for label, wrapper in [
        ('<span class="label">We read this from what you sent',
         '<span dir="auto">${esc(r.source_text)}</span>'),
        ('<strong>Sach yeh hai:</strong>',
         '<span dir="auto">${esc(lc ? lc.correction : v.correction)}</span>'),
    ]:
        assert label in _PAGE, label
        assert wrapper in _PAGE, wrapper
    # And the inert form must not come back.
    assert '<div class="heard" dir="auto">' not in _PAGE
    assert '<div class="correction" dir="auto">' not in _PAGE
