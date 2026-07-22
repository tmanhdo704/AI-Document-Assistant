from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.guest_session import GuestSession


class GuestRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        token_hash: str,
        identity_hash: str,
    ) -> GuestSession:
        guest_session = GuestSession(
            token_hash=token_hash,
            identity_hash=identity_hash,
        )

        self.db.add(guest_session)
        self.db.flush()

        return guest_session

    def get_by_token_hash(
        self,
        token_hash: str,
        *,
        for_update: bool = False,
    ) -> GuestSession | None:
        statement = select(GuestSession).where(
            GuestSession.token_hash == token_hash,
        )

        if for_update:
            statement = statement.with_for_update()

        return self.db.scalar(statement)

    def get_by_identity_hash(
        self,
        identity_hash: str,
        *,
        for_update: bool = False,
    ) -> GuestSession | None:
        statement = select(GuestSession).where(
            GuestSession.identity_hash == identity_hash,
        )

        if for_update:
            statement = statement.with_for_update()

        return self.db.scalar(statement)

    def update_token_hash(
        self,
        guest_session: GuestSession,
        token_hash: str,
    ) -> None:
        guest_session.token_hash = token_hash
        self.db.flush()