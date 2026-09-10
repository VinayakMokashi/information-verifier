r"""REAL end-to-end check of a pasted Reel/Shorts link. COSTS MONEY.

Needs ANTHROPIC_API_KEY (+ SARVAM_API_KEY when the post has no subtitles).
Spends: Sarvam ASR on the clip's audio, then Claude + web search.

This drives the real HTTP route rather than the engine directly, so what it
proves is the whole surface a phone would use — including the caps that
protect the wallet before any of it runs.

    .venv\Scripts\python.exe scripts\link_smoke.py <url>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402


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
    from app.models.answer import Answer
    from scripts.render import force_utf8_stdout, print_answer
    from scripts.usage_report import print_usage

    force_utf8_stdout()

    # TestClient runs BackgroundTasks before returning, so the POST blocks
    # until the whole job (download -> ASR -> answer) is done. Nothing streams
    # here on purpose: this script exists to measure the finished bill.
    with TestClient(app) as client:
        resp = client.post("/api/v1/verify/link", json={"url": url})
        if resp.status_code != 202:
            print(f"REJECTED ({resp.status_code}): {resp.json().get('detail')}")
            return
        job_id = resp.json()["job_id"]
        payload = client.get(f"/api/v1/reports/{job_id}").json()

    print_answer(Answer.model_validate(payload))
    print_usage(payload.get("usage"))


if __name__ == "__main__":
    main()
