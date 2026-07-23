"""Page-aware PDF text extraction."""

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

from app.core.exceptions import ApplicationError


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str


@dataclass(frozen=True)
class ExtractedDocument:
    pages: tuple[ExtractedPage, ...]
    page_count: int
    character_count: int


class ExtractionService:
    def extract_pdf(
        self,
        content: bytes,
    ) -> ExtractedDocument:
        reader = self._create_reader(content)

        if reader.is_encrypted:
            try:
                decrypt_result = reader.decrypt("")
            except Exception as exc:
                raise self._encrypted_pdf_error() from exc

            if decrypt_result == 0:
                raise self._encrypted_pdf_error()

        extracted_pages: list[ExtractedPage] = []

        try:
            for page_index, page in enumerate(
                reader.pages,
                start=1,
            ):
                text = self._normalize_text(
                    page.extract_text() or "",
                )
                extracted_pages.append(
                    ExtractedPage(
                        page_number=page_index,
                        text=text,
                    ),
                )
        except FileNotDecryptedError as exc:
            raise self._encrypted_pdf_error() from exc
        except Exception as exc:
            raise ApplicationError(
                "PDF_EXTRACTION_FAILED",
                "Text could not be extracted from the PDF.",
                status_code=422,
            ) from exc

        if not extracted_pages:
            raise ApplicationError(
                "EMPTY_PDF",
                "PDF does not contain any pages.",
                status_code=422,
            )

        character_count = sum(
            len(page.text)
            for page in extracted_pages
        )

        if character_count == 0:
            raise ApplicationError(
                "PDF_TEXT_NOT_FOUND",
                "PDF does not contain extractable text.",
                status_code=422,
            )

        return ExtractedDocument(
            pages=tuple(extracted_pages),
            page_count=len(extracted_pages),
            character_count=character_count,
        )

    @staticmethod
    def _create_reader(content: bytes) -> PdfReader:
        try:
            return PdfReader(
                BytesIO(content),
                strict=False,
            )
        except (PdfReadError, ValueError, OSError) as exc:
            raise ApplicationError(
                "INVALID_PDF",
                "Document does not contain valid PDF data.",
                status_code=400,
            ) from exc

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized_lines = (
            line.strip()
            for line in text.replace("\x00", "").splitlines()
        )
        return "\n".join(
            line
            for line in normalized_lines
            if line
        ).strip()

    @staticmethod
    def _encrypted_pdf_error() -> ApplicationError:
        return ApplicationError(
            "ENCRYPTED_PDF",
            "Password-protected PDFs are not supported.",
            status_code=422,
        )
