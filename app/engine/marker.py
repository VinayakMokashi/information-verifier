"""The verdict sentinel: how confidence rides out on a stream without leaking.

The model ends its answer with a machine-readable trailer:

    <verdict confidence="82" trusted="yes" used="boomlive.in who.int"/>

`used` (optional, added 2026-09-22) names the domains the answer actually
rests on. The first paid runs returned ZERO citations — web_search_20260209
filters results through code execution, and nothing comes back as a citation —
so the source list was every raw search result, Manchester City Council
included, for a claim about Nagpur Metro. `used` lets the model NARROW that
list to what it relied on. It can never extend it: a domain it names that no
search returned simply matches nothing.

A TRAILER, not a header, because a header cannot survive streaming. Claude
narrates before it searches ("Let me check the trusted fact-checkers.") — one
sentence, no newline, then a tool call. A header protocol has to decide
"preamble or answer?" at that moment and cannot: the same block is preamble if
a tool call follows and the entire paid answer if nothing does. A trailer needs
no lookahead. It also puts the number AFTER the reasoning that justifies it,
which is the calibrated ordering.

The input cannot forge it: `as_prompt_data()` rewrites every `<` and `>` in
user text to `‹`/`›` before it reaches the prompt, so a sentinel in the
response can only have come from the model.

This module is pure — no API, no I/O — so the nasty part (a sentinel split
across arbitrary delta boundaries) is exhaustively testable.
"""
import re

# Bounded hold-back: only a trailing run that could still become the sentinel
# is withheld, so streaming stays word-by-word rather than line-by-line. A
# markdown paragraph is one line, so a line-buffered filter would visibly
# stutter.
_OPEN = "<verdict"
# Comfortably longer than the longest sentinel, `used` list included. Only a
# run that begins `<verdict` is ever held this long, and a real one is always
# the last thing in the answer.
_MAX_USED_CHARS = 600
_MAX_HOLD = 700

_SENTINEL_RE = re.compile(
    r"<verdict\s+confidence=\"(?P<confidence>\d{1,3})\"\s+"
    r"trusted=\"(?P<trusted>yes|no)\""
    r"(?:\s+used=\"(?P<used>[^\"<>]{0,%d})\")?\s*/?>" % _MAX_USED_CHARS,
    re.IGNORECASE,
)
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def _could_still_become_sentinel(tail: str) -> bool:
    """Is `tail` a prefix of a sentinel that later deltas might complete?"""
    if len(tail) > _MAX_HOLD:
        return False
    # An unterminated but already-matching opener (`<verdict conf...`).
    if tail.startswith(_OPEN):
        return ">" not in tail
    # A partial opener (`<`, `<ver`, ...).
    return _OPEN.startswith(tail)


class MarkerFilter:
    """Streams text through, withholding only a possible trailing sentinel.

    Usage: `feed()` each text delta and emit whatever it returns; `flush()`
    at the end of the stream; `parse()` for the values. Any sentinel found is
    removed from the emitted text — the reader never sees it.
    """

    def __init__(self) -> None:
        self._held = ""      # trailing run that might still become a sentinel
        self._full = ""      # everything, sentinel included, for parse()

    def feed(self, delta: str) -> str:
        if not delta:
            return ""
        self._full += delta
        buf = self._held + delta
        self._held = ""

        # Emit complete sentinels' surrounding text, drop the sentinels.
        out = []
        pos = 0
        for match in _SENTINEL_RE.finditer(buf):
            out.append(buf[pos:match.start()])
            pos = match.end()
        buf = buf[pos:] if pos else buf
        emitted = "".join(out)

        # Whatever trails after the last `<` may still be a sentinel opening.
        cut = buf.rfind("<")
        if cut != -1 and _could_still_become_sentinel(buf[cut:]):
            self._held = buf[cut:]
            buf = buf[:cut]
        return emitted + buf

    def flush(self) -> str:
        """End of stream: a held run that never became a sentinel is text."""
        held, self._held = self._held, ""
        if _SENTINEL_RE.fullmatch(held.strip()):
            return ""
        return held

    def parse(self) -> tuple[int | None, bool | None]:
        """(confidence, trusted) from the LAST sentinel, or (None, None).

        Last, not first: a paused turn resumes and the model may restate it.
        A missing or malformed sentinel is not an error — it means the answer
        carries no stated confidence, and (crucially) that nothing may be
        escalated on the strength of it.
        """
        matches = list(_SENTINEL_RE.finditer(self._full))
        if not matches:
            return None, None
        last = matches[-1]
        confidence = int(last.group("confidence"))
        if not 0 <= confidence <= 100:      # a nonsense number is no number
            return None, last.group("trusted").lower() == "yes"
        # Round to 5: a model's "82%" is false precision, and displaying it
        # to the digit implies a calibration nobody has measured.
        return round(confidence / 5) * 5, last.group("trusted").lower() == "yes"

    def used(self) -> list[str] | None:
        """Domains from the LAST sentinel's `used`, or None if not given."""
        matches = list(_SENTINEL_RE.finditer(self._full))
        if not matches:
            return None
        return parse_used(matches[-1].group("used"))


def parse_used(raw: str | None) -> list[str] | None:
    """The `used` attribute -> normalized domains, or None when it is absent.

    Forgiving about what the model writes (commas, URLs, `www.`, a path) and
    strict about what comes out: plain hostnames only. None means "no list was
    given" and must leave the sources alone; [] means "relied on nothing" —
    which ONLY an empty attribute can say. Found by review: used="Alt News"
    (names, not domains) parsed to [] and stripped every source from an
    answer that had named its source. Words we cannot read are unsaid.
    """
    if raw is None or not raw.strip():
        return None if raw is None else []
    domains: list[str] = []
    for token in re.split(r"[\s,;]+", raw.strip().lower()):
        token = re.sub(r"^[a-z]+://", "", token).split("/")[0].split("?")[0]
        token = token.removeprefix("www.").strip(".")
        if token and _DOMAIN_RE.match(token) and token not in domains:
            domains.append(token)
    return domains or None


# Looser than _SENTINEL_RE on purpose: renderers strip ANYTHING that opens
# like a sentinel, malformed or not, as defence in depth for invariant 7 —
# including rows written before a fix. It used to be copy-pasted into the
# Telegram bot and the console renderer.
_ANY_SENTINEL_RE = re.compile(r"<verdict\b[^>]*/?>", re.IGNORECASE)


def strip_any_sentinel(text: str) -> str:
    """Remove every sentinel-shaped tag, well-formed or not. For renderers."""
    return _ANY_SENTINEL_RE.sub("", text)


def strip_sentinels(text: str) -> str:
    """Remove any sentinel from a finished string (non-streaming paths)."""
    return _SENTINEL_RE.sub("", text).strip()
