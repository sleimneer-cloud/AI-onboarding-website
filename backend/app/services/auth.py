from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.core.errors import ApiProblem
from app.db.session import transaction
from app.models.auth import AuthRateLimit, AuthSession, User
from app.models.enums import UserRole
from app.security.passwords import PasswordManager
from app.security.tokens import (
    generate_opaque_token,
    hash_opaque_token,
    rate_limit_subject_hash,
    tokens_match,
)


def normalize_email(email: str) -> str:
    return email.strip().lower()


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    name: str
    email: str
    role: UserRole
    is_active: bool


@dataclass(frozen=True)
class AuthContext:
    session_id: UUID
    user: AuthenticatedUser
    csrf_token_hash: str
    expires_at: datetime
    revoked_at: datetime | None = None


@dataclass(frozen=True)
class LoginResult:
    user: AuthenticatedUser
    raw_session_token: str
    raw_csrf_token: str
    expires_at: datetime


class AuthService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        password_manager: PasswordManager,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._settings = settings
        self._password_manager = password_manager
        self._now = now or (lambda: datetime.now(UTC))

    async def login(
        self,
        *,
        email: str,
        password: str,
        client_address: str,
    ) -> LoginResult:
        normalized_email = normalize_email(email)
        subject_hash = self._rate_limit_subject(normalized_email, client_address)

        try:
            retry_after = await self._check_login_allowed(subject_hash)
            if retry_after is not None:
                self._raise_rate_limited(retry_after)

            user = await self._read_user(normalized_email)
            password_valid = self._password_manager.verify_or_dummy(
                password,
                user.password_hash if user is not None else None,
            )
            if user is None or not password_valid:
                retry_after = await self._record_login_failure(subject_hash)
                if retry_after is not None:
                    self._raise_rate_limited(retry_after)
                raise ApiProblem(
                    status_code=401,
                    code="INVALID_CREDENTIALS",
                    message="이메일 또는 비밀번호를 확인해 주세요.",
                )

            if not user.is_active:
                retry_after = await self._record_login_failure(subject_hash)
                if retry_after is not None:
                    self._raise_rate_limited(retry_after)
                raise ApiProblem(
                    status_code=403,
                    code="USER_INACTIVE",
                    message="사용할 수 없는 계정입니다.",
                )

            result, retry_after = await self._create_session(user, subject_hash)
            if retry_after is not None:
                self._raise_rate_limited(retry_after)
            assert result is not None
            return result
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def authenticate(self, raw_session_token: str | None) -> AuthContext:
        if not raw_session_token:
            self._raise_auth_required()

        token_hash = hash_opaque_token(raw_session_token)
        now = self._utc_now()
        try:
            async with transaction(self._session_factory) as session:
                row = (
                    await session.execute(
                        select(AuthSession, User)
                        .join(User, User.id == AuthSession.user_id)
                        .where(AuthSession.token_hash == token_hash)
                        .with_for_update(of=AuthSession)
                    )
                ).one_or_none()
                if row is None:
                    self._raise_auth_required()

                auth_session, user = row
                if auth_session.expires_at <= now:
                    self._raise_session_expired()
                if auth_session.revoked_at is not None or not user.is_active:
                    self._raise_auth_required()

                auth_session.last_seen_at = now
                return AuthContext(
                    session_id=auth_session.id,
                    user=self._snapshot_user(user),
                    csrf_token_hash=auth_session.csrf_token_hash,
                    expires_at=auth_session.expires_at,
                )
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def rotate_csrf(self, context: AuthContext) -> str:
        raw_csrf_token = generate_opaque_token()
        csrf_token_hash = hash_opaque_token(raw_csrf_token)
        now = self._utc_now()
        try:
            async with transaction(self._session_factory) as session:
                auth_session = (
                    await session.execute(
                        select(AuthSession)
                        .where(AuthSession.id == context.session_id)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if auth_session is None or auth_session.revoked_at is not None:
                    self._raise_auth_required()
                if auth_session.expires_at <= now:
                    self._raise_session_expired()
                auth_session.csrf_token_hash = csrf_token_hash
                auth_session.last_seen_at = now
            return raw_csrf_token
        except SQLAlchemyError:
            self._raise_database_unavailable()

    async def logout(
        self,
        *,
        raw_session_token: str | None,
        raw_csrf_token: str | None,
    ) -> None:
        if not raw_session_token:
            self._raise_auth_required()
        token_hash = hash_opaque_token(raw_session_token)
        now = self._utc_now()
        try:
            async with transaction(self._session_factory) as session:
                auth_session = (
                    await session.execute(
                        select(AuthSession)
                        .where(AuthSession.token_hash == token_hash)
                        .with_for_update()
                    )
                ).scalar_one_or_none()
                if auth_session is None:
                    self._raise_auth_required()
                if auth_session.expires_at <= now:
                    self._raise_session_expired()
                self.enforce_csrf_hash(auth_session.csrf_token_hash, raw_csrf_token)
                if auth_session.revoked_at is None:
                    auth_session.revoked_at = now
        except SQLAlchemyError:
            self._raise_database_unavailable()

    @staticmethod
    def enforce_csrf_hash(expected_hash: str, raw_csrf_token: str | None) -> None:
        if raw_csrf_token is None or not tokens_match(raw_csrf_token, expected_hash):
            raise ApiProblem(
                status_code=403,
                code="CSRF_INVALID",
                message="CSRF 토큰을 확인해 주세요.",
            )

    def _rate_limit_subject(self, normalized_email: str, client_address: str) -> str:
        if self._settings.session_secret is None:
            raise ApiProblem(
                status_code=500,
                code="INTERNAL_ERROR",
                message="서버 설정을 확인해 주세요.",
            )
        return rate_limit_subject_hash(
            normalized_email=normalized_email,
            client_address=client_address,
            secret=self._settings.session_secret.get_secret_value(),
        )

    async def _read_user(self, normalized_email: str) -> User | None:
        async with self._session_factory() as session:
            return (
                await session.execute(
                    select(User).where(User.normalized_email == normalized_email)
                )
            ).scalar_one_or_none()

    async def _check_login_allowed(self, subject_hash: str) -> int | None:
        now = self._utc_now()
        retry_after: int | None = None
        async with transaction(self._session_factory) as session:
            record = await self._locked_rate_limit(session, subject_hash)
            if record is None:
                return None
            self._normalize_rate_limit_window(record, now)
            if record.blocked_until is not None and record.blocked_until > now:
                retry_after = self._retry_after_seconds(record.blocked_until, now)
        return retry_after

    async def _record_login_failure(self, subject_hash: str) -> int | None:
        now = self._utc_now()
        retry_after: int | None = None
        async with transaction(self._session_factory) as session:
            await session.execute(
                postgresql_insert(AuthRateLimit)
                .values(
                    subject_hash=subject_hash,
                    window_started_at=now,
                    failure_count=0,
                    updated_at=now,
                )
                .on_conflict_do_nothing(index_elements=[AuthRateLimit.subject_hash])
            )
            record = await self._locked_rate_limit(session, subject_hash)
            assert record is not None
            self._normalize_rate_limit_window(record, now)
            if record.blocked_until is not None and record.blocked_until > now:
                retry_after = self._retry_after_seconds(record.blocked_until, now)
            else:
                record.failure_count += 1
                record.updated_at = now
                if record.failure_count > self._settings.login_rate_limit_max_failures:
                    record.blocked_until = now + timedelta(
                        seconds=self._settings.login_rate_limit_block_seconds
                    )
                    retry_after = self._settings.login_rate_limit_block_seconds
        return retry_after

    async def _create_session(
        self,
        user: User,
        subject_hash: str,
    ) -> tuple[LoginResult | None, int | None]:
        now = self._utc_now()
        raw_session_token = generate_opaque_token()
        raw_csrf_token = generate_opaque_token()
        expires_at = now + timedelta(seconds=self._settings.session_ttl_seconds)
        retry_after: int | None = None

        async with transaction(self._session_factory) as session:
            rate_limit = await self._locked_rate_limit(session, subject_hash)
            if rate_limit is not None:
                self._normalize_rate_limit_window(rate_limit, now)
                if rate_limit.blocked_until is not None and rate_limit.blocked_until > now:
                    retry_after = self._retry_after_seconds(rate_limit.blocked_until, now)
                else:
                    rate_limit.window_started_at = now
                    rate_limit.failure_count = 0
                    rate_limit.blocked_until = None
                    rate_limit.updated_at = now

            if retry_after is None:
                session.add(
                    AuthSession(
                        user_id=user.id,
                        token_hash=hash_opaque_token(raw_session_token),
                        csrf_token_hash=hash_opaque_token(raw_csrf_token),
                        expires_at=expires_at,
                        last_seen_at=now,
                    )
                )

        if retry_after is not None:
            return None, retry_after
        return (
            LoginResult(
                user=self._snapshot_user(user),
                raw_session_token=raw_session_token,
                raw_csrf_token=raw_csrf_token,
                expires_at=expires_at,
            ),
            None,
        )

    async def _locked_rate_limit(
        self,
        session: AsyncSession,
        subject_hash: str,
    ) -> AuthRateLimit | None:
        return (
            await session.execute(
                select(AuthRateLimit)
                .where(AuthRateLimit.subject_hash == subject_hash)
                .with_for_update()
            )
        ).scalar_one_or_none()

    def _normalize_rate_limit_window(
        self,
        record: AuthRateLimit,
        now: datetime,
    ) -> None:
        window_ends_at = record.window_started_at + timedelta(
            seconds=self._settings.login_rate_limit_window_seconds
        )
        if record.blocked_until is not None and record.blocked_until <= now:
            record.blocked_until = None
        if window_ends_at <= now and record.blocked_until is None:
            record.window_started_at = now
            record.failure_count = 0
            record.updated_at = now

    @staticmethod
    def _snapshot_user(user: User) -> AuthenticatedUser:
        return AuthenticatedUser(
            id=user.id,
            name=user.name,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
        )

    def _utc_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("AuthService clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    @staticmethod
    def _retry_after_seconds(blocked_until: datetime, now: datetime) -> int:
        return max(1, math.ceil((blocked_until - now).total_seconds()))

    @staticmethod
    def _raise_rate_limited(retry_after: int) -> None:
        raise ApiProblem(
            status_code=429,
            code="LOGIN_RATE_LIMITED",
            message="로그인 요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.",
            headers={"Retry-After": str(retry_after)},
        )

    @staticmethod
    def _raise_auth_required() -> None:
        raise ApiProblem(
            status_code=401,
            code="AUTH_REQUIRED",
            message="로그인이 필요합니다.",
        )

    @staticmethod
    def _raise_session_expired() -> None:
        raise ApiProblem(
            status_code=401,
            code="SESSION_EXPIRED",
            message="세션이 만료되었습니다. 다시 로그인해 주세요.",
        )

    @staticmethod
    def _raise_database_unavailable() -> None:
        raise ApiProblem(
            status_code=503,
            code="DATABASE_UNAVAILABLE",
            message="데이터베이스를 사용할 수 없습니다.",
        ) from None
