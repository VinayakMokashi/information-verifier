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
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

_LIVE_APP = "http://127.0.0.1:8000"
_LIVE_WAIT_S = 600.0


def through_live_app(url: str, client=None) -> dict | None:
    """The link, sent to the app already running on this machine, as the
    page sends it; its finished report, or None if it was refused.

    MEASURED 2026-11-19: with the app running (it always is, since go-live),
    this script's own copy of the app could not start: the database lock
    refuses a second one, as it should. From this machine no Turnstile is
    asked, and the check goes through today's budget and the ledger like
    any other."""
    import httpx

    own = client is None
    client = client or httpx.Client(base_url=_LIVE_APP, timeout=30)
    try:
        resp = client.post("/api/v1/verify/link", json={"url": url})
        if resp.status_code != 202:
            print(f"REJECTED ({resp.status_code}): {resp.json().get('detail')}")
            return None
        job_id = resp.json()["job_id"]
        deadline = time.monotonic() + _LIVE_WAIT_S
        while True:
            payload = client.get(f"/api/v1/reports/{job_id}").json()
            if payload.get("status") in ("COMPLETE", "FAILED") or time.monotonic() > deadline:
                return payload
            time.sleep(2)
    finally:
        if own:
            client.close()


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
    from app.store.instance import AlreadyRunning
    from scripts.render import force_utf8_stdout, print_answer
    from scripts.usage_report import print_usage

    force_utf8_stdout()

    # TestClient runs BackgroundTasks before returning, so the POST blocks
    # until the whole job (download -> ASR -> answer) is done. Nothing streams
    # here on purpose: this script exists to measure the finished bill.
    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/verify/link", json={"url": url})
            if resp.status_code != 202:
                print(f"REJECTED ({resp.status_code}): {resp.json().get('detail')}")
                return
            job_id = resp.json()["job_id"]
            payload = client.get(f"/api/v1/reports/{job_id}").json()
    except AlreadyRunning:
        print(">> The app is running on this machine: sending the link to it, as "
              "the page would. It counts against today's budget.\n")
        payload = through_live_app(url)
        if payload is None:
            return

    print_answer(Answer.model_validate(payload))
    print_usage(payload.get("usage"))


if __name__ == "__main__":
    main()
