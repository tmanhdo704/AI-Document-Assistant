import uuid

from app.services.chunking_service import ChunkingService
from app.services.extraction_service import ExtractedPage
from app.services.retrieval_service import RetrievalService, SourceChunk


def test_chunking_preserves_page_number_and_size() -> None:
    chunks = ChunkingService(
        chunk_size=30,
        overlap=5,
    ).chunk_pages(
        (
            ExtractedPage(
                page_number=7,
                text=(
                    "Alpha beta gamma delta epsilon zeta eta theta "
                    "iota kappa lambda."
                ),
            ),
        ),
    )

    assert len(chunks) > 1
    assert all(chunk.page_number == 7 for chunk in chunks)
    assert all(len(chunk.text) <= 30 for chunk in chunks)


def test_chunking_overlap_starts_with_complete_words() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel"

    chunks = ChunkingService(
        chunk_size=20,
        overlap=5,
    ).chunk_pages(
        (
            ExtractedPage(
                page_number=1,
                text=text,
            ),
        ),
    )

    source_words = set(text.split())
    chunk_first_words = {
        chunk.text.split(maxsplit=1)[0]
        for chunk in chunks
    }

    assert len(chunks) > 1
    assert chunk_first_words <= source_words
    assert all(len(chunk.text) <= 20 for chunk in chunks)


def test_chunking_overlap_keeps_all_source_words() -> None:
    text = "alpha bravo charlie delta echo foxtrot golf hotel"

    chunks = ChunkingService(
        chunk_size=20,
        overlap=5,
    ).chunk_pages(
        (
            ExtractedPage(
                page_number=1,
                text=text,
            ),
        ),
    )

    chunk_words = {
        word
        for chunk in chunks
        for word in chunk.text.split()
    }

    assert set(text.split()) <= chunk_words


def test_chunking_overlap_prefers_sentence_boundaries() -> None:
    text = (
        "First sentence contains alpha details. "
        "Second sentence contains beta details. "
        "Third sentence contains gamma details."
    )

    chunks = ChunkingService(
        chunk_size=70,
        overlap=20,
    ).chunk_pages(
        (
            ExtractedPage(
                page_number=1,
                text=text,
            ),
        ),
    )

    assert [chunk.text for chunk in chunks] == [
        "First sentence contains alpha details.",
        "Second sentence contains beta details.",
        "Third sentence contains gamma details.",
    ]


def test_retrieval_ranks_matching_chunk_first() -> None:
    page_chunks = ChunkingService().chunk_pages(
        (
            ExtractedPage(
                page_number=1,
                text="Chính sách làm việc từ xa áp dụng hai ngày mỗi tuần.",
            ),
            ExtractedPage(
                page_number=2,
                text="Nhân viên có mười hai ngày nghỉ phép mỗi năm.",
            ),
        ),
    )
    first_document_id = uuid.uuid4()
    second_document_id = uuid.uuid4()
    chunks = tuple(
        SourceChunk(
            document_id=(
                first_document_id
                if chunk.page_number == 1
                else second_document_id
            ),
            filename=(
                "remote-work.pdf"
                if chunk.page_number == 1
                else "leave-policy.pdf"
            ),
            page_number=chunk.page_number,
            text=chunk.text,
        )
        for chunk in page_chunks
    )

    result = RetrievalService().retrieve(
        "Có bao nhiêu ngày nghỉ phép?",
        chunks,
        limit=1,
    )

    assert len(result) == 1
    assert result[0].page_number == 2
    assert result[0].document_id == second_document_id
    assert result[0].filename == "leave-policy.pdf"
