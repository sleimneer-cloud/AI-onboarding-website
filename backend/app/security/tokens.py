from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def hash_opaque_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def tokens_match(raw_token: str, expected_hash: str) -> bool:
    actual_hash = hash_opaque_token(raw_token)
    return hmac.compare_digest(actual_hash, expected_hash)


def rate_limit_subject_hash(
    *,
    normalized_email: str,
    client_address: str,
    secret: str,
) -> str:
    subject = f"ix-rate-limit-v1\0{normalized_email}\0{client_address}".encode()
    return hmac.new(secret.encode("utf-8"), subject, hashlib.sha256).hexdigest()
