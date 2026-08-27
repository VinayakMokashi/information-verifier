"""Per-report spend metering — every report carries its own measured bill.

The cost model in PROJECT_PLAN §8 was exactly that — a model — until the
first metered run (2026-07-28, $0.279 vs $0.39 modelled). The gap matters to
a cost-conscious deployment, so measurement is now built in rather than
living in a smoke script.

Shape: a `UsageMeter` is created per job and made ambient with a contextvar,
because a report's work fans out (claims check concurrently, translations
too) and threading a meter argument through every stage would touch a dozen
signatures. contextvars propagate into `asyncio.gather` children and
`asyncio.to_thread` workers, so one `with meter.activate():` around the
pipeline body covers every call made on the report's behalf. The Anthropic
client is instrumented ONCE (idempotent) to report each call's usage — read
from the API's own usage fields, not estimated — into whatever meter is
active; with no meter active it is a no-op, so scripts and tests that never
asked for metering are untouched.

ASR seconds are noted where the audio's true duration is learned (ffprobe in
normalize_to_wav), which slightly over-counts if transcription then fails
mid-way — the conservative direction for a spend figure.
"""
from contextlib import contextmanager
from contextvars import ContextVar

from app.models.report import ModelUsage, ReportUsage

# $ per MTok, list prices. Tokens in a ReportUsage are measured facts; only
# the dollar estimate inherits this table's staleness. Cache writes bill at
# 1.25x input, cache reads at 0.1x.
_PRICES = {
    "claude-opus-4-8":  {"in": 5.0, "out": 25.0, "cache_w": 6.25, "cache_r": 0.50},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0,  "cache_w": 1.25, "cache_r": 0.10},
}
_FALLBACK_PRICE = _PRICES["claude-opus-4-8"]   # unknown model: price as the dearest
_SEARCH_USD = 0.01                              # per web_search request
_ASR_USD_PER_S = (30.0 / 3600.0) / 88.0         # Sarvam ₹30/hr at ~₹88/$

_current: ContextVar["UsageMeter | None"] = ContextVar("usage_meter", default=None)
# Guards against counting one API call twice if an SDK's parse() ever routes
# through its own create(). The installed SDK's parse() calls _post() directly
# (checked), so this is insurance, not a live fix — but a silently doubled
# bill is exactly the error this meter exists to prevent, and it would look
# entirely plausible in the report.
_in_call: ContextVar[bool] = ContextVar("usage_in_call", default=False)


class UsageMeter:
    def __init__(self) -> None:
        self._models: dict[str, ModelUsage] = {}
        self._searches = 0
        self._asr_seconds = 0.0

    @contextmanager
    def activate(self):
        """Make this meter ambient for everything awaited inside the block."""
        token = _current.set(self)
        try:
            yield self
        finally:
            _current.reset(token)

    def note_llm(self, model: str, usage) -> None:
        if usage is None:
            return
        row = self._models.setdefault(str(model), ModelUsage())
        row.calls += 1
        row.input_tokens += getattr(usage, "input_tokens", 0) or 0
        row.output_tokens += getattr(usage, "output_tokens", 0) or 0
        row.cache_write_tokens += getattr(usage, "cache_creation_input_tokens", 0) or 0
        row.cache_read_tokens += getattr(usage, "cache_read_input_tokens", 0) or 0
        server_tools = getattr(usage, "server_tool_use", None)
        self._searches += getattr(server_tools, "web_search_requests", 0) or 0

    def note_asr(self, seconds: float) -> None:
        self._asr_seconds += max(0.0, float(seconds))

    def snapshot(self) -> ReportUsage:
        usd = self._searches * _SEARCH_USD + self._asr_seconds * _ASR_USD_PER_S
        for model, row in self._models.items():
            p = _PRICES.get(model, _FALLBACK_PRICE)
            usd += (row.input_tokens * p["in"] + row.output_tokens * p["out"]
                    + row.cache_write_tokens * p["cache_w"]
                    + row.cache_read_tokens * p["cache_r"]) / 1e6
        return ReportUsage(
            models={m: r.model_copy() for m, r in self._models.items()},
            web_searches=self._searches,
            asr_seconds=round(self._asr_seconds, 2),
            estimated_usd=round(usd, 4),
        )


def note_llm(model: str, usage) -> None:
    """Report one API call into the ambient meter, if any."""
    meter = _current.get()
    if meter is not None:
        meter.note_llm(model, usage)


def note_asr(seconds: float) -> None:
    meter = _current.get()
    if meter is not None:
        meter.note_asr(seconds)


def instrument(client) -> None:
    """Wrap `client.messages.parse/create` to feed the ambient meter.

    Idempotent, and a strict no-op when no meter is active — demos, probes
    and tests behave exactly as before. Never raises: a metering bug must
    cost a usage row, not a report.
    """
    messages = client.messages
    if getattr(messages, "_usage_instrumented", False):
        return

    def wrap(real):
        async def metered(**kw):
            if _in_call.get():          # nested: the outer wrapper will count it
                return await real(**kw)
            token = _in_call.set(True)
            try:
                resp = await real(**kw)
            finally:
                _in_call.reset(token)
            try:
                note_llm(kw.get("model", "?"), getattr(resp, "usage", None))
            except Exception as exc:  # noqa: BLE001 — see docstring
                print(f"[usage] metering failed: {type(exc).__name__}: {exc}")
            return resp

        return metered

    messages.parse = wrap(messages.parse)
    messages.create = wrap(messages.create)
    messages._usage_instrumented = True
