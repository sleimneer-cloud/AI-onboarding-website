from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi import Request, Response
from pydantic import ValidationError

from app.api.dependencies import enforce_role, ensure_resource_owner
from app.core.config import Settings
from app.core.errors import ApiProblem
from app.models.enums import UserRole
from app.schemas.auth import LoginRequest
from app.security.cookies import (
    delete_session_cookie,
    session_cookie_policy,
    set_session_cookie,
)
from app.security.passwords import PasswordManager
from app.security.requests import direct_peer_address, enforce_origin
from app.security.tokens import (
    generate_opaque_token,
    hash_opaque_token,
    rate_limit_subject_hash,
    tokens_match,
)
from app.services.auth import AuthContext, AuthenticatedUser, normalize_email


def _request(*, origin: str | None = None, forwarded_for: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if origin is not None:
        headers.append((b"origin", origin.encode()))
    if forwarded_for is not None:
        headers.append((b"x-forwarded-for", forwarded_for.encode()))
    return Request(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": ("198.51.100.24", 43210),
            "server": ("test", 80),
        }
    )


def _context(role: UserRole = UserRole.EMPLOYEE) -> AuthContext:
    now = datetime.now(UTC)
    return AuthContext(
        session_id=uuid4(),
        user=AuthenticatedUser(
            id=uuid4(),
            name="테스트 사용자",
            email="person@ix-demo.test",
            role=role,
            is_active=True,
        ),
        csrf_token_hash="a" * 64,
        expires_at=now + timedelta(hours=8),
    )


def test_settings_require_strong_session_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(_env_file=None, session_secret="short")

    with pytest.raises(ValidationError, match="required"):
        Settings(_env_file=None, app_env="production", session_secret=None)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, login_rate_limit_max_failures=100)


def test_settings_normalize_origin_and_reject_paths() -> None:
    settings = Settings(_env_file=None, app_origin="HTTPS://Example.TEST/")
    assert settings.app_origin == "https://example.test"

    with pytest.raises(ValidationError, match="without path"):
        Settings(_env_file=None, app_origin="https://example.test/login")


def test_password_manager_uses_argon2id_and_dummy_verification() -> None:
    manager = PasswordManager()
    password_hash = manager.hash("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert manager.verify_or_dummy("correct horse battery staple", password_hash) is True
    assert manager.verify_or_dummy("wrong", password_hash) is False
    assert manager.verify_or_dummy("unknown password", None) is False


def test_opaque_tokens_are_hashed_and_compared_without_raw_storage() -> None:
    raw_token = generate_opaque_token()
    token_hash = hash_opaque_token(raw_token)

    assert raw_token != token_hash
    assert len(token_hash) == 64
    assert tokens_match(raw_token, token_hash) is True
    assert tokens_match(f"{raw_token}x", token_hash) is False


def test_rate_limit_subject_is_keyed_and_domain_separated() -> None:
    first = rate_limit_subject_hash(
        normalized_email="person@example.test",
        client_address="198.51.100.24",
        secret="s" * 32,
    )
    second = rate_limit_subject_hash(
        normalized_email="person@example.test",
        client_address="198.51.100.25",
        secret="s" * 32,
    )

    assert len(first) == 64
    assert first != second
    assert "person@example.test" not in first


def test_direct_peer_ignores_spoofed_forwarding_headers() -> None:
    request = _request(forwarded_for="203.0.113.99")
    assert direct_peer_address(request) == "198.51.100.24"


def test_origin_must_match_configured_origin_exactly() -> None:
    settings = Settings(_env_file=None, app_origin="https://example.test")
    enforce_origin(_request(origin="https://example.test"), settings)

    with pytest.raises(ApiProblem) as missing:
        enforce_origin(_request(), settings)
    assert missing.value.code == "ORIGIN_FORBIDDEN"

    with pytest.raises(ApiProblem) as wrong:
        enforce_origin(_request(origin="https://evil.test"), settings)
    assert wrong.value.code == "ORIGIN_FORBIDDEN"


def test_cookie_policy_separates_local_and_production() -> None:
    local = Settings(_env_file=None, app_env="test", session_secret="s" * 32)
    production = Settings(
        _env_file=None,
        app_env="production",
        app_origin="https://example.test",
        session_secret="s" * 32,
    )

    assert session_cookie_policy(local).name == "ix_session"
    assert session_cookie_policy(local).secure is False
    assert session_cookie_policy(production).name == "__Host-ix_session"
    assert session_cookie_policy(production).secure is True

    response = Response()
    set_session_cookie(response, "raw-session-token", production)
    cookie = response.headers["set-cookie"]
    assert "__Host-ix_session=raw-session-token" in cookie
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    assert "Domain=" not in cookie

    delete_response = Response()
    delete_session_cookie(delete_response, production)
    assert "Max-Age=0" in delete_response.headers["set-cookie"]


def test_login_request_rejects_unknown_fields_and_normalizes_email_in_service() -> None:
    with pytest.raises(ValidationError):
        LoginRequest.model_validate(
            {"email": "person@example.test", "password": "secret", "role": "hr"}
        )

    assert normalize_email("  Person@Example.TEST  ") == "person@example.test"


@pytest.mark.parametrize("role", list(UserRole))
def test_each_role_is_allowed_only_when_explicitly_listed(role: UserRole) -> None:
    context = _context(role)
    enforce_role(context, frozenset({role}))

    with pytest.raises(ApiProblem) as forbidden:
        enforce_role(context, frozenset(set(UserRole) - {role}))
    assert forbidden.value.status_code == 403
    assert forbidden.value.code == "ROLE_FORBIDDEN"


def test_ownership_helper_hides_another_users_resource() -> None:
    employee = _context(UserRole.EMPLOYEE)

    ensure_resource_owner(employee.user.id, employee.user.id)
    with pytest.raises(ApiProblem) as hidden:
        ensure_resource_owner(uuid4(), employee.user.id)
    assert hidden.value.status_code == 404
    assert hidden.value.code == "RESOURCE_NOT_FOUND"
