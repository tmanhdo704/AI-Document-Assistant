import pytest

from app.core.exceptions import ApplicationError
from app.services.extraction_service import ExtractionService
from tests.pdf_factory import create_test_pdf


def test_extract_pdf_text_by_page() -> None:
    content = create_test_pdf(
        "First page",
        "Second page",
    )

    result = ExtractionService().extract_pdf(content)

    assert result.page_count == 2
    assert result.character_count == 21
    assert [page.page_number for page in result.pages] == [1, 2]
    assert [page.text for page in result.pages] == [
        "First page",
        "Second page",
    ]


def test_reject_encrypted_pdf() -> None:
    content = create_test_pdf(
        "Protected content",
        password="secret",
    )

    with pytest.raises(ApplicationError) as error_info:
        ExtractionService().extract_pdf(content)

    assert error_info.value.code == "ENCRYPTED_PDF"
    assert error_info.value.status_code == 422


def test_reject_pdf_without_extractable_text() -> None:
    content = create_test_pdf("")

    with pytest.raises(ApplicationError) as error_info:
        ExtractionService().extract_pdf(content)

    assert error_info.value.code == "PDF_TEXT_NOT_FOUND"
    assert error_info.value.status_code == 422


def test_reject_invalid_pdf() -> None:
    with pytest.raises(ApplicationError) as error_info:
        ExtractionService().extract_pdf(
            b"%PDF-1.7\ninvalid",
        )

    assert error_info.value.code == "INVALID_PDF"
    assert error_info.value.status_code == 400
