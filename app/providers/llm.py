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
