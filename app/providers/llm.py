"""Shared async Anthropic client.

One AsyncAnthropic instance for the whole app — the pipeline is I/O-bound
fan-out, so async is load-bearing, not stylistic. Credentials resolve from
ANTHROPIC_API_KEY (or an `ant auth login` profile) automatically.
"""
import anthropic

from app.config import settings
from app.providers.usage import instrument

async_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key or None)
# Every call reports its measured token usage into the ambient per-report
# meter (a no-op when none is active). Done here so no stage can forget.
instrument(async_client)


# What a reader is told while Anthropic refuses for MONEY (paused_reason).
PAUSED_MESSAGE = "Checking is paused for now. Please try again later."

# The documented shapes (docs/research/2026-10-15/limits-budget.verification.md,
# from platform.claude.com/docs/en/api/errors and rate-limits, 2026-10-15):
# a spend limit the owner set -> 400 "You have reached your specified
# (workspace) API usage limits"; the account tier's monthly cap -> 429 with
# error.details.error_code "enforced_spend_limit_reached", failing "until
# access resumes"; a billing problem -> 402 billing_error. An exhausted credit
# balance is undocumented; historically a 400 naming the "credit balance".
_PAUSED_400 = ("specified api usage limits", "specified workspace api usage limits",
               "credit balance")


def paused_reason(exc: BaseException) -> str | None:
    """Why Anthropic refused for MONEY rather than for this request — or None.

    These fail for every check until someone pays or the month turns, and
    "failed requests aren't charged" (Anthropic's billing article): so a
    check refused this way cost nothing and is worth no retry. An ordinary
    rate limit, an overload or a bad request is NOT a pause.
    """
    if not isinstance(exc, anthropic.APIStatusError):
        return None
    status = exc.status_code
    body = exc.body if isinstance(exc.body, dict) else {}
    error = body.get("error") if isinstance(body.get("error"), dict) else {}
    details = error.get("details") if isinstance(error.get("details"), dict) else {}
    message = str(error.get("message") or exc)
    if status == 402:
        return f"HTTP 402 billing_error: {message[:200]}"
    if status == 429 and details.get("error_code") == "enforced_spend_limit_reached":
        return "HTTP 429 enforced_spend_limit_reached (the account tier's monthly cap)"
    if status == 400 and any(words in message.lower() for words in _PAUSED_400):
        return f"HTTP 400: {message[:200]}"
    return None


def tell_owner_paused(reason: str) -> None:
    """The one console line that says what to fix (Anthropic's own words)."""
    print(f"[paused] Anthropic refused a check for money: {reason}. Top up the "
          "credit balance or raise the spend limit (console.anthropic.com); "
          "until then paid checks pause, and one is let through every "
          f"{max(1, settings.paused_retry_s // 60)} minutes to see if it has cleared.")
