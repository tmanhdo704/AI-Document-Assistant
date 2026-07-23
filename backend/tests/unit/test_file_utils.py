import asyncio
import hashlib
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from app.core.exceptions import ApplicationError
from app.utils.file import (
    delete_document_file,
    generate_document_storage_key,
    save_document_file,
    validate_pdf_upload,
)


def create_upload(
    *,
    filename: str,
    content: bytes,
    content_type: str,
) -> UploadFile:
    return UploadFile(
        filename=filename,
        file=BytesIO(content),
        headers=Headers({"content-type": content_type}),
    )


def test_validate_pdf_upload() -> None:
    content = b"%PDF-1.7\nexample"
    upload = create_upload(
        filename=r"C:\fakepath\Report.PDF",
        content=content,
        content_type="application/pdf",
    )

    result = asyncio.run(
        validate_pdf_upload(upload, max_size_bytes=1024),
    )

    assert result.original_filename == "Report.PDF"
    assert result.content_type == "application/pdf"
    assert result.content == content
    assert result.size_bytes == len(content)
    assert result.file_hash == hashlib.sha256(content).hexdigest()


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "expected_code"),
    [
        (
            "notes.txt",
            "text/plain",
            b"hello",
            "UNSUPPORTED_DOCUMENT_TYPE",
        ),
        (
            "fake.pdf",
            "text/plain",
            b"%PDF-1.7\nfake",
            "UNSUPPORTED_DOCUMENT_TYPE",
        ),
        (
            "fake.pdf",
            "application/pdf",
            b"not a real pdf",
            "INVALID_PDF",
        ),
    ],
)
def test_reject_invalid_pdf_upload(
    filename: str,
    content_type: str,
    content: bytes,
    expected_code: str,
) -> None:
    upload = create_upload(
        filename=filename,
        content=content,
        content_type=content_type,
    )

    with pytest.raises(ApplicationError) as error_info:
        asyncio.run(
            validate_pdf_upload(upload, max_size_bytes=1024),
        )

    assert error_info.value.code == expected_code


def test_reject_oversized_pdf() -> None:
    upload = create_upload(
        filename="large.pdf",
        content=b"%PDF-" + b"a" * 20,
        content_type="application/pdf",
    )

    with pytest.raises(ApplicationError) as error_info:
        asyncio.run(
            validate_pdf_upload(upload, max_size_bytes=10),
        )

    assert error_info.value.code == "DOCUMENT_TOO_LARGE"
    assert error_info.value.status_code == 413


def test_save_and_delete_document_file(tmp_path: Path) -> None:
    content = b"%PDF-1.7\nexample"
    storage_key = generate_document_storage_key()

    saved_path = save_document_file(
        upload_directory=str(tmp_path),
        storage_key=storage_key,
        content=content,
    )

    assert saved_path.read_bytes() == content
    assert saved_path.is_relative_to(tmp_path)

    delete_document_file(
        upload_directory=str(tmp_path),
        storage_key=storage_key,
    )

    assert not saved_path.exists()


def test_storage_key_cannot_escape_directory(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        save_document_file(
            upload_directory=str(tmp_path),
            storage_key="../outside.pdf",
            content=b"%PDF-1.7",
        )
