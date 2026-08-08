"""REAL end-to-end check of a pasted Reel/Shorts link. COSTS MONEY.

Needs ANTHROPIC_API_KEY (+ SARVAM_API_KEY when the post has no subtitles).
Spends: Sarvam ASR on the clip's audio, Haiku retrieval + web search, Opus
extraction + adjudication, Haiku back-translation.

Every report now carries its own measured bill (report.usage — built after
this script's one-off meter proved the idea), so this script simply runs the
real route and prints what the app itself measured.

    .venv\Scripts\python.exe scripts\link_smoke.py <url>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402


def _print_usage(usage: dict | None) -> None:
    print()
    print("=" * 66)
    if not usage:
        print("MEASURED SPEND: missing — report predates the meter?")
        return
    print("MEASURED SPEND (from report.usage — the API's own usage fields)")
    print("=" * 66)
    for model, row in sorted((usage.get("models") or {}).items()):
        print(f"{model}: {row['calls']} call(s)  "
              f"in={row['input_tokens']:,} out={row['output_tokens']:,} "
              f"cache_w={row['cache_write_tokens']:,} cache_r={row['cache_read_tokens']:,}")
    print(f"web searches: {usage.get('web_searches', 0)}")
    print(f"ASR audio   : {usage.get('asr_seconds', 0.0):.1f}s")
    print("-" * 66)
    print(f"estimated total: ${usage.get('estimated_usd', 0.0):.4f}")


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        return
    url = sys.argv[1]
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY in .env. Aborting (no cost).")
        return

    print(">> This calls PAID APIs: Sarvam ASR + Anthropic + web search.")
    print(f">> Checking: {url}\n")

    from fastapi.testclient import TestClient

    from app.main import app
    from app.models.report import TruthReport
    from scripts.render import print_report

    # TestClient runs BackgroundTasks before returning, so the POST blocks
    # until the whole job (download -> ASR -> pipeline -> translation) is done.
    with TestClient(app) as client:
        resp = client.post("/api/v1/verify/link", json={"url": url})
        if resp.status_code != 202:
            print(f"REJECTED ({resp.status_code}): {resp.json().get('detail')}")
            return
        job_id = resp.json()["job_id"]
        report = client.get(f"/api/v1/reports/{job_id}").json()

    print_report(TruthReport.model_validate(report))
    _print_usage(report.get("usage"))


if __name__ == "__main__":
    main()
