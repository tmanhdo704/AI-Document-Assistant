"""Evaluate retrieval from a freshly chunked local PDF."""

import argparse
from pathlib import Path

from app.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingDocument,
)
from app.services.chunking_service import ChunkingService
from app.services.extraction_service import ExtractionService
from scripts.evaluate_retrieval import QUESTIONS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--limit", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extracted = ExtractionService().extract_pdf(args.pdf.read_bytes())
    chunks = ChunkingService().chunk_pages(extracted.pages)
    embedding_client = EmbeddingClient()
    document_title = args.title or args.pdf.name
    chunk_vectors = embedding_client.embed_documents(
        tuple(
            EmbeddingDocument(
                title=document_title,
                text=chunk.text,
            )
            for chunk in chunks
        ),
    )

    print(
        f"Fresh evaluation: pages={extracted.page_count} "
        f"chunks={len(chunks)}",
    )

    for question in QUESTIONS:
        query_vector = embedding_client.embed_query(question)
        ranked = sorted(
            (
                (
                    sum(
                        query_value * chunk_value
                        for query_value, chunk_value in zip(
                            query_vector,
                            chunk_vector,
                            strict=True,
                        )
                    ),
                    index,
                )
                for index, chunk_vector in enumerate(chunk_vectors)
            ),
            reverse=True,
        )[: max(args.limit, 0)]

        print()
        print("=" * 80)
        print(f"QUESTION: {question}")

        for rank, (score, chunk_index) in enumerate(
            ranked,
            start=1,
        ):
            chunk = chunks[chunk_index]
            compact_text = " ".join(chunk.text.split())

            print()
            print(
                f"[{rank}] score={score:.4f} "
                f"page={chunk.page_number} "
                f"chunk={chunk_index}",
            )
            print(compact_text[:300])


if __name__ == "__main__":
    main()
