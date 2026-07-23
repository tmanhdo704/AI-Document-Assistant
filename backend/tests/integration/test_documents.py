from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.core.config import get_settings
from tests.pdf_factory import create_test_pdf


def start_guest_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/guest/session",
        headers={
            "User-Agent": "Document Test Browser",
            "Accept-Language": "vi-VN",
        },
    )
    assert response.status_code == 200


def use_temporary_upload_directory(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "document_upload_directory",
        str(tmp_path),
    )


def test_guest_can_upload_and_list_pdf(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    start_guest_session(client)
    content = create_test_pdf("guest document")

    upload_response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "guest-report.pdf",
                content,
                "application/pdf",
            ),
        },
    )

    assert upload_response.status_code == 201
    uploaded = upload_response.json()
    assert uploaded["original_filename"] == "guest-report.pdf"
    assert uploaded["content_type"] == "application/pdf"
    assert uploaded["size_bytes"] == len(content)
    assert uploaded["status"] == "EXTRACTED"
    assert uploaded["page_count"] == 1
    assert "storage_key" not in uploaded
    assert "file_hash" not in uploaded

    saved_files = list(tmp_path.rglob("*.pdf"))
    assert len(saved_files) == 1
    assert saved_files[0].read_bytes() == content

    list_response = client.get("/api/v1/documents")
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [
        uploaded["id"],
    ]


def test_authenticated_user_can_upload_pdf(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "document-owner@example.com",
            "password": "strong-password",
        },
    )
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    upload_response = client.post(
        "/api/v1/documents",
        headers=headers,
        files={
            "file": (
                "user-report.pdf",
                create_test_pdf("user document"),
                "application/pdf",
            ),
        },
    )

    assert upload_response.status_code == 201

    list_response = client.get(
        "/api/v1/documents",
        headers=headers,
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert (
        list_response.json()[0]["original_filename"]
        == "user-report.pdf"
    )


def test_upload_requires_user_or_guest_session(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "report.pdf",
                create_test_pdf("content"),
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "DOCUMENT_OWNER_REQUIRED"
    assert not list(tmp_path.rglob("*.pdf"))


def test_invalid_pdf_is_not_stored(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    start_guest_session(client)

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "fake.pdf",
                b"plain text",
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_PDF"
    assert not list(tmp_path.rglob("*.pdf"))
    assert client.get("/api/v1/documents").json() == []


def test_oversized_pdf_is_rejected(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    monkeypatch.setattr(
        get_settings(),
        "document_max_size_bytes",
        10,
    )
    start_guest_session(client)

    response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "large.pdf",
                create_test_pdf("large document"),
                "application/pdf",
            ),
        },
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "DOCUMENT_TOO_LARGE"
    assert not list(tmp_path.rglob("*.pdf"))


def test_guest_document_limit_is_three(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    start_guest_session(client)

    for index in range(3):
        response = client.post(
            "/api/v1/documents",
            files={
                "file": (
                    f"guest-{index}.pdf",
                    create_test_pdf(f"guest {index}"),
                    "application/pdf",
                ),
            },
        )
        assert response.status_code == 201

    rejected_response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "guest-4.pdf",
                create_test_pdf("guest 4"),
                "application/pdf",
            ),
        },
    )

    assert rejected_response.status_code == 403
    error = rejected_response.json()["error"]
    assert error["code"] == "DOCUMENT_LIMIT_REACHED"
    assert error["details"] == {
        "document_count": 3,
        "document_limit": 3,
    }
    assert len(client.get("/api/v1/documents").json()) == 3
    assert len(list(tmp_path.rglob("*.pdf"))) == 3


def test_user_document_limit_is_ten(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    use_temporary_upload_directory(monkeypatch, tmp_path)
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "limited-user@example.com",
            "password": "strong-password",
        },
    )
    access_token = register_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    for index in range(10):
        response = client.post(
            "/api/v1/documents",
            headers=headers,
            files={
                "file": (
                    f"user-{index}.pdf",
                    create_test_pdf(f"user {index}"),
                    "application/pdf",
                ),
            },
        )
        assert response.status_code == 201

    rejected_response = client.post(
        "/api/v1/documents",
        headers=headers,
        files={
            "file": (
                "user-11.pdf",
                create_test_pdf("user 11"),
                "application/pdf",
            ),
        },
    )

    assert rejected_response.status_code == 403
    error = rejected_response.json()["error"]
    assert error["code"] == "DOCUMENT_LIMIT_REACHED"
    assert error["details"] == {
        "document_count": 10,
        "document_limit": 10,
    }
    list_response = client.get(
        "/api/v1/documents",
        headers=headers,
    )
    assert len(list_response.json()) == 10
    assert len(list(tmp_path.rglob("*.pdf"))) == 10
