"""Pretty-print an Answer to the console.

The frame is ASCII (box-drawing characters are unreliable across Windows code
pages), but the CONTENT is not: an answer comes back in the sender's language,
so it is routinely Devanagari, Tamil or Bengali. Print that through a
redirected stdout on Windows and Python falls back to the ANSI code page —
measured here as cp1252, where `demo_offline.py > out.txt` dies with
UnicodeEncodeError while the same command on a console succeeds.
`print_answer()` exists to make that impossible; use it rather than
`print(render_answer(...))`.

Wrapping is deliberately width-aware but script-naive: `textwrap` counts code
points, so a Devanagari line wraps a little early. That is cosmetic. Breaking
inside a grapheme cluster would not be, which is why nothing here slices.
"""
import re
import sys
import textwrap

from app.models.answer import Answer

_W = 74
_BAR = 28

# The engine strips its own sentinel, but this renderer is also pointed at
# rows that predate a fix, and a leaked `<verdict .../>` in the console is
# how invariant 7 gets noticed too late.
_SENTINEL_RE = re.compile(r"<verdict\b[^>]*/?>", re.IGNORECASE)


def _confbar(c: int) -> str:
    filled = round(_BAR * c / 100)
    return "[" + "#" * filled + "-" * (_BAR - filled) + f"] {c}%"


def _plain(markdown: str) -> list[str]:
    """Markdown -> console lines. A strict subset, same as the web page.

    Emphasis markers are dropped rather than rendered: a terminal that does
    not do ANSI is more common than one that does, and `**this**` reads worse
    than `this`. Links are never emitted at all — invariant 3: prose is not a
    receipt, so URLs come only from `answer.sources` below.
    """
    out: list[str] = []
    for block in _SENTINEL_RE.sub("", markdown).split("\n\n"):
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        for line in lines:
            bullet = re.match(r"^(?:[-*]|\d+[.)])\s+(.*)$", line)
            body = bullet.group(1) if bullet else line
            body = re.sub(r"\*\*([^*]+)\*\*", r"\1", body)
            body = re.sub(r"(?<!\*)\*([^*\n]+)\*(?!\*)", r"\1", body)
            body = re.sub(r"`([^`]+)`", r"\1", body)
            body = re.sub(r"^#{1,6}\s*", "", body)
            prefix, indent = ("  - ", "    ") if bullet else ("", "")
            wrapped = textwrap.wrap(body, _W - len(indent)) or [""]
            out.append(prefix + wrapped[0])
            out.extend(indent + w for w in wrapped[1:])
        out.append("")
    while out and not out[-1]:
        out.pop()
    return out


_TIER_LABEL = {
    "trusted": "Fact-checkers and official sources",
    "web": "General web only - NO fact-checker has covered this",
    "none": "Nothing reliable addressed this",
}


def render_answer(answer: Answer) -> str:
    L: list[str] = []
    L.append("=" * _W)
    L.append(f"ANSWER   job={answer.job_id[:12]}   status={answer.status.value}")
    L.append("=" * _W)

    if answer.error:
        L.append("")
        L.append(f"COULD NOT CHECK: {answer.error}")
        L.append("")
        return "\n".join(L)

    if answer.input_text:
        L.append("")
        L.append("YOU SENT:")
        L.extend("  " + w for w in textwrap.wrap(answer.input_text, _W - 2)[:6])

    if answer.source_text:
        # Invariant 4 on this surface too: ASR/OCR output is a GUESS, and a
        # mis-hear means the answer below is about different words than the
        # ones actually said. The web page shows this; the console did not
        # until the first real reel run made the gap obvious.
        L.append("")
        L.append("WHAT THE MACHINE READ (if this is wrong, the answer below is")
        L.append("about the wrong words):")
        L.extend("  " + w for w in textwrap.wrap(answer.source_text, _W - 2))

    for section in answer.sections:
        if not section.markdown.strip():
            continue
        L.append("")
        if section.tier == "web":
            # The divider is not decoration. Merged into one blob, a random
            # blog reads as if it carried a fact-checker's authority.
            L.append("-" * _W)
            L.append("NO FACT-CHECKER HAS COVERED THIS - general web below")
            L.append("-" * _W)
        L.extend(_plain(section.markdown))

    L.append("")
    L.append("=" * _W)
    if answer.confidence is not None:
        L.append(f"Confidence : {_confbar(answer.confidence)}")
    else:
        L.append("Confidence : not stated")
    L.append(f"Based on   : {_TIER_LABEL[answer.tier]}")
    if answer.truncated:
        L.append("NOTE       : the answer was cut short (length limit).")
    if answer.cached:
        L.append("NOTE       : served from cache - this check cost $0.")

    if answer.sources:
        for tier, heading in (("trusted", "TRUSTED SOURCES"),
                              ("web", "GENERAL WEB (not fact-checkers)")):
            rows = [s for s in answer.sources if s.tier == tier]
            if not rows:
                continue
            L.append("")
            L.append(heading)
            for s in rows:
                L.append(f"  - {s.display_name}"
                         + (f": {s.title}" if s.title else ""))
                L.append(f"    {s.url}")
    else:
        L.append("")
        L.append("SOURCES    : none - nothing vetted addressed this.")
    L.append("")
    return "\n".join(L)


def force_utf8_stdout() -> None:
    """Make stdout able to carry Indic text. See the module docstring.

    Whatever is sitting on sys.stdout is arbitrary — a StringIO (no
    `reconfigure` at all), a pytest capture, an editor's console shim — and
    printing matters more than the encoding nicety, so every way this can go
    wrong degrades to "print it anyway". Streaming scripts must call this
    BEFORE the first chunk: the answer arrives a word at a time, and the
    first Devanagari word would otherwise kill the run mid-sentence.
    """
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if callable(reconfigure):
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass  # detached, or a stream that refuses to be re-encoded


def print_answer(answer: Answer) -> None:
    """Render and print, forcing UTF-8 on stdout first."""
    force_utf8_stdout()
    print(render_answer(answer))
