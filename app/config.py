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

    # Model tiers  (see docs: $5/$25 vs $1/$5 per MTok)
    opus_model: str = "claude-opus-4-8"   # adjudication, extraction, vision OCR
    haiku_model: str = "claude-haiku-4-5"  # language detect + translation

    # Storage
    db_path: str = "./data/verifier.db"

    # Retrieval
    max_search_uses: int = 4  # cap web_search rounds per claim (each ~$0.01)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
