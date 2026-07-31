import pytest
from pydantic import ValidationError

from app.core.config import REPOSITORY_ROOT, Settings
from app.services.readiness import normalize_database_url


def test_settings_resolve_repository_relative_frontend_path() -> None:
    settings = Settings(_env_file=None, frontend_dist_dir="frontend/custom-dist")

    assert settings.frontend_dist_dir == (REPOSITORY_ROOT / "frontend/custom-dist").resolve()


def test_blank_database_url_is_treated_as_unset() -> None:
    settings = Settings(_env_file=None, database_url="  ")

    assert settings.database_url is None


def test_invalid_readiness_timeout_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_ready_timeout_seconds=0)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("postgresql://user:pass@db/name", "postgresql+psycopg://user:pass@db/name"),
        ("postgres://user:pass@db/name", "postgresql+psycopg://user:pass@db/name"),
        ("postgresql+psycopg://user:pass@db/name", "postgresql+psycopg://user:pass@db/name"),
    ],
)
def test_database_url_normalization(source: str, expected: str) -> None:
    assert normalize_database_url(source) == expected


def test_non_postgresql_database_url_is_rejected() -> None:
    with pytest.raises(ValueError, match="PostgreSQL"):
        normalize_database_url("sqlite:///local.db")
