import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def get_by_google_sub(
        self,
        google_sub: str,
    ) -> User | None:
        statement = select(User).where(
            User.google_sub == google_sub,
        )
        return self.db.scalar(statement)

    def create(
        self,
        *,
        email: str,
        password_hash: str,
        full_name: str | None,
    ) -> User:
        user = User(
            email=email,
            password_hash=password_hash,
            full_name=full_name,
        )

        self.db.add(user)
        self.db.flush()

        return user

    def create_google(
        self,
        *,
        email: str,
        google_sub: str,
        full_name: str | None,
    ) -> User:
        user = User(
            email=email,
            password_hash=None,
            full_name=full_name,
            auth_provider="GOOGLE",
            google_sub=google_sub,
        )

        self.db.add(user)
        self.db.flush()

        return user

    def link_google_identity(
        self,
        *,
        user: User,
        google_sub: str,
        full_name: str | None,
    ) -> User:
        user.google_sub = google_sub

        if user.full_name is None:
            user.full_name = full_name

        self.db.flush()

        return user
