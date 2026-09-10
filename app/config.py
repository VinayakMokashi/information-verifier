"""Central settings, loaded once from environment / .env.

Model IDs live here so the whole pipeline swaps tiers in one place.
Reasoning + vision run on Opus 4.8; high-volume normalization on Haiku 4.5.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Credentials
    anthropic_api_key: str = ""
    google_factcheck_api_key: str = ""
    sarvam_api_key: str = ""
    hf_token: str = ""  # Hugging Face token — EmbeddingGemma is a gated repo
    telegram_bot_token: str = ""  # from @BotFather; used only by scripts/telegram_bot.py

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
    # An answer resting only on general web sources can never show a
    # fact-checker-grade number. None = no cap (a trust decision; see §11).
    web_tier_confidence_cap: int | None = 75
    # Exact-match answer cache. TTL by tier because "no fact-checker has
    # covered this" is wrong the day one does.
    answer_cache_ttl_trusted_h: int = 168   # 7 days
    answer_cache_ttl_web_h: int = 24




    # Media (Phase 2) — audio/video via ffmpeg + Sarvam Saaras
    max_media_bytes: int = 25 * 1024 * 1024  # 25 MB upload cap
    max_media_seconds: int = 300             # 5 min cap — protects ASR credits
    asr_chunk_seconds: int = 29              # Sarvam sync API takes <=30 s per request

    # Spending guard — every check costs money and the share link is public.
    # Rate limits count REQUESTS, so the per-request caps below are what
    # actually bound the worst case: one submission fans out to one paid
    # retrieval + adjudication per claim.
    rate_limit_enabled: bool = True
    max_checks_per_hour: int = 10   # per visitor IP
    max_checks_per_day: int = 100   # across the whole deployment
    max_input_chars: int = 5000     # a forwarded message, not a book


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
