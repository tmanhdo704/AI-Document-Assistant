"""Evaluate multi-document retrieval in an isolated Qdrant collection."""

import uuid
from collections import Counter
from pathlib import Path

from app.clients.embedding_client import EmbeddingClient
from app.clients.qdrant_client import QdrantVectorClient
from app.core.config import get_settings
from app.services.chunking_service import ChunkingService
from app.services.embedding_service import EmbeddingService
from app.services.extraction_service import ExtractionService
from app.services.retrieval_service import VectorRetrievalService

DOCUMENTS = (
    (
        "IRS Form W-9.pdf",
        Path(
            "/app/storage/uploads/documents/"
            "3c01dd85-3cfd-497c-8dc6-478133c5272d.pdf",
        ),
    ),
    (
        "Y Combinator Post-money SAFE Primer.pdf",
        Path(
            "/app/storage/uploads/documents/"
            "c283dd3b-ba11-499b-abc6-8111542fc770.pdf",
        ),
    ),
)
QUESTIONS = (
    (
        "Khi nào áp dụng backup withholding?",
        {"IRS Form W-9.pdf"},
    ),
    (
        "What is a post-money SAFE and how does it calculate ownership?",
        {"Y Combinator Post-money SAFE Primer.pdf"},
    ),
    (
        "So sánh mục đích của Form W-9 và Post-money SAFE.",
        {
            "IRS Form W-9.pdf",
            "Y Combinator Post-money SAFE Primer.pdf",
        },
    ),
    (
        "Các tài liệu này nói về vấn đề gì?",
        {
            "IRS Form W-9.pdf",
            "Y Combinator Post-money SAFE Primer.pdf",
        },
    ),
)


def main() -> None:
    collection_name = f"retrieval_eval_{uuid.uuid4().hex}"
    settings = get_settings().model_copy(
        update={
            "qdrant_collection_name": collection_name,
        },
    )
    qdrant = QdrantVectorClient(settings=settings)
    qdrant.ensure_collection()
    owner_id = uuid.uuid4()

    try:
        embedding_client = EmbeddingClient(settings=settings)
        embedding_service = EmbeddingService(
            embedding_client=embedding_client,
            qdrant_client=qdrant,
        )

        for filename, path in DOCUMENTS:
            extracted = ExtractionService().extract_pdf(
                path.read_bytes(),
            )
            chunks = ChunkingService().chunk_pages(
                extracted.pages,
            )
            embedding_service.index_document(
                document_id=uuid.uuid4(),
                filename=filename,
                chunks=chunks,
                user_id=owner_id,
            )

        retrieval = VectorRetrievalService(
            embedding_client=embedding_client,
            qdrant_client=qdrant,
        )

        for question, expected_filenames in QUESTIONS:
            results = retrieval.retrieve(
                question,
                user_id=owner_id,
            )
            retrieved_filenames = {
                result.filename
                for result in results
            }

            print()
            print("=" * 80)
            print(f"QUESTION: {question}")
            print(
                "FILES:",
                Counter(
                    result.filename
                    for result in results
                ),
            )
            for result in results:
                print(
                    f"{result.score:.4f} "
                    f"{result.filename} "
                    f"page={result.page_number} "
                    f"chunk={result.chunk_index}",
                )

            if not expected_filenames <= retrieved_filenames:
                raise AssertionError(
                    f"Missing expected files: "
                    f"{expected_filenames - retrieved_filenames}",
                )

        print()
        print("multi_document_retrieval=passed")
    finally:
        qdrant.client.delete_collection(collection_name)


if __name__ == "__main__":
    main()
