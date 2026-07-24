import uuid
from dataclasses import dataclass

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.repositories.document_repository import DocumentRepository
from app.repositories.guest_repository import GuestRepository
from app.repositories.user_repository import UserRepository
from app.schemas.document import DocumentResponse
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import ExtractionService
from app.utils.file import (
    delete_document_file,
    generate_document_storage_key,
    save_document_file,
    validate_pdf_upload,
)


@dataclass(frozen=True)
class DocumentOwner:
    user_id: uuid.UUID | None = None
    guest_session_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        has_user = self.user_id is not None
        has_guest = self.guest_session_id is not None

        if has_user == has_guest:
            raise ValueError("Document must have exactly one owner.")


class DocumentService:
    def __init__(
        self,
        db: Session,
        embedding_service: EmbeddingService | None = None,
    ) -> None:
        self.db = db
        self.repository = DocumentRepository(db)
        self.settings = get_settings()
        self.embedding_service = embedding_service

    async def upload(
        self,
        upload: UploadFile,
        owner: DocumentOwner,
    ) -> DocumentResponse:
        validated_pdf = await validate_pdf_upload(
            upload,
            max_size_bytes=self.settings.document_max_size_bytes,
        )
        extracted_document = ExtractionService().extract_pdf(
            validated_pdf.content,
        )

        chunks = ChunkingService().chunk_pages(
            extracted_document.pages,
        )

        document_count, document_limit = self._lock_owner_and_count_documents(
            owner,
        )

        if document_count >= document_limit:
            self.db.rollback()
            raise ApplicationError(
                "DOCUMENT_LIMIT_REACHED",
                "Document limit has been reached.",
                status_code=403,
                details={
                    "document_count": document_count,
                    "document_limit": document_limit,
                },
            )

        storage_key = generate_document_storage_key()

        try:
            save_document_file(
                upload_directory=self.settings.document_upload_directory,
                storage_key=storage_key,
                content=validated_pdf.content,
            )

            document = self.repository.create(
                user_id=owner.user_id,
                guest_session_id=owner.guest_session_id,
                original_filename=validated_pdf.original_filename,
                storage_key=storage_key,
                content_type=validated_pdf.content_type,
                size_bytes=validated_pdf.size_bytes,
                file_hash=validated_pdf.file_hash,
            )

            embedding_service = (
                self.embedding_service
                or EmbeddingService()
            )

            embedding_service.index_document(
                document_id=document.id,
                filename=document.original_filename,
                chunks=chunks,
                user_id=document.user_id,
                guest_session_id=document.guest_session_id,
            )

            self.repository.update_status(
                document,
                status="EXTRACTED",
                page_count=extracted_document.page_count,
            )

            self.db.commit()
            self.db.refresh(document)
        except Exception:
            self.db.rollback()
            delete_document_file(
                upload_directory=self.settings.document_upload_directory,
                storage_key=storage_key,
            )
            raise

        return DocumentResponse.model_validate(document)

    def list_documents(
        self,
        owner: DocumentOwner,
    ) -> list[DocumentResponse]:
        if owner.user_id is not None:
            documents = self.repository.list_for_user(owner.user_id)
        else:
            if owner.guest_session_id is None:
                raise ValueError("Guest owner id is missing.")

            documents = self.repository.list_for_guest(
                owner.guest_session_id,
            )

        return [
            DocumentResponse.model_validate(document)
            for document in documents
        ]

    def _lock_owner_and_count_documents(
        self,
        owner: DocumentOwner,
    ) -> tuple[int, int]:
        if owner.user_id is not None:
            user = UserRepository(self.db).get_by_id(
                owner.user_id,
                for_update=True,
            )

            if user is None:
                raise ApplicationError(
                    "UNAUTHORIZED",
                    "Login session is invalid or expired.",
                    status_code=401,
                )

            return (
                self.repository.count_for_user(owner.user_id),
                self.settings.user_max_documents,
            )

        if owner.guest_session_id is None:
            raise ValueError("Guest owner id is missing.")

        guest_session = GuestRepository(self.db).get_by_id(
            owner.guest_session_id,
            for_update=True,
        )

        if guest_session is None:
            raise ApplicationError(
                "INVALID_GUEST_SESSION",
                "Guest session is invalid.",
                status_code=401,
            )

        return (
            self.repository.count_for_guest(owner.guest_session_id),
            self.settings.guest_max_documents,
        )
