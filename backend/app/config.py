from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    rtzr_client_id: str
    rtzr_client_secret: str
    llm_api_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
