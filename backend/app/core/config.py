from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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
    session_secret: SecretStr | None = None
    session_ttl_seconds: Literal[28800] = 28800
    login_rate_limit_window_seconds: Literal[600] = 600
    login_rate_limit_max_failures: Literal[5] = 5
    login_rate_limit_block_seconds: Literal[900] = 900
    demo_account_password: SecretStr = SecretStr("DemoPassword!")
    demo_reference_date: date = date(2026, 8, 2)
    frontend_dist_dir: Path = DEFAULT_FRONTEND_DIST

    @field_validator("database_url", mode="before")
    @classmethod
    def blank_database_url_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("session_secret", mode="before")
    @classmethod
    def blank_session_secret_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("app_origin")
    @classmethod
    def validate_app_origin(cls, value: str) -> str:
        from urllib.parse import urlsplit

        candidate = value.strip()
        parsed = urlsplit(candidate)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("APP_ORIGIN must be one HTTP(S) origin without path or query")
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}"

    @model_validator(mode="after")
    def validate_authentication_secret(self) -> "Settings":
        if self.session_secret is not None:
            secret_bytes = self.session_secret.get_secret_value().encode("utf-8")
            if len(secret_bytes) < 32:
                raise ValueError("SESSION_SECRET must be at least 32 UTF-8 bytes")
        if self.app_env == "production" and self.session_secret is None:
            raise ValueError("SESSION_SECRET is required when APP_ENV=production")
        return self

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
