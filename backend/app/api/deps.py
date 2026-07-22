import uuid
from collections.abc import Generator

from fastapi import Depends
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.exceptions import ApplicationError
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme,
    ),
    db: Session = Depends(get_db),
) -> User:
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
