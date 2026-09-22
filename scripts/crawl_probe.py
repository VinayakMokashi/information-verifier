r"""Which whitelisted domains will Anthropic's web search actually accept?

`allowed_domains` is ALL-OR-NOTHING (measured 2026-07-24): if one listed domain
blocks Anthropic's crawler, the entire search request is rejected with HTTP 400.
The engine survives that by retrying with the five crawler-verified core
domains — which silently shrinks a general-purpose checker back to Indian
fact-checkers for that request. This script finds out BEFORE a real check does.

    .venv\Scripts\python.exe scripts\crawl_probe.py                  # the live list
    .venv\Scripts\python.exe scripts\crawl_probe.py example.org ...  # plus candidates

COST: effectively nothing. A rejected request is a 400 and is not billed. An
accepted one is a tiny prompt at effort "low" with max_tokens=64 that asks the
model not to search — measured below, typically a fraction of a cent. Nothing
is cached or stored.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.trusted_sources import SEARCH_DOMAINS, domains_named_in  # noqa: E402
from scripts.render import force_utf8_stdout  # noqa: E402


def main() -> int:
    # Measured the hard way on this script's first run: the API call succeeded
    # and the cp1252 console then killed the report of it.
    force_utf8_stdout()
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY in .env. Aborting (no cost).")
        return 2
    import anthropic

    from app.providers.usage import UsageMeter

    extra = [d.strip().lower() for d in sys.argv[1:] if d.strip()]
    domains = list(dict.fromkeys(SEARCH_DOMAINS + extra))
    print(f">> Probing {len(domains)} domains against {settings.chat_model} "
          f"({len(extra)} extra candidate(s)).")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        resp = client.messages.create(
            model=settings.chat_model,
            max_tokens=64,
            output_config={"effort": "low"},
            tools=[{"type": "web_search_20260209", "name": "web_search",
                    "max_uses": 1, "allowed_domains": domains}],
            messages=[{"role": "user",
                       "content": "Reply with just the word OK. Do not search."}],
        )
    except anthropic.BadRequestError as exc:
        text = str(exc)
        named = domains_named_in(text, domains)
        print(f"\nREJECTED (400, not billed). The API said:\n  {text[:1500]}\n")
        if named:
            print(f"{len(named)} domain(s) named as inaccessible:")
            for d in named:
                print(f"  - {d}")
            print("\nMove these to FACTCHECK_ONLY_DOMAINS (still trusted when "
                  "cited, reached via Google Fact Check instead of search).")
        else:
            print("No requested domain was named — the 400 is about something "
                  "else. Read the message above.")
        return 1

    usage = resp.usage
    # Priced by the same meter that bills real answers, so the probe's figure
    # and the app's figure can never disagree about what a token costs.
    meter = UsageMeter()
    meter.note_llm(settings.chat_model, usage)
    bill = meter.snapshot()
    searched, usd = bill.web_searches, bill.estimated_usd
    print(f"\nACCEPTED: all {len(domains)} domains passed validation.")
    print(f"  stop_reason={resp.stop_reason}  searches={searched}  "
          f"in={usage.input_tokens} out={usage.output_tokens}  cost~${usd:.4f}")
    # Every field, not just the ones this script knows about: the 20260209
    # search tool filters results with code execution, and if that ever
    # shows up as its own billable line, this is where it appears first.
    print(f"  raw usage: {usage.model_dump(exclude_none=True)}")
    if not searched:
        print("  (No search ran, so this proves the request was accepted — the "
              "first real check is what proves every domain returns results.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
