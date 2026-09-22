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
# Only a run that opens `<verdict` is ever held this long, and a real one is
# always the last thing in the answer. It used to be 700, with `used` capped
# at 600 INSIDE the regex — so a model that wrote full URLs (which parse_used
# deliberately tolerates) produced a tag nothing recognised, and the reader
# saw it (found by review). The cap now only bounds how long a stray
# `<verdict` in the middle of prose can delay the rest of the answer.
_MAX_HOLD = 4000

# Recognising the TAG is separate from reading it, because every tag must go
# whether or not it parses: invariant 7 says the sentinel is never shown, and
# a malformed one is still the sentinel. Attributes are read in ANY order —
# a tag with used= before trusted= used to match nothing and leak.
_TAG_RE = re.compile(r"<verdict\b([^<>]*)>", re.IGNORECASE)
_CONFIDENCE_RE = re.compile(r'\bconfidence\s*=\s*"(\d{1,3})"', re.IGNORECASE)
_TRUSTED_RE = re.compile(r'\btrusted\s*=\s*"(yes|no)"', re.IGNORECASE)
_USED_RE = re.compile(r'\bused\s*=\s*"([^"]*)"', re.IGNORECASE)
_DOMAIN_RE = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
# What a model writes when it means used="" — "relied on nothing", not
# "unreadable". Nothing here can be a domain, so no real list is swallowed.
_NOTHING = frozenset({"", "none", "nothing", "nil", "n/a", "na", "null", "-",
                      "--", "no sources", "no source", "not applicable"})
_WORD_CHAR = re.compile(r"\w")


def _could_still_become_sentinel(tail: str) -> bool:
    """Is `tail` a prefix of a sentinel that later deltas might complete?

    Case-insensitive, like the tag itself — the hold-back used to compare
    exactly while the regex ignored case, so `<Ver` + `dict …` split across
    two deltas went straight to the reader (found by review).
    """
    if len(tail) > _MAX_HOLD:
        return False
    low = tail.lower()
    if low.startswith(_OPEN):
        after = tail[len(_OPEN):len(_OPEN) + 1]
        if after and _WORD_CHAR.match(after):
            return False            # "<verdicts": a word, not the tag
        return ">" not in tail      # an opened tag, not yet closed
    return _OPEN.startswith(low)    # a partial opener: `<`, `<Ver`, ...


def _is_cut_sentinel(held: str) -> bool:
    """At the end of the stream: did the answer stop INSIDE the sentinel?

    max_tokens can end a stream mid-tag, and flush() used to hand that
    fragment to the reader. Anything from `<v` on that can only be the
    sentinel's opening is dropped; a lone `<` could be prose, and is kept.
    """
    low = held.lower()
    return len(held) >= 2 and (low.startswith(_OPEN) or _OPEN.startswith(low))


def _read_tag(attrs: str) -> tuple[int | None, bool, str | None] | None:
    """(confidence, trusted, used) from one tag's attributes; None if the
    tag lacks a well-formed confidence or trusted — then it says nothing."""
    confidence = _CONFIDENCE_RE.search(attrs)
    trusted = _TRUSTED_RE.search(attrs)
    if confidence is None or trusted is None:
        return None
    used = _USED_RE.search(attrs)
    return (int(confidence.group(1)), trusted.group(1).lower() == "yes",
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

        # Whatever trails after the last `<` may still be a sentinel opening.
        cut = buf.rfind("<")
        if cut != -1 and _could_still_become_sentinel(buf[cut:]):
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
        if not 0 <= confidence <= 100:      # a nonsense number is no number
            return None, trusted
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
    r"<verdict\b[^<>]*(?:>|$)|<v(?:e(?:r(?:d(?:i(?:c)?)?)?)?)?$", re.IGNORECASE)


def strip_any_sentinel(text: str) -> str:
    """Remove every sentinel-shaped tag, well-formed or not. For renderers."""
    return _ANY_SENTINEL_RE.sub("", text)


def strip_sentinels(text: str) -> str:
    """Remove any sentinel from a finished string (non-streaming paths)."""
    return _TAG_RE.sub("", text).strip()
