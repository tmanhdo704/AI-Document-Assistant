"""Stateless PDF validation and local-storage helpers."""

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.core.exceptions import ApplicationError

ALLOWED_PDF_CONTENT_TYPES = {
    "application/pdf",
    "application/octet-stream",
}


@dataclass(frozen=True)
class ValidatedPdf:
    original_filename: str
    content_type: str
    content: bytes
    size_bytes: int
    file_hash: str


async def validate_pdf_upload(
    upload: UploadFile,
    *,
    max_size_bytes: int,
) -> ValidatedPdf:
    original_filename = _normalize_filename(upload.filename)

    if not original_filename:
        raise ApplicationError(
            "INVALID_DOCUMENT_FILENAME",
            "Document filename is invalid.",
            status_code=400,
        )

    if len(original_filename) > 255:
        raise ApplicationError(
            "DOCUMENT_FILENAME_TOO_LONG",
            "Document filename is too long.",
            status_code=400,
        )

    if Path(original_filename).suffix.lower() != ".pdf":
        raise ApplicationError(
            "UNSUPPORTED_DOCUMENT_TYPE",
            "Only PDF documents are supported.",
            status_code=415,
        )

    received_content_type = (upload.content_type or "").strip().lower()

    if (
        received_content_type
        and received_content_type not in ALLOWED_PDF_CONTENT_TYPES
    ):
        raise ApplicationError(
            "UNSUPPORTED_DOCUMENT_TYPE",
            "Only PDF documents are supported.",
            status_code=415,
        )

    content = await upload.read(max_size_bytes + 1)

    if len(content) > max_size_bytes:
        raise ApplicationError(
            "DOCUMENT_TOO_LARGE",
            "Document exceeds the maximum allowed size.",
            status_code=413,
            details={"max_size_bytes": max_size_bytes},
        )

    if not content:
        raise ApplicationError(
            "EMPTY_DOCUMENT",
            "Document is empty.",
            status_code=400,
        )

    if not content.startswith(b"%PDF-"):
        raise ApplicationError(
            "INVALID_PDF",
            "Document does not contain valid PDF data.",
            status_code=400,
        )

    return ValidatedPdf(
        original_filename=original_filename,
        content_type="application/pdf",
        content=content,
        size_bytes=len(content),
        file_hash=hashlib.sha256(content).hexdigest(),
    )


def generate_document_storage_key() -> str:
    return f"documents/{uuid.uuid4()}.pdf"


def save_document_file(
    *,
    upload_directory: str,
    storage_key: str,
    content: bytes,
) -> Path:
    target_path = _resolve_storage_path(upload_directory, storage_key)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_suffix(".tmp")

    try:
        temporary_path.write_bytes(content)
        temporary_path.replace(target_path)
    finally:
        temporary_path.unlink(missing_ok=True)

    return target_path


def delete_document_file(
    *,
    upload_directory: str,
    storage_key: str,
) -> None:
    target_path = _resolve_storage_path(upload_directory, storage_key)
    target_path.unlink(missing_ok=True)


def _normalize_filename(filename: str | None) -> str:
    if filename is None:
        return ""

    normalized = filename.replace("\\", "/")
    return normalized.rsplit("/", maxsplit=1)[-1].strip()


def _resolve_storage_path(
    upload_directory: str,
    storage_key: str,
) -> Path:
    storage_root = Path(upload_directory).resolve()
    target_path = (storage_root / storage_key).resolve()

    if not target_path.is_relative_to(storage_root):
        raise ValueError("Storage key escapes the upload directory.")

    return target_path
