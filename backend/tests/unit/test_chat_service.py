import uuid

from app.clients.llm_client import NO_ANSWER_TEXT
from app.services.chat_service import ChatService
from app.services.retrieval_service import RetrievedChunk


def test_citations_are_deduplicated_by_document_and_page() -> None:
    document_id = uuid.uuid4()
    sources = (
        _source(document_id, page=2, chunk_index=4),
        _source(document_id, page=3, chunk_index=7),
        _source(document_id, page=2, chunk_index=5),
    )

    answer, citations = ChatService._normalize_citations(
        "First claim [1]. Same page [3]. Other page [2].",
        sources=sources,
        cited_indexes=[1, 3, 2],
    )

    assert answer == (
        "First claim [1]. Same page [1]. Other page [2]."
    )
    assert [citation.index for citation in citations] == [1, 2]
    assert [citation.page_number for citation in citations] == [2, 3]


def test_missing_citations_do_not_fall_back_to_all_sources() -> None:
    assert ChatService._cited_indexes(
        "An unsupported answer without citations.",
        source_count=3,
    ) == []
    assert ChatService._cited_indexes(
        NO_ANSWER_TEXT,
        source_count=3,
    ) == []


def _source(
    document_id: uuid.UUID,
    *,
    page: int,
    chunk_index: int,
) -> RetrievedChunk:
    return RetrievedChunk(
        document_id=document_id,
        filename="handbook.pdf",
        page_number=page,
        text=f"Evidence on page {page}, chunk {chunk_index}.",
        score=1.0,
        chunk_index=chunk_index,
    )
