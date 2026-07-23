import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        *,
        user_id: uuid.UUID | None,
        guest_session_id: uuid.UUID | None,
        original_filename: str,
        storage_key: str,
        content_type: str,
        size_bytes: int,
        file_hash: str,
    ) -> Document:
        document = Document(
            user_id=user_id,
            guest_session_id=guest_session_id,
            original_filename=original_filename,
            storage_key=storage_key,
            content_type=content_type,
            size_bytes=size_bytes,
            file_hash=file_hash,
            status="PENDING",
        )

        self.db.add(document)
        self.db.flush()

        return document

    def get_by_id(
        self,
        document_id: uuid.UUID,
    ) -> Document | None:
        return self.db.get(
            Document,
            document_id,
        )

    def get_by_id_for_user(
        self,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.user_id == user_id,
        )

        return self.db.scalar(statement)

    def get_by_id_for_guest(
        self,
        document_id: uuid.UUID,
        guest_session_id: uuid.UUID,
    ) -> Document | None:
        statement = select(Document).where(
            Document.id == document_id,
            Document.guest_session_id == guest_session_id,
        )

        return self.db.scalar(statement)

    def list_for_user(
        self,
        user_id: uuid.UUID,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc())
        )

        return list(self.db.scalars(statement))

    def list_for_guest(
        self,
        guest_session_id: uuid.UUID,
    ) -> list[Document]:
        statement = (
            select(Document)
            .where(
                Document.guest_session_id == guest_session_id,
            )
            .order_by(Document.created_at.desc())
        )

        return list(self.db.scalars(statement))

    def count_for_user(
        self,
        user_id: uuid.UUID,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id)
        )

        return self.db.scalar(statement) or 0

    def count_for_guest(
        self,
        guest_session_id: uuid.UUID,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(Document)
            .where(
                Document.guest_session_id == guest_session_id,
            )
        )

        return self.db.scalar(statement) or 0

    def update_status(
        self,
        document: Document,
        *,
        status: str,
        page_count: int | None = None,
        error_message: str | None = None,
    ) -> Document:
        document.status = status
        document.page_count = page_count
        document.error_message = error_message

        self.db.flush()

        return document
