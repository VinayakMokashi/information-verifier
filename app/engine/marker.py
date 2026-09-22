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
_OPEN_BODY = "verdict"          # after the `<` (or `</`)
# Only a run that opens `<verdict` is ever held this long, and a real one is
# always the last thing in the answer. It used to be 700 with `used` capped at
# 600 INSIDE the regex, then 4000 — both let a long tag through to the reader
# (two review rounds). A used= of full URLs runs to thousands of characters.
# The cap now only bounds how long a stray `<verdict` in the middle of prose
# could delay the rest of the answer.
_MAX_HOLD = 16000

# Recognising the TAG is separate from reading it, because every tag must go
# whether or not it parses: invariant 7 says the sentinel is never shown, and
# a malformed one is still the sentinel. Attributes are read in ANY order (a
# tag with used= before trusted= used to match nothing and leak), a closing
# `</verdict>` counts, and a QUOTED value may contain `<` or `>` — `[^<>]*`
# could not span those, so the whole tag was shown. The alternation is
# prefix-disjoint (a quote or not), so matching stays linear.
_ATTRS = r'(?:[^<>"]|"[^"]*")*'
_TAG_RE = re.compile(r"</?verdict\b(" + _ATTRS + r")>", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r'\bconfidence\s*=\s*"(\d{1,3})"', re.IGNORECASE)
_TRUSTED_RE = re.compile(r'\btrusted\s*=\s*"(yes|no)"', re.IGNORECASE)
_USED_RE = re.compile(r'\bused\s*=\s*"([^"]*)"', re.IGNORECASE)
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
# What a model writes when it means used="" — "relied on nothing", not
# "unreadable". Nothing here can be a domain, so no real list is swallowed.
_NOTHING = frozenset({"", "none", "nothing", "nil", "n/a", "na", "null", "-",
                      "--", "no sources", "no source", "not applicable"})
_WORD_CHAR = re.compile(r"\w")


def _closes_outside_quotes(buf: str, start: int) -> bool:
    """Is there a `>` from `start` on that is not inside a quoted value?"""
    in_quote = False
    for ch in buf[start:]:
        if ch == '"':
            in_quote = not in_quote
        elif ch == ">" and not in_quote:
            return True
    return False


def _could_still_become_sentinel(buf: str, i: int = 0) -> bool:
    """Could the run at `buf[i:]` still become the sentinel?

    Case-insensitive, like the tag itself — the hold-back used to compare
    exactly while the regex ignored case, so `<Ver` + `dict …` split across
    two deltas went straight to the reader (found by review). Indices rather
    than slices: this runs per `<` in the buffer.
    """
    if len(buf) - i > _MAX_HOLD:
        return False
    j = i + 2 if buf.startswith("</", i) else i + 1     # past `<` or `</`
    body = buf[j:j + len(_OPEN_BODY)].lower()
    if body == _OPEN_BODY:
        after = buf[j + len(_OPEN_BODY):j + len(_OPEN_BODY) + 1]
        if after and _WORD_CHAR.match(after):
            return False            # "<verdicts": a word, not the tag
        # An opened tag, not yet closed. A `>` inside a quoted value does not
        # close it — that is how a used= containing `>` used to escape.
        return not _closes_outside_quotes(buf, j + len(_OPEN_BODY))
    return _OPEN_BODY.startswith(body)   # a partial opener: `<`, `</Ver`, ...


def _hold_from(buf: str) -> int:
    """The EARLIEST `<` that could still become the sentinel, or -1.

    Earliest, not last: the last `<` in an unfinished tag can be one inside
    its own quoted used= value, and holding from there would emit the first
    half of the tag. A stray `<` in prose stops being a candidate as soon as
    any non-matching character follows it, so this holds nothing extra.
    """
    i = buf.find("<")
    while i != -1:
        if _could_still_become_sentinel(buf, i):
            return i
        i = buf.find("<", i + 1)
    return -1


def _is_cut_sentinel(held: str) -> bool:
    """At the end of the stream: did the answer stop INSIDE the sentinel?

    max_tokens can end a stream mid-tag, and flush() used to hand that
    fragment to the reader. Anything from `<v` on that can only be the
    sentinel's opening is dropped; a lone `<` could be prose, and is kept.
    """
    if len(held) < 2:
        return False
    low = held.lower()
    body = low[2:] if low.startswith("</") else low[1:]
    return body.startswith(_OPEN_BODY) or _OPEN_BODY.startswith(body)


def _read_tag(attrs: str) -> tuple[int | None, bool | None, str | None] | None:
    """(confidence, trusted, used) from one tag's attributes, each read on
    its own — None for any the tag does not state well-formed. None for the
    whole tag when it states nothing at all.

    Independently, because requiring both threw away a well-formed
    trusted="no" whenever the confidence was junk (found by review) — and
    trusted="no", with used="", is the model's only way to LOWER a label.
    """
    confidence = _CONFIDENCE_RE.search(attrs)
    trusted = _TRUSTED_RE.search(attrs)
    used = _USED_RE.search(attrs)
    if confidence is None and trusted is None and used is None:
        return None
    return (int(confidence.group(1)) if confidence else None,
            trusted.group(1).lower() == "yes" if trusted else None,
            used.group(1) if used else None)


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
        buf = _TAG_RE.sub("", self._held + delta)   # every complete tag goes
        self._held = ""

        cut = _hold_from(buf)       # a run that may still become a sentinel
        if cut != -1:
            self._held = buf[cut:]
            buf = buf[:cut]
        return buf

    def flush(self) -> str:
        """End of stream: a held run that never became a sentinel is text —
        unless the stream stopped inside one (see _is_cut_sentinel)."""
        held, self._held = self._held, ""
        return "" if _is_cut_sentinel(held) else held

    def _last(self) -> tuple[int | None, bool, str | None] | None:
        """The LAST tag that says something. Last, not first: a paused turn
        resumes and the model may restate its verdict."""
        for match in reversed(list(_TAG_RE.finditer(self._full))):
            read = _read_tag(match.group(1))
            if read is not None:
                return read
        return None

    def parse(self) -> tuple[int | None, bool | None]:
        """(confidence, trusted) from the LAST sentinel, or (None, None).

        A missing or malformed sentinel is not an error — it means the answer
        carries no stated confidence, and (crucially) that nothing may be
        escalated on the strength of it.
        """
        last = self._last()
        if last is None:
            return None, None
        confidence, trusted, _ = last
        if confidence is None or not 0 <= confidence <= 100:
            return None, trusted            # a nonsense number is no number
        # Round to 5: a model's "82%" is false precision, and displaying it
        # to the digit implies a calibration nobody has measured.
        return round(confidence / 5) * 5, trusted

    def used(self) -> list[str] | None:
        """Domains from the LAST sentinel's `used`, or None if not given."""
        last = self._last()
        return None if last is None else parse_used(last[2])


def parse_used(raw: str | None) -> list[str] | None:
    """The `used` attribute -> normalized domains, or None when it is absent.

    Forgiving about what the model writes (commas, URLs, `www.`, a path) and
    strict about what comes out: plain hostnames only. None means "no list was
    given" and must leave the sources alone; [] means "relied on nothing".

    Two review findings, in opposite directions. used="Alt News" (names, not
    domains) parsed to [] and stripped every source from an answer that had
    NAMED its source — words we cannot read are unsaid. But then used="none"
    became "unsaid" too, and every raw result came back as a receipt —
    Manchester City Council for a Nagpur claim, the exact thing used= exists
    to stop. The prompt asks for used=""; models write the words instead, so
    the words are read as what they plainly mean.
    """
    if raw is None:
        return None
    if raw.strip().lower() in _NOTHING:
        return []
    domains: list[str] = []
    for token in re.split(r"[\s,;]+", raw.strip().lower()):
        token = re.sub(r"^[a-z]+://", "", token).split("/")[0].split("?")[0]
        token = token.removeprefix("www.").strip(".")
        if token and _DOMAIN_RE.match(token) and token not in domains:
            domains.append(token)
    return domains or None


# Renderers strip ANYTHING that opens like a sentinel, as defence in depth for
# invariant 7 — including rows stored before a fix. It needed a closing `>`,
# so a row cut off mid-tag by max_tokens showed it (found by review); a tag
# or an opener cut off at the very END is stripped too. static/index.html
# carries the same pattern as SENTINEL_RE — a test keeps them in step.
_ANY_SENTINEL_RE = re.compile(
    r"</?verdict\b" + _ATTRS + r">"          # a tag, quoted brackets and all
    r"|</?verdict\b[^<]*$"                   # one cut off at the very end
    r"|</?v(?:e(?:r(?:d(?:i(?:c)?)?)?)?)?$",  # an opener cut off at the end
    re.IGNORECASE)


def strip_any_sentinel(text: str) -> str:
    """Remove every sentinel-shaped tag, well-formed or not. For renderers."""
    return _ANY_SENTINEL_RE.sub("", text)


def strip_sentinels(text: str) -> str:
    """Remove any sentinel from a finished string (non-streaming paths)."""
    return _TAG_RE.sub("", text).strip()
