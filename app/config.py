"""Central settings, loaded once from environment / .env.

Model IDs live here so the whole engine swaps models in one place: the chat
check and vision OCR both run on Sonnet 5 since the 2026-09 pivot.
"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _credential():
    """A key field that no repr, str or dump of Settings ever shows.

    MEASURED 2026-09-29: a failing assert displayed this object with the
    start of the real Anthropic key (PROJECT_PLAN §11 17). Plain `str`, not
    SecretStr, on purpose: providers, the demo's key-blanking and the tests
    all assign and read plain strings. tests/test_secrets.py fails any field
    named like a credential that is declared without this.
    """
    return Field(default="", repr=False, exclude=True)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credentials
    anthropic_api_key: str = _credential()
    google_factcheck_api_key: str = _credential()
    sarvam_api_key: str = _credential()
    hf_token: str = _credential()  # unused since the pivot removed the local embedding model
    telegram_bot_token: str = _credential()  # from @BotFather; used only by scripts/telegram_bot.py

    # Vision OCR still needs a model of its own (it is not the chat call).
    vision_model: str = "claude-sonnet-5"

    # Storage
    db_path: str = "./data/verifier.db"

    # Chat engine (the pivot, 2026-09-10) — one Claude call per check,
    # whitelist-first then open web. Sonnet 5 chosen over Opus 5 on cost:
    # this workload is mostly "read these search results and explain them",
    # not the hard adjudication the old pipeline needed Opus for.
    chat_model: str = "claude-sonnet-5"
    chat_effort: str = "medium"      # low | medium | high | xhigh | max
    chat_max_tokens: int = 12000     # caps thinking + prose; a pre-call bound
    chat_max_searches_trusted: int = 3
    chat_max_searches_web: int = 2
    web_tier_enabled: bool = True    # False = whitelist only, never escalate
    # When Google's free Fact Check API found vetted fact-checks, answer from
    # them with no search tool first (2026-10-10, PROJECT_PLAN §7). False =
    # always search; the kill switch if its answers ever disappoint.
    factcheck_shortcut_enabled: bool = True
    # An answer resting only on general web sources can never show a
    # fact-checker-grade number. None = no cap (a trust decision; see §11).
    web_tier_confidence_cap: int | None = 75
    # Exact-match answer cache. TTL by tier because "no fact-checker has
    # covered this" is wrong the day one does.
    answer_cache_ttl_trusted_h: int = 168   # 7 days
    answer_cache_ttl_web_h: int = 24
    # What a pasted link said, by its platform video id. A post's audio does
    # not change; its caption can, so this still expires.
    transcript_cache_ttl_days: int = 30
    # Every stranger's message used to be kept forever. Answers (which hold
    # the message, what a machine read from it, and the reply) are deleted
    # after this many days; the spend ledger keeps the costs, with no content.
    answer_retention_days: int = 30

    # Media — audio/video via ffmpeg + Sarvam Saaras
    max_media_bytes: int = 25 * 1024 * 1024  # 25 MB upload cap — upload routes ONLY
    # Every other request body. REPRODUCED 2026-10-15: the 25 MB upload cap
    # was the only cap, so a 25 MB JSON "message" was parsed whole and the
    # small-talk triage froze the whole server for 10-19 s before any limit.
    # Fits a max_input_chars message even fully \uXXXX-escaped (a test pins it).
    max_json_bytes: int = 64 * 1024
    max_media_seconds: int = 300             # 5 min cap — protects ASR credits
    asr_chunk_seconds: int = 29              # Sarvam sync API takes <=30 s per request

    # Spending guard — every check costs money and the share link is public.
    # One submission is one answer since the pivot (it used to fan out to a
    # paid check per claim), so a count of submissions now bounds spend.
    rate_limit_enabled: bool = True
    max_checks_per_hour: int = 10   # per visitor IP (abuse, not spend)
    # DECIDED 2026-09-22 by Vinayak, before the first live use: "lower it for
    # now and do only 2 checks per day, just to be safe. We can increase it
    # later." Across the whole deployment — web page and Telegram bot share
    # it. Persisted in SQLite so a restart cannot quietly hand out two more.
    # Raise it here (or MAX_CHECKS_PER_DAY in .env); PROJECT_PLAN §7 has why.
    # RAISED to 5 on 2026-09-29 for the answer-quality checks ("use 5 or even
    # more if you want"). Measured checks run $0.05–0.26, so a full day is at
    # most ~$1.30. Five, not more: quality testing needs a handful a day, and
    # the cap's job is still to bound a bad day.
    max_checks_per_day: int = 5
    # When "a day" rolls over. IST (UTC+5:30), because the person watching the
    # bill is in India and "2 a day" means his day. A fixed offset rather than
    # a zone name: India has no DST, and zoneinfo needs the tzdata package on
    # Windows.
    day_boundary_utc_offset_min: int = 330
    max_input_chars: int = 5000     # a forwarded message, not a book


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
