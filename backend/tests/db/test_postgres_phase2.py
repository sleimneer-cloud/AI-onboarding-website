from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import REPOSITORY_ROOT, Settings
from app.core.errors import ApiProblem
from app.db.session import create_database_engine, create_session_factory, transaction
from app.main import create_app
from app.models.auth import AuthRateLimit, AuthSession, User
from app.security.passwords import PasswordManager
from app.security.tokens import hash_opaque_token
from app.services.auth import AuthService
from app.services.demo_data import reset_demo_data

pytestmark = pytest.mark.postgres

DEMO_PASSWORD = "Phase2TestPassword!"
SESSION_SECRET = "phase-2-test-session-secret-is-long-enough"
PEER_ADDRESS = "198.51.100.24"


def alembic_config() -> Config:
    return Config(str(REPOSITORY_ROOT / "backend" / "alembic.ini"))


@pytest.fixture(scope="module")
def postgres_url() -> Iterator[str]:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is required for PostgreSQL integration tests")

    parsed_url = make_url(database_url)
    if not parsed_url.drivername.startswith("postgresql"):
        pytest.fail("TEST_DATABASE_URL must use PostgreSQL")
    if "test" not in (parsed_url.database or "").lower():
        pytest.fail("Refusing Phase 2 tests outside a database named with 'test'")

    previous_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        command.upgrade(alembic_config(), "head")
        yield database_url
    finally:
        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url


@dataclass(frozen=True)
class AuthTestEnvironment:
    settings: Settings
    app: object
    client: AsyncClient

    @property
    def session_factory(self):
        return self.app.state.session_factory


@pytest_asyncio.fixture
async def auth_env(postgres_url: str) -> AsyncIterator[AuthTestEnvironment]:
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_origin="http://test",
        database_url=postgres_url,
        session_secret=SESSION_SECRET,
        demo_account_password=DEMO_PASSWORD,
        frontend_dist_dir=REPOSITORY_ROOT / "frontend" / "dist",
    )
    seed_engine = create_database_engine(settings)
    try:
        async with transaction(create_session_factory(seed_engine)) as session:
            await reset_demo_data(session, settings)
            await session.execute(delete(AuthRateLimit))
    finally:
        await seed_engine.dispose()

    app = create_app(settings)
    transport = ASGITransport(app=app, client=(PEER_ADDRESS, 43210))
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield AuthTestEnvironment(settings=settings, app=app, client=client)

    await app.state.database_engine.dispose()


async def _login(
    client: AsyncClient,
    *,
    email: str = "employee@ix-demo.test",
    password: str = DEMO_PASSWORD,
    origin: str | None = "http://test",
    extra_headers: dict[str, str] | None = None,
):
    headers = dict(extra_headers or {})
    if origin is not None:
        headers["Origin"] = origin
    return await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password},
    )


def _error_code(response) -> str:
    return response.json()["error"]["code"]


async def test_login_stores_only_hashes_and_authenticates_me(
    auth_env: AuthTestEnvironment,
) -> None:
    response = await _login(auth_env.client, email="  Employee@IX-DEMO.TEST  ")

    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["role"] == "employee"
    assert payload["default_path"] == "/employee"
    assert payload["csrf_token"]
    assert response.headers["Cache-Control"] == "no-store"
    cookie_header = response.headers["set-cookie"]
    assert "ix_session=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    assert "Secure" not in cookie_header
    assert "Max-Age=28800" in cookie_header

    raw_session_token = auth_env.client.cookies.get("ix_session")
    assert raw_session_token is not None
    async with auth_env.session_factory() as session:
        auth_session = (
            await session.execute(
                select(AuthSession)
                .join(User, User.id == AuthSession.user_id)
                .where(User.normalized_email == "employee@ix-demo.test")
            )
        ).scalar_one()
    assert auth_session.token_hash == hash_opaque_token(raw_session_token)
    assert auth_session.token_hash != raw_session_token
    assert auth_session.csrf_token_hash == hash_opaque_token(payload["csrf_token"])
    assert auth_session.csrf_token_hash != payload["csrf_token"]

    me_response = await auth_env.client.get("/api/v1/auth/me")
    assert me_response.status_code == 200
    assert me_response.json() == payload["user"]


@pytest.mark.parametrize(
    ("email", "role", "default_path"),
    [
        ("employee@ix-demo.test", "employee", "/employee"),
        ("manager@ix-demo.test", "manager", "/manager"),
        ("hr@ix-demo.test", "hr", "/hr"),
    ],
)
async def test_each_demo_role_receives_its_server_selected_default_path(
    auth_env: AuthTestEnvironment,
    email: str,
    role: str,
    default_path: str,
) -> None:
    response = await _login(auth_env.client, email=email)
    assert response.status_code == 200
    assert response.json()["user"]["role"] == role
    assert response.json()["default_path"] == default_path


async def test_unknown_and_wrong_password_share_generic_error(
    auth_env: AuthTestEnvironment,
) -> None:
    wrong = await _login(auth_env.client, password="WrongPassword!")
    unknown = await _login(
        auth_env.client,
        email="unknown@ix-demo.test",
        password="WrongPassword!",
    )

    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["error"]["code"] == "INVALID_CREDENTIALS"
    assert wrong.json()["error"]["message"] == unknown.json()["error"]["message"]


async def test_unknown_user_runs_dummy_password_verification(
    auth_env: AuthTestEnvironment,
) -> None:
    class SpyPasswordManager(PasswordManager):
        def __init__(self) -> None:
            self.password_hashes: list[str | None] = []

        def verify_or_dummy(self, password: str, password_hash: str | None) -> bool:
            del password
            self.password_hashes.append(password_hash)
            return False

    spy = SpyPasswordManager()
    service = AuthService(
        session_factory=auth_env.session_factory,
        settings=auth_env.settings,
        password_manager=spy,
    )

    with pytest.raises(ApiProblem) as invalid:
        await service.login(
            email="missing@ix-demo.test",
            password="does-not-matter",
            client_address=PEER_ADDRESS,
        )
    assert invalid.value.code == "INVALID_CREDENTIALS"
    assert spy.password_hashes == [None]


async def test_inactive_account_is_rejected_after_valid_password(
    auth_env: AuthTestEnvironment,
) -> None:
    async with transaction(auth_env.session_factory) as session:
        user = (
            await session.execute(
                select(User).where(User.normalized_email == "employee@ix-demo.test")
            )
        ).scalar_one()
        user.is_active = False

    response = await _login(auth_env.client)
    assert response.status_code == 403
    assert _error_code(response) == "USER_INACTIVE"


async def test_sixth_failure_blocks_login_and_forwarded_headers_are_ignored(
    auth_env: AuthTestEnvironment,
) -> None:
    responses = []
    for attempt in range(6):
        responses.append(
            await _login(
                auth_env.client,
                password="WrongPassword!",
                extra_headers={
                    "X-Forwarded-For": f"203.0.113.{attempt + 1}",
                    "Forwarded": f"for=203.0.113.{attempt + 1}",
                },
            )
        )

    assert [response.status_code for response in responses[:5]] == [401] * 5
    assert responses[5].status_code == 429
    assert _error_code(responses[5]) == "LOGIN_RATE_LIMITED"
    assert int(responses[5].headers["Retry-After"]) > 0

    async with auth_env.session_factory() as session:
        records = (await session.execute(select(AuthRateLimit))).scalars().all()
    assert len(records) == 1
    assert "employee@ix-demo.test" not in records[0].subject_hash
    assert "203.0.113" not in records[0].subject_hash

    blocked_valid_login = await _login(auth_env.client)
    assert blocked_valid_login.status_code == 429


async def test_expired_session_and_revoked_session_are_rejected(
    auth_env: AuthTestEnvironment,
) -> None:
    login_response = await _login(auth_env.client)
    assert login_response.status_code == 200
    raw_session_token = auth_env.client.cookies.get("ix_session")
    assert raw_session_token is not None

    async with transaction(auth_env.session_factory) as session:
        auth_session = (
            await session.execute(
                select(AuthSession).where(
                    AuthSession.token_hash == hash_opaque_token(raw_session_token)
                )
            )
        ).scalar_one()
        auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    expired = await auth_env.client.get("/api/v1/auth/me")
    assert expired.status_code == 401
    assert _error_code(expired) == "SESSION_EXPIRED"


async def test_csrf_rotation_logout_revoke_and_idempotent_logout(
    auth_env: AuthTestEnvironment,
) -> None:
    login_response = await _login(auth_env.client)
    payload = login_response.json()
    first_csrf = payload["csrf_token"]
    raw_session_token = auth_env.client.cookies.get("ix_session")
    assert raw_session_token is not None

    rotate = await auth_env.client.get("/api/v1/auth/csrf")
    assert rotate.status_code == 200
    assert rotate.headers["Cache-Control"] == "no-store"
    second_csrf = rotate.json()["csrf_token"]
    assert second_csrf != first_csrf

    stale = await auth_env.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://test", "X-CSRF-Token": first_csrf},
    )
    assert stale.status_code == 403
    assert _error_code(stale) == "CSRF_INVALID"

    logged_out = await auth_env.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://test", "X-CSRF-Token": second_csrf},
    )
    assert logged_out.status_code == 204
    assert "Max-Age=0" in logged_out.headers["set-cookie"]

    repeated = await auth_env.client.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": "http://test",
            "X-CSRF-Token": second_csrf,
            "Cookie": f"ix_session={raw_session_token}",
        },
    )
    assert repeated.status_code == 204

    rejected = await auth_env.client.get(
        "/api/v1/auth/me",
        headers={"Cookie": f"ix_session={raw_session_token}"},
    )
    assert rejected.status_code == 401
    assert _error_code(rejected) == "AUTH_REQUIRED"


async def test_logout_requires_origin_and_csrf_without_revoking_session(
    auth_env: AuthTestEnvironment,
) -> None:
    login_response = await _login(auth_env.client)
    assert login_response.status_code == 200

    missing_origin = await auth_env.client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": login_response.json()["csrf_token"]},
    )
    assert missing_origin.status_code == 403
    assert _error_code(missing_origin) == "ORIGIN_FORBIDDEN"

    missing_csrf = await auth_env.client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "http://test"},
    )
    assert missing_csrf.status_code == 403
    assert _error_code(missing_csrf) == "CSRF_INVALID"

    assert (await auth_env.client.get("/api/v1/auth/me")).status_code == 200


async def test_credentials_tokens_and_email_are_not_logged(
    auth_env: AuthTestEnvironment,
    caplog: pytest.LogCaptureFixture,
) -> None:
    email = "employee@ix-demo.test"
    password = DEMO_PASSWORD
    caplog.clear()

    response = await _login(auth_env.client, email=email, password=password)
    assert response.status_code == 200
    raw_session = auth_env.client.cookies.get("ix_session")
    raw_csrf = response.json()["csrf_token"]
    captured = caplog.text

    assert email not in captured
    assert password not in captured
    assert raw_session not in captured
    assert raw_csrf not in captured


async def test_login_success_resets_failure_counter(
    auth_env: AuthTestEnvironment,
) -> None:
    assert (await _login(auth_env.client, password="WrongPassword!")).status_code == 401
    assert (await _login(auth_env.client)).status_code == 200

    async with auth_env.session_factory() as session:
        failure_count = await session.scalar(select(func.sum(AuthRateLimit.failure_count)))
    assert failure_count == 0
