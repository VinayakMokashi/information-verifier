"""REAL end-to-end check of a pasted Reel/Shorts link. COSTS MONEY.

Needs ANTHROPIC_API_KEY (+ SARVAM_API_KEY when the post has no subtitles).
Spends: Sarvam ASR on the clip's audio, Haiku retrieval + web search, Opus
extraction + adjudication, Haiku back-translation.

Unlike every earlier paid run, this one MEASURES what it spends: the shared
Anthropic client is wrapped so each call's token usage and web-search count
are recorded, and ASR seconds are captured at the ffmpeg boundary. The
printed breakdown is the project's first measured cost figure — §8's numbers
have been models until now.

    .venv\\Scripts\\python.exe scripts\\link_smoke.py <url>
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import settings  # noqa: E402

# $ per MTok — Anthropic list prices (PROJECT_PLAN §8). Cache writes bill at
# 1.25x input, cache reads at 0.1x input.
_PRICES = {
    settings.opus_model:  {"in": 5.0,  "out": 25.0, "cache_w": 6.25, "cache_r": 0.50},
    settings.haiku_model: {"in": 1.0,  "out": 5.0,  "cache_w": 1.25, "cache_r": 0.10},
}
_SEARCH_USD = 0.01           # per web search request
_ASR_INR_PER_S = 30.0 / 3600.0   # Sarvam ₹30/hour, billed by the second
_USD_INR = 88.0              # rough, for the single combined figure only


class Meter:
    def __init__(self) -> None:
        self.by_model: dict[str, dict[str, int]] = defaultdict(
            lambda: {"in": 0, "out": 0, "cache_w": 0, "cache_r": 0, "calls": 0})
        self.searches = 0
        self.asr_seconds = 0.0

    def note(self, model: str, usage) -> None:
        if usage is None:
            return
        row = self.by_model[model]
        row["calls"] += 1
        row["in"] += getattr(usage, "input_tokens", 0) or 0
        row["out"] += getattr(usage, "output_tokens", 0) or 0
        row["cache_w"] += getattr(usage, "cache_creation_input_tokens", 0) or 0
        row["cache_r"] += getattr(usage, "cache_read_input_tokens", 0) or 0
        stu = getattr(usage, "server_tool_use", None)
        self.searches += getattr(stu, "web_search_requests", 0) or 0

    def llm_usd(self) -> float:
        total = 0.0
        for model, row in self.by_model.items():
            p = _PRICES.get(model)
            if p is None:      # unknown model id — price as Opus, the dearest
                p = _PRICES[settings.opus_model]
            total += (row["in"] * p["in"] + row["out"] * p["out"]
                      + row["cache_w"] * p["cache_w"]
                      + row["cache_r"] * p["cache_r"]) / 1e6
        return total

    def report(self) -> str:
        lines = ["", "=" * 66, "MEASURED SPEND (not a model — read from API usage fields)",
                 "=" * 66]
        for model, row in sorted(self.by_model.items()):
            lines.append(
                f"{model}: {row['calls']} call(s)  "
                f"in={row['in']:,} out={row['out']:,} "
                f"cache_w={row['cache_w']:,} cache_r={row['cache_r']:,}")
        lines.append(f"web searches: {self.searches}  (${self.searches * _SEARCH_USD:.2f})")
        asr_inr = self.asr_seconds * _ASR_INR_PER_S
        lines.append(f"ASR audio: {self.asr_seconds:.1f}s  (Rs {asr_inr:.2f})")
        llm = self.llm_usd()
        search = self.searches * _SEARCH_USD
        total_usd = llm + search + asr_inr / _USD_INR
        lines.append("-" * 66)
        lines.append(f"LLM ${llm:.4f} + search ${search:.2f} + ASR Rs {asr_inr:.2f}"
                     f"  ~= ${total_usd:.3f} total")
        return "\n".join(lines)


def _arm(meter: Meter) -> None:
    """Wrap the seams every stage actually calls. Additive: real calls still run."""
    from app.api import routes as R
    from app.providers import llm

    real_parse = llm.async_client.messages.parse
    real_create = llm.async_client.messages.create

    async def parse(**kw):
        resp = await real_parse(**kw)
        meter.note(kw.get("model", "?"), getattr(resp, "usage", None))
        return resp

    async def create(**kw):
        resp = await real_create(**kw)
        meter.note(kw.get("model", "?"), getattr(resp, "usage", None))
        return resp

    llm.async_client.messages.parse = parse
    llm.async_client.messages.create = create

    real_norm = R.normalize_to_wav

    def norm(data, filename="media", max_seconds=None):
        wav, duration = real_norm(data, filename, max_seconds)
        meter.asr_seconds += duration   # what Sarvam will bill for, by the second
        return wav, duration

    R.normalize_to_wav = norm


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

    meter = Meter()
    _arm(meter)

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
            print(meter.report())
            return
        job_id = resp.json()["job_id"]
        report = client.get(f"/api/v1/reports/{job_id}").json()

    print_report(TruthReport.model_validate(report))
    print(meter.report())


if __name__ == "__main__":
    main()
