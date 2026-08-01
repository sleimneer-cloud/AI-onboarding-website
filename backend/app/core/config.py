from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_FRONTEND_DIST = REPOSITORY_ROOT / "frontend" / "dist"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "demo", "production"] = "local"
    app_origin: str = "http://127.0.0.1:5173"
    app_version: str = "0.1.0"
    database_url: SecretStr | None = None
    database_ready_timeout_seconds: float = Field(default=2.0, gt=0, le=10)
    demo_account_password: SecretStr = SecretStr("DemoPassword!")
    demo_reference_date: date = date(2026, 8, 2)
    frontend_dist_dir: Path = DEFAULT_FRONTEND_DIST

    @field_validator("database_url", mode="before")
    @classmethod
    def blank_database_url_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("frontend_dist_dir", mode="before")
    @classmethod
    def resolve_frontend_dist_dir(cls, value: object) -> Path:
        path = Path(str(value)).expanduser()
        if not path.is_absolute():
            path = REPOSITORY_ROOT / path
        return path.resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
