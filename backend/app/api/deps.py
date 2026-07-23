import uuid
from collections.abc import Generator

from fastapi import Cookie, Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.security import decode_access_token, hash_guest_token
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories.guest_repository import GuestRepository
from app.repositories.user_repository import UserRepository
from app.services.document_service import DocumentOwner

bearer_scheme = HTTPBearer(auto_error=False)
GUEST_COOKIE_NAME = "docally_guest_token"


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme,
    ),
    db: Session = Depends(get_db),
) -> User | None:
    if credentials is None:
        return None

    subject = (
        decode_access_token(credentials.credentials)
        if credentials
        else None
    )

    try:
        user_id = uuid.UUID(subject) if subject else None
    except ValueError:
        user_id = None

    user = (
        UserRepository(db).get_by_id(user_id)
        if user_id
        else None
    )

    if user is None:
        raise ApplicationError(
            "UNAUTHORIZED",
            "Login session is invalid or expired.",
            status_code=401,
        )

    return user


def get_current_user(
    current_user: User | None = Depends(
        get_optional_current_user,
    ),
) -> User:
    if current_user is None:
        raise ApplicationError(
            "UNAUTHORIZED",
            "Login session is invalid or expired.",
            status_code=401,
        )

    return current_user


def get_document_owner(
    current_user: User | None = Depends(
        get_optional_current_user,
    ),
    guest_token: str | None = Cookie(
        default=None,
        alias=GUEST_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
) -> DocumentOwner:
    if current_user is not None:
        return DocumentOwner(user_id=current_user.id)

    if guest_token is None:
        raise ApplicationError(
            "DOCUMENT_OWNER_REQUIRED",
            "Login or start a guest session before uploading documents.",
            status_code=401,
        )

    guest_session = GuestRepository(db).get_by_token_hash(
        hash_guest_token(guest_token),
    )

    if guest_session is None:
        raise ApplicationError(
            "INVALID_GUEST_SESSION",
            "Guest session is invalid.",
            status_code=401,
        )

    return DocumentOwner(guest_session_id=guest_session.id)
