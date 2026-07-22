import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth_session import AuthSession


class AuthSessionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: uuid.UUID,
        token_hash: str,
        expires_at: datetime,
    ) -> AuthSession:
        auth_session = AuthSession(
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )

        self.db.add(auth_session)
        self.db.flush()

        return auth_session

    def get_active_by_token_hash(
        self,
        token_hash: str,
        now: datetime,
    ) -> AuthSession | None:
        statement = (
            select(AuthSession)
            .where(
                AuthSession.token_hash == token_hash,
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
            .with_for_update()
        )

        return self.db.scalar(statement)

    def revoke(
        self,
        auth_session: AuthSession,
        revoked_at: datetime,
    ) -> None:
        auth_session.revoked_at = revoked_at
        self.db.flush()