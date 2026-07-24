"""Grounded question-answering orchestration."""

import re

from sqlalchemy.orm import Session

from app.clients.llm_client import LLMClient
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.chat import (
    AnswerResponse,
    CitationResponse,
)
from app.services.chunking_service import ChunkingService
from app.services.document_service import DocumentOwner
from app.services.extraction_service import ExtractionService
from app.services.guest_service import GuestService
from app.services.retrieval_service import RetrievalService, SourceChunk
from app.utils.file import read_document_file

NO_ANSWER_TEXT = (
    "Tôi không tìm thấy đủ thông tin trong tài liệu để trả lời câu hỏi này."
)
CITATION_PATTERN = re.compile(r"\[(\d+)]")


class ChatService:
    def __init__(
        self,
        db: Session,
        llm_client: LLMClient,
    ) -> None:
        self.db = db
        self.llm_client = llm_client
        self.documents = DocumentRepository(db)
        self.settings = get_settings()

    def ask(
        self,
        *,
        owner: DocumentOwner,
        question: str,
        guest_token: str | None,
    ) -> AnswerResponse:
        normalized_question = question.strip()
        documents = self._list_owned_documents(owner)
        ready_documents = [
            document
            for document in documents
            if document.status == "EXTRACTED"
        ]

        if not ready_documents:
            raise ApplicationError(
                "DOCUMENT_REQUIRED",
                "Upload at least one readable document before asking.",
                status_code=400,
            )

        guest_service: GuestService | None = None

        if owner.guest_session_id is not None:
            if guest_token is None:
                raise ApplicationError(
                    "INVALID_GUEST_SESSION",
                    "Guest session cookie is missing.",
                    status_code=401,
                )

            guest_service = GuestService(self.db)
            usage = guest_service.get_usage(guest_token)
            if usage.questions_remaining == 0:
                raise ApplicationError(
                    "GUEST_QUESTION_LIMIT_REACHED",
                    "Guest question limit has been reached.",
                    status_code=403,
                )

        chunks = self._load_source_chunks(ready_documents)
        sources = RetrievalService().retrieve(
            normalized_question,
            chunks,
        )
        llm_answer = self.llm_client.answer(
            question=normalized_question,
            sources=sources,
        )

        questions_remaining: int | None = None
        if guest_service is not None and guest_token is not None:
            usage = guest_service.consume_question(guest_token)
            questions_remaining = usage.questions_remaining

        cited_indexes = self._cited_indexes(llm_answer.text, len(sources))
        citations = [
            CitationResponse(
                index=index,
                document_id=sources[index - 1].document_id,
                filename=sources[index - 1].filename,
                page_number=sources[index - 1].page_number,
                excerpt=self._excerpt(sources[index - 1].text),
            )
            for index in cited_indexes
        ]

        return AnswerResponse(
            answer=llm_answer.text,
            citations=citations,
            questions_remaining=questions_remaining,
        )

    def _list_owned_documents(
        self,
        owner: DocumentOwner,
    ) -> list[Document]:
        if owner.user_id is not None:
            return self.documents.list_for_user(
                owner.user_id,
            )

        if owner.guest_session_id is None:
            raise ValueError("Guest owner id is missing.")

        return self.documents.list_for_guest(owner.guest_session_id)

    def _load_source_chunks(
        self,
        documents: list[Document],
    ) -> tuple[SourceChunk, ...]:
        source_chunks: list[SourceChunk] = []

        for document in documents:
            content = read_document_file(
                upload_directory=self.settings.document_upload_directory,
                storage_key=document.storage_key,
            )
            extracted = ExtractionService().extract_pdf(content)
            document_chunks = ChunkingService().chunk_pages(
                extracted.pages,
            )
            source_chunks.extend(
                SourceChunk(
                    document_id=document.id,
                    filename=document.original_filename,
                    page_number=chunk.page_number,
                    text=chunk.text,
                )
                for chunk in document_chunks
            )

        return tuple(source_chunks)

    @staticmethod
    def _cited_indexes(answer: str, source_count: int) -> list[int]:
        if answer.strip() == NO_ANSWER_TEXT:
            return []

        indexes = {
            int(match)
            for match in CITATION_PATTERN.findall(answer)
            if 1 <= int(match) <= source_count
        }

        if not indexes:
            indexes = set(range(1, source_count + 1))

        return sorted(indexes)

    @staticmethod
    def _excerpt(text: str, limit: int = 280) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"
