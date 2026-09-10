"""REAL end-to-end check of one claim through the live engine. COSTS MONEY.

Needs ANTHROPIC_API_KEY in .env. Calls Claude + web search — modelled at
~$0.16 for a single pass and ~$0.26 when no fact-checker has covered the claim
and the open-web pass runs too. The bill it prints at the end is MEASURED,
from the API's own usage fields; trust that over the model.

Run from the project root:
    .venv\\Scripts\\python.exe scripts\\smoke_test.py
    .venv\\Scripts\\python.exe scripts\\smoke_test.py "your claim here"
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402
from app.engine.job import run_check  # noqa: E402
from app.models.answer import Answer, JobStatus  # noqa: E402
from app.store.db import init_db  # noqa: E402
from app.store.repository import AnswerRepository  # noqa: E402
from scripts.render import force_utf8_stdout, print_answer  # noqa: E402
from scripts.usage_report import print_usage  # noqa: E402


class ConsoleStream:
    """Watch the money being spent as it is spent. `publish` only — same duck
    typing as the offline demo, for the same reason."""

    async def publish(self, kind: str, data: dict) -> None:
        if kind == "status":
            print(f"\n[{data.get('text', '')}]")
        elif kind == "text":
            print(data.get("text", ""), end="", flush=True)
        elif kind == "tier":
            print("\n\n--- no fact-checker covered this; general web below ---")
        elif kind == "done":
            print()


async def main() -> None:
    force_utf8_stdout()
    if not settings.anthropic_api_key:
        print("No ANTHROPIC_API_KEY found in .env. Add it first. Aborting (no cost).")
        return

    claim = sys.argv[1] if len(sys.argv) > 1 else \
        "WHO ne kaha hai ki 5G se coronavirus phailta hai."

    print(">> This calls the PAID Anthropic API + web search.")
    print(f">> Model: {settings.chat_model} (effort {settings.chat_effort}), "
          f"open-web pass {'ON' if settings.web_tier_enabled else 'OFF'}")
    print(f">> Checking: {claim}\n")

    init_db()
    repo = AnswerRepository()
    answer = Answer(job_id=uuid.uuid4().hex, status=JobStatus.QUEUED,
                    created_at=datetime.now(timezone.utc), input_text=claim)
    repo.save(answer)

    await run_check(answer.job_id, claim, repo, ConsoleStream())
    stored = repo.get(answer.job_id)
    print_answer(stored)
    print_usage(stored.usage.model_dump() if stored.usage else None)


if __name__ == "__main__":
    asyncio.run(main())
