from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SELFBG_", env_file=".env", extra="ignore")

    api_key: str = ""
    model: str = "birefnet-general"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"

    @field_validator("api_key")
    @classmethod
    def _api_key_must_be_set(cls, value: str) -> str:
        if not value or len(value) < 16:
            raise ValueError(
                "SELFBG_API_KEY is required and must be at least 16 characters. "
                "Generate one with: openssl rand -hex 32"
            )
        return value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
