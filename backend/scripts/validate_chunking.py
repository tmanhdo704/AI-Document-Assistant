"""Validate chunk boundaries for local PDF files."""

import argparse
from pathlib import Path

from app.services.chunking_service import ChunkingService
from app.services.extraction_service import ExtractionService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pdf_paths = sorted(args.directory.glob("*.pdf"))

    if not pdf_paths:
        raise RuntimeError("No PDF files were found.")

    has_failures = False

    for pdf_path in pdf_paths:
        try:
            extracted = ExtractionService().extract_pdf(
                pdf_path.read_bytes(),
            )
        except Exception as exc:
            has_failures = True
            print(
                f"FAIL {pdf_path.name}: "
                f"{type(exc).__name__}: {exc}",
            )
            continue

        chunking_service = ChunkingService()
        chunks = chunking_service.chunk_pages(extracted.pages)
        page_text = {
            page.page_number: page.text
            for page in extracted.pages
        }
        mid_word_starts = 0

        for chunk in chunks:
            source_text = page_text[chunk.page_number]
            chunk_start = source_text.find(chunk.text)

            if (
                chunk_start > 0
                and not source_text[chunk_start - 1].isspace()
            ):
                mid_word_starts += 1

        oversized_chunks = sum(
            len(chunk.text) > chunking_service.chunk_size
            for chunk in chunks
        )
        status = (
            "PASS"
            if mid_word_starts == 0 and oversized_chunks == 0
            else "FAIL"
        )
        has_failures = has_failures or status == "FAIL"

        print(
            f"{status} {pdf_path.name}: "
            f"pages={extracted.page_count} "
            f"chunks={len(chunks)} "
            f"mid_word={mid_word_starts} "
            f"oversized={oversized_chunks}",
        )

    if has_failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
