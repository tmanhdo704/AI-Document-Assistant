"""Grounded question-answering orchestration."""

import re

from sqlalchemy.orm import Session

from app.clients.llm_client import (
    NO_ANSWER_TEXT,
    LLMClient,
)
from app.core.exceptions import ApplicationError
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.schemas.chat import (
    AnswerResponse,
    CitationResponse,
)
from app.services.document_service import DocumentOwner
from app.services.guest_service import GuestService
from app.services.retrieval_service import (
    RetrievedChunk,
    VectorRetrievalService,
)

CITATION_PATTERN = re.compile(r"\[(\d+)]")
DOCUMENT_CLARIFICATION_TEXT = (
    "Bạn đã tải lên nhiều tài liệu. Vui lòng nêu tên tài liệu cần hỏi "
    "hoặc hỏi về tất cả tài liệu."
)


class ChatService:
    def __init__(
        self,
        db: Session,
        llm_client: LLMClient,
        retrieval_service: VectorRetrievalService | None = None,
    ) -> None:
        self.db = db
        self.llm_client = llm_client
        self.retrieval_service = retrieval_service
        self.documents = DocumentRepository(db)

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
        questions_remaining: int | None = None

        if owner.guest_session_id is not None:
            if guest_token is None:
                raise ApplicationError(
                    "INVALID_GUEST_SESSION",
                    "Guest session cookie is missing.",
                    status_code=401,
                )

            guest_service = GuestService(self.db)
            usage = guest_service.get_usage(guest_token)
            questions_remaining = usage.questions_remaining

            if usage.questions_remaining == 0:
                raise ApplicationError(
                    "GUEST_QUESTION_LIMIT_REACHED",
                    "Guest question limit has been reached.",
                    status_code=403,
                )

        retrieval_service = (
            self.retrieval_service
            or VectorRetrievalService()
        )

        if retrieval_service.requires_document_clarification(
            normalized_question,
            document_count=len(ready_documents),
        ):
            return AnswerResponse(
                answer=DOCUMENT_CLARIFICATION_TEXT,
                citations=[],
                questions_remaining=questions_remaining,
            )

        sources = retrieval_service.retrieve(
            normalized_question,
            user_id=owner.user_id,
            guest_session_id=owner.guest_session_id,
        )

        llm_answer = self.llm_client.answer(
            question=normalized_question,
            sources=sources,
        )

        if guest_service is not None and guest_token is not None:
            usage = guest_service.consume_question(guest_token)
            questions_remaining = usage.questions_remaining

        if not llm_answer.answerable:
            answer_text = NO_ANSWER_TEXT
            citations: list[CitationResponse] = []
        else:
            cited_indexes = (
                list(llm_answer.cited_indexes)
                if llm_answer.cited_indexes
                else self._cited_indexes(
                    llm_answer.text,
                    len(sources),
                )
            )
            answer_text, citations = self._normalize_citations(
                llm_answer.text,
                sources=sources,
                cited_indexes=cited_indexes,
            )

            if not citations:
                answer_text = NO_ANSWER_TEXT

        return AnswerResponse(
            answer=answer_text,
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

    @staticmethod
    def _cited_indexes(answer: str, source_count: int) -> list[int]:
        if answer.strip() == NO_ANSWER_TEXT:
            return []

        indexes: list[int] = []

        for match in CITATION_PATTERN.findall(answer):
            index = int(match)

            if (
                1 <= index <= source_count
                and index not in indexes
            ):
                indexes.append(index)

        return indexes

    @classmethod
    def _normalize_citations(
        cls,
        answer: str,
        *,
        sources: tuple[RetrievedChunk, ...],
        cited_indexes: list[int],
    ) -> tuple[str, list[CitationResponse]]:
        source_to_display: dict[int, int] = {}
        page_to_display: dict[tuple[object, int], int] = {}
        citations: list[CitationResponse] = []

        for source_index in cited_indexes:
            if not 1 <= source_index <= len(sources):
                continue

            source = sources[source_index - 1]
            page_key = (
                source.document_id,
                source.page_number,
            )
            display_index = page_to_display.get(page_key)

            if display_index is None:
                display_index = len(citations) + 1
                page_to_display[page_key] = display_index
                citations.append(
                    CitationResponse(
                        index=display_index,
                        document_id=source.document_id,
                        filename=source.filename,
                        page_number=source.page_number,
                        excerpt=cls._excerpt(source.text),
                    ),
                )

            source_to_display[source_index] = display_index

        def replace_citation(match: re.Match[str]) -> str:
            source_index = int(match.group(1))
            display_index = source_to_display.get(source_index)
            return (
                f"[{display_index}]"
                if display_index is not None
                else ""
            )

        normalized_answer = CITATION_PATTERN.sub(
            replace_citation,
            answer,
        ).strip()

        return normalized_answer, citations

    @staticmethod
    def _excerpt(text: str, limit: int = 280) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "…"
