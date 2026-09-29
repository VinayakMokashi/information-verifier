"""One definition of "what did that cost", shared by every paid script.

Every job carries its own bill in `answer.usage`, built from the API's own
usage fields. The tokens are facts; only the dollar figure inherits staleness
from the pricing table in `app/providers/usage.py` — which is exactly why the
per-model token counts are printed too, not just the total.
"""


def format_usage(usage: dict | None) -> str:
    L = ["", "=" * 66]
    if not usage:
        L.append("MEASURED SPEND: missing — did the job fail before any call?")
        L.append("=" * 66)
        return "\n".join(L)
    L.append("MEASURED SPEND (from usage — the API's own numbers)")
    L.append("=" * 66)
    for model, row in sorted((usage.get("models") or {}).items()):
        L.append(f"{model}: {row['calls']} call(s)  "
                 f"in={row['input_tokens']:,} out={row['output_tokens']:,} "
                 f"cache_w={row['cache_write_tokens']:,} "
                 f"cache_r={row['cache_read_tokens']:,}")
    L.append(f"web searches: {usage.get('web_searches', 0)}")
    errors = usage.get("search_errors") or {}
    if errors:
        L.append("  failed    : " + ", ".join(
            f"{code} x{n}" for code, n in sorted(errors.items())))
    L.append(f"ASR audio   : {usage.get('asr_seconds', 0.0):.1f}s")
    L.append("-" * 66)
    L.append(f"estimated total: ${usage.get('estimated_usd', 0.0):.4f}")
    return "\n".join(L)


def print_usage(usage: dict | None) -> None:
    print(format_usage(usage))
