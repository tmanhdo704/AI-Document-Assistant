"""Guest session lifecycle and usage-limit rules."""
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.core.security import (
    create_guest_identity_hash,
    generate_guest_token,
    hash_guest_token,
)
from app.models.guest_session import GuestSession
from app.repositories.guest_repository import GuestRepository
from app.schemas.guest import GuestUsageResponse


@dataclass(frozen=True)
class GuestSessionResult:
    response: GuestUsageResponse
    guest_token: str


class GuestService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repository = GuestRepository(db)
        self.settings = get_settings()

    def create_or_restore_session(
        self,
        *,
        guest_token: str | None,
        ip_address: str,
        user_agent: str | None,
        accept_language: str | None,
    ) -> GuestSessionResult:
        if guest_token:
            guest_session = self.repository.get_by_token_hash(
                hash_guest_token(guest_token),
            )

            if guest_session is not None:
                return self._build_result(
                    guest_session,
                    guest_token,
                )

        identity_hash = create_guest_identity_hash(
            ip_address=ip_address,
            user_agent=user_agent,
            accept_language=accept_language,
        )

        new_guest_token = generate_guest_token()
        new_token_hash = hash_guest_token(new_guest_token)

        guest_session = self.repository.get_by_identity_hash(
            identity_hash,
            for_update=True,
        )

        if guest_session is not None:
            self.repository.update_token_hash(
                guest_session,
                new_token_hash,
            )
            self.db.commit()
            self.db.refresh(guest_session)

            return self._build_result(
                guest_session,
                new_guest_token,
            )

        try:
            guest_session = self.repository.create(
                token_hash=new_token_hash,
                identity_hash=identity_hash,
            )
            self.db.commit()
            self.db.refresh(guest_session)
        except IntegrityError:
            self.db.rollback()

            guest_session = self.repository.get_by_identity_hash(
                identity_hash,
                for_update=True,
            )

            if guest_session is None:
                raise ApplicationError(
                    "GUEST_SESSION_UNAVAILABLE",
                    "Guest session could not be created.",
                    status_code=503,
                )

            self.repository.update_token_hash(
                guest_session,
                new_token_hash,
            )
            self.db.commit()
            self.db.refresh(guest_session)

        return self._build_result(
            guest_session,
            new_guest_token,
        )

    def get_usage(
        self,
        guest_token: str,
    ) -> GuestUsageResponse:
        guest_session = self._get_guest_session(
            guest_token,
        )
        return self._build_usage(guest_session)

    def consume_document(
        self,
        guest_token: str,
    ) -> GuestUsageResponse:
        guest_session = self._get_guest_session(
            guest_token,
            for_update=True,
        )

        if (
            guest_session.document_count
            >= self.settings.guest_max_documents
        ):
            self.db.rollback()
            raise ApplicationError(
                "GUEST_DOCUMENT_LIMIT_REACHED",
                "Guest document limit has been reached.",
                status_code=403,
            )

        guest_session.document_count += 1

        self.db.commit()
        self.db.refresh(guest_session)

        return self._build_usage(guest_session)

    def consume_question(
        self,
        guest_token: str,
    ) -> GuestUsageResponse:
        guest_session = self._get_guest_session(
            guest_token,
            for_update=True,
        )

        if (
            guest_session.question_count
            >= self.settings.guest_max_questions
        ):
            self.db.rollback()
            raise ApplicationError(
                "GUEST_QUESTION_LIMIT_REACHED",
                "Guest question limit has been reached.",
                status_code=403,
            )

        guest_session.question_count += 1

        self.db.commit()
        self.db.refresh(guest_session)

        return self._build_usage(guest_session)

    def _get_guest_session(
        self,
        guest_token: str,
        *,
        for_update: bool = False,
    ) -> GuestSession:
        guest_session = self.repository.get_by_token_hash(
            hash_guest_token(guest_token),
            for_update=for_update,
        )

        if guest_session is None:
            raise ApplicationError(
                "INVALID_GUEST_SESSION",
                "Guest session is invalid.",
                status_code=401,
            )

        return guest_session

    def _build_result(
        self,
        guest_session: GuestSession,
        guest_token: str,
    ) -> GuestSessionResult:
        return GuestSessionResult(
            response=self._build_usage(guest_session),
            guest_token=guest_token,
        )

    def _build_usage(
        self,
        guest_session: GuestSession,
    ) -> GuestUsageResponse:
        return GuestUsageResponse(
            question_count=guest_session.question_count,
            question_limit=self.settings.guest_max_questions,
            questions_remaining=max(
                self.settings.guest_max_questions
                - guest_session.question_count,
                0,
            ),
            document_count=guest_session.document_count,
            document_limit=self.settings.guest_max_documents,
            documents_remaining=max(
                self.settings.guest_max_documents
                - guest_session.document_count,
                0,
            ),
        )