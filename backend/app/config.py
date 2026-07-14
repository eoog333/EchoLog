from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
    )

    rtzr_client_id: str
    rtzr_client_secret: str
    llm_api_key: str = ""


@lru_cache()
def get_settings() -> Settings:
    return Settings()
