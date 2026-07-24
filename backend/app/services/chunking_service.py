"""Page-aware text chunking."""

from dataclasses import dataclass

from app.services.extraction_service import ExtractedPage


@dataclass(frozen=True)
class TextChunk:
    page_number: int
    text: str


class ChunkingService:
    def __init__(
        self,
        *,
        chunk_size: int = 1400,
        overlap: int = 180,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive.")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be between 0 and chunk_size.")

        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_pages(
        self,
        pages: tuple[ExtractedPage, ...],
    ) -> tuple[TextChunk, ...]:
        chunks: list[TextChunk] = []

        for page in pages:
            chunks.extend(self._chunk_page(page))

        return tuple(chunks)

    def _chunk_page(self, page: ExtractedPage) -> list[TextChunk]:
        text = page.text.strip()

        if not text:
            return []

        result: list[TextChunk] = []
        start = 0

        while start < len(text):
            desired_end = min(start + self.chunk_size, len(text))
            end = self._find_boundary(text, start, desired_end)
            chunk_text = text[start:end].strip()

            if chunk_text:
                result.append(
                    TextChunk(
                        page_number=page.page_number,
                        text=chunk_text,
                    ),
                )

            if end >= len(text):
                break

            next_start = max(end - self.overlap, start + 1)
            start = self._skip_whitespace(text, next_start)

        return result

    @staticmethod
    def _find_boundary(
        text: str,
        start: int,
        desired_end: int,
    ) -> int:
        if desired_end >= len(text):
            return len(text)

        minimum_end = start + max((desired_end - start) // 2, 1)

        for separator in ("\n", ". ", " "):
            boundary = text.rfind(separator, minimum_end, desired_end)
            if boundary != -1:
                return boundary + len(separator)

        return desired_end

    @staticmethod
    def _skip_whitespace(text: str, start: int) -> int:
        while start < len(text) and text[start].isspace():
            start += 1
        return start
