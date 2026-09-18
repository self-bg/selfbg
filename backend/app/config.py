from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SELFBG_", env_file=".env", extra="ignore")

    api_key: str = ""
    model: str = "birefnet-general"
    max_upload_mb: int = 25
    cors_origins: str = "http://localhost:3000"
    redis_url: str = "redis://redis:6379/0"
    data_dir: str = "/data/jobs"
    result_ttl_seconds: int = 86400
    cleanup_interval_seconds: int = 3600

    # Video (Phase 4). CPU worker only for now; GPU support is a future phase.
    max_video_upload_mb: int = 200
    max_video_duration_seconds: int = 30
    max_video_short_side_px: int = 480
    rvm_model_path: str = "/models/rvm_mobilenetv3_fp32.onnx"

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
    def max_video_upload_bytes(self) -> int:
        return self.max_video_upload_mb * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
