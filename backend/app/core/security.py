import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from jwt import InvalidTokenError
from pwdlib import PasswordHash

from app.core.config import get_settings

password_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(
    password: str,
    hashed_password: str,
) -> bool:
    return password_hasher.verify(
        password,
        hashed_password,
    )


def create_access_token(subject: str) -> str:
    settings = get_settings()
    now = datetime.now(UTC)

    payload = {
        "sub": subject,
        "type": "access",
        "iat": now,
        "exp": now
        + timedelta(
            minutes=settings.access_token_expire_minutes,
        ),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> str | None:
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except InvalidTokenError:
        return None

    if payload.get("type") != "access":
        return None

    subject = payload.get("sub")

    if not isinstance(subject, str):
        return None

    return subject


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8"),
    ).hexdigest()

def generate_guest_token() -> str:
    return secrets.token_urlsafe(48)


def hash_guest_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8"),
    ).hexdigest()


def create_guest_identity_hash(
    *,
    ip_address: str,
    user_agent: str | None,
    accept_language: str | None,
) -> str:
    settings = get_settings()

    identity_key = hmac.new(
        settings.jwt_secret_key.encode("utf-8"),
        b"docally-guest-identity-key-v1",
        hashlib.sha256,
    ).digest()

    normalized_identity = "\n".join(
        [
            "docally-guest-identity-v1",
            ip_address.strip(),
            (user_agent or "").strip().lower(),
            (accept_language or "").strip().lower(),
        ]
    )

    return hmac.new(
        identity_key,
        normalized_identity.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()