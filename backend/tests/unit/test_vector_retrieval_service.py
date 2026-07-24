import uuid
from collections import Counter
from dataclasses import dataclass

from app.services.retrieval_service import (
    RetrievedChunk,
    VectorRetrievalService,
)


@dataclass
class FakePoint:
    payload: dict[str, object]
    score: float | None = None


class FakeEmbeddingClient:
    def __init__(self) -> None:
        self.queries: list[str] = []

    def embed_query(self, query: str) -> tuple[float, ...]:
        self.queries.append(query)
        return (0.0,) * 384


class FakeQdrantClient:
    def __init__(
        self,
        *,
        candidates: tuple[FakePoint, ...] = (),
        stored_points: tuple[FakePoint, ...] = (),
        openings: tuple[FakePoint, ...] = (),
    ) -> None:
        self.candidates = candidates
        self.openings = openings
        self.search_limit: int | None = None
        self.requested_references: tuple[
            tuple[uuid.UUID, int],
            ...,
        ] = ()
        self.points_by_reference = {
            (
                uuid.UUID(str(point.payload["document_id"])),
                int(point.payload["chunk_index"]),
            ): point
            for point in stored_points
        }

    def search(self, *, limit: int, **kwargs) -> tuple[FakePoint, ...]:
        self.search_limit = limit
        return self.candidates[:limit]

    def get_chunks(
        self,
        *,
        references,
        **kwargs,
    ) -> tuple[FakePoint, ...]:
        self.requested_references = tuple(references)
        return tuple(
            self.points_by_reference[reference]
            for reference in dict.fromkeys(references)
            if reference in self.points_by_reference
        )

    def get_opening_chunks(
        self,
        *,
        limit: int,
        **kwargs,
    ) -> tuple[FakePoint, ...]:
        return self.openings[:limit]


def test_diverse_selection_limits_duplicate_pages_and_documents() -> None:
    first_document_id = uuid.uuid4()
    second_document_id = uuid.uuid4()
    candidates = tuple(
        RetrievedChunk(
            document_id=(
                first_document_id
                if index < 6
                else second_document_id
            ),
            filename="document.pdf",
            page_number=1 if index < 5 else index,
            text=f"Unique chunk {index}",
            score=1.0 - index / 100,
            chunk_index=index,
        )
        for index in range(8)
    )

    selected = VectorRetrievalService._select_diverse_chunks(
        candidates,
        limit=8,
    )
    page_counts = Counter(
        (chunk.document_id, chunk.page_number)
        for chunk in selected
    )
    document_counts = Counter(
        chunk.document_id
        for chunk in selected
    )

    assert max(page_counts.values()) <= 2
    assert max(document_counts.values()) <= 4
    assert {chunk.document_id for chunk in selected} == {
        first_document_id,
        second_document_id,
    }


def test_document_filter_removes_weak_unrelated_document() -> None:
    relevant_document_id = uuid.uuid4()
    unrelated_document_id = uuid.uuid4()
    candidates = (
        RetrievedChunk(
            document_id=relevant_document_id,
            filename="tax-form.pdf",
            page_number=1,
            text="Backup withholding applies in these cases.",
            score=0.90,
        ),
        RetrievedChunk(
            document_id=unrelated_document_id,
            filename="safe-primer.pdf",
            page_number=1,
            text="Startup financing.",
            score=0.78,
        ),
    )

    filtered = VectorRetrievalService._filter_relevant_documents(
        "Khi nào áp dụng backup withholding?",
        candidates,
    )

    assert {
        chunk.document_id
        for chunk in filtered
    } == {relevant_document_id}


def test_document_filter_keeps_explicitly_named_document() -> None:
    first_document_id = uuid.uuid4()
    second_document_id = uuid.uuid4()
    candidates = (
        RetrievedChunk(
            document_id=first_document_id,
            filename="IRS Form W-9.pdf",
            page_number=1,
            text="Tax form.",
            score=0.90,
        ),
        RetrievedChunk(
            document_id=second_document_id,
            filename="Post-money SAFE Primer.pdf",
            page_number=1,
            text="Startup financing.",
            score=0.78,
        ),
    )

    filtered = VectorRetrievalService._filter_relevant_documents(
        "Compare Form W-9 with the Post-money SAFE.",
        candidates,
    )

    assert {
        chunk.document_id
        for chunk in filtered
    } == {
        first_document_id,
        second_document_id,
    }


def test_vector_retrieval_uses_candidates_and_neighbors_from_each_document(
) -> None:
    first_document_id = uuid.uuid4()
    second_document_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    candidates = (
        _point(first_document_id, 5, page=2, score=0.90),
        _point(first_document_id, 12, page=4, score=0.89),
        _point(first_document_id, 20, page=6, score=0.88),
        _point(second_document_id, 2, page=1, score=0.87),
    )
    stored_points = tuple(
        _point(document_id, index, page=page)
        for document_id, center, page in (
            (first_document_id, 5, 2),
            (second_document_id, 2, 1),
            (first_document_id, 12, 4),
        )
        for index in range(center - 1, center + 2)
    )
    embedding = FakeEmbeddingClient()
    qdrant = FakeQdrantClient(
        candidates=candidates,
        stored_points=stored_points,
    )
    service = VectorRetrievalService(
        embedding_client=embedding,
        qdrant_client=qdrant,
    )

    results = service.retrieve(
        "specific policy question",
        user_id=owner_id,
        limit=8,
    )

    assert qdrant.search_limit == 24
    assert embedding.queries == ["specific policy question"]
    assert (first_document_id, 4) in qdrant.requested_references
    assert (second_document_id, 1) in qdrant.requested_references
    assert {result.document_id for result in results} == {
        first_document_id,
        second_document_id,
    }
    assert len(results) <= 8


def test_overview_question_uses_opening_and_next_chunk() -> None:
    document_id = uuid.uuid4()
    owner_id = uuid.uuid4()
    opening = _point(document_id, 0, page=1)
    next_chunk = _point(document_id, 1, page=1)
    embedding = FakeEmbeddingClient()
    qdrant = FakeQdrantClient(
        openings=(opening,),
        stored_points=(next_chunk,),
    )
    service = VectorRetrievalService(
        embedding_client=embedding,
        qdrant_client=qdrant,
    )

    results = service.retrieve(
        "Tài liệu này nói về vấn đề gì?",
        user_id=owner_id,
        limit=8,
    )

    assert embedding.queries == []
    assert qdrant.search_limit is None
    assert [result.chunk_index for result in results] == [0, 1]


def test_singular_overview_requires_clarification_for_multiple_documents(
) -> None:
    assert VectorRetrievalService.requires_document_clarification(
        "Tài liệu này nói về vấn đề gì?",
        document_count=2,
    )
    assert not VectorRetrievalService.requires_document_clarification(
        "Các tài liệu này nói về vấn đề gì?",
        document_count=2,
    )
    assert not VectorRetrievalService.requires_document_clarification(
        "Mục đích của Form W-9 là gì?",
        document_count=2,
    )
    assert not VectorRetrievalService.requires_document_clarification(
        "Tài liệu này nói về vấn đề gì?",
        document_count=1,
    )


def _point(
    document_id: uuid.UUID,
    chunk_index: int,
    *,
    page: int,
    score: float | None = None,
) -> FakePoint:
    return FakePoint(
        payload={
            "owner_type": "user",
            "owner_id": str(uuid.uuid4()),
            "document_id": str(document_id),
            "filename": f"{document_id}.pdf",
            "page_number": page,
            "chunk_index": chunk_index,
            "text": f"Document text for chunk {chunk_index}.",
        },
        score=score,
    )
