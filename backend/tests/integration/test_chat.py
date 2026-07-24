from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api.deps import get_llm_client
from app.clients.llm_client import LLMAnswer
from app.core.config import get_settings
from app.core.exceptions import ApplicationError
from app.main import app
from tests.pdf_factory import create_test_pdf


class FakeLLMClient:
    def answer(self, *, question, sources) -> LLMAnswer:
        assert question
        assert sources
        return LLMAnswer(text=f"Nội dung trả lời cho {question} [1]")


class UnavailableLLMClient:
    def answer(self, *, question, sources) -> LLMAnswer:
        raise ApplicationError(
            "LLM_UNAVAILABLE",
            "Model unavailable.",
            status_code=503,
        )


def configure_chat_test(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    llm_client,
) -> None:
    monkeypatch.setattr(
        get_settings(),
        "document_upload_directory",
        str(tmp_path),
    )
    app.dependency_overrides[get_llm_client] = lambda: llm_client


def start_guest_and_upload(client: TestClient) -> dict:
    session_response = client.post(
        "/api/v1/guest/session",
        headers={
            "User-Agent": "Chat Test Browser",
            "Accept-Language": "vi-VN",
        },
    )
    assert session_response.status_code == 200

    upload_response = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "handbook.pdf",
                create_test_pdf(
                    "Chinh sach nghi phep gom muoi hai ngay moi nam.",
                    "Nhan vien gui yeu cau cho quan ly truc tiep.",
                ),
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201
    return upload_response.json()


def test_guest_can_ask_document_and_receive_citation(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_chat_test(monkeypatch, tmp_path, FakeLLMClient())
    document = start_guest_and_upload(client)
    unrelated_upload = client.post(
        "/api/v1/documents",
        files={
            "file": (
                "remote-work.pdf",
                create_test_pdf(
                    "Nhan vien duoc lam viec tu xa hai ngay moi tuan.",
                ),
                "application/pdf",
            ),
        },
    )
    assert unrelated_upload.status_code == 201

    response = client.post(
        "/api/v1/ask",
        json={"question": "Chinh sach nghi phep la gi?"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"].endswith("[1]")
    assert body["questions_remaining"] == 2
    assert body["citations"] == [
        {
            "index": 1,
            "document_id": document["id"],
            "filename": "handbook.pdf",
            "page_number": 1,
            "excerpt": "Chinh sach nghi phep gom muoi hai ngay moi nam.",
        },
    ]
    assert client.get("/api/v1/guest/usage").json()["question_count"] == 1


def test_blank_question_is_rejected(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_chat_test(monkeypatch, tmp_path, FakeLLMClient())
    start_guest_and_upload(client)

    response = client.post(
        "/api/v1/ask",
        json={"question": "   "},
    )

    assert response.status_code == 422
    assert client.get("/api/v1/guest/usage").json()["question_count"] == 0


def test_fourth_guest_question_is_rejected_without_calling_model(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_chat_test(monkeypatch, tmp_path, FakeLLMClient())
    start_guest_and_upload(client)
    path = "/api/v1/ask"

    for index in range(3):
        response = client.post(
            path,
            json={"question": f"Câu hỏi {index + 1}"},
        )
        assert response.status_code == 200

    rejected = client.post(
        path,
        json={"question": "Câu hỏi thứ tư"},
    )

    assert rejected.status_code == 403
    assert (
        rejected.json()["error"]["code"]
        == "GUEST_QUESTION_LIMIT_REACHED"
    )
    assert client.get("/api/v1/guest/usage").json()["question_count"] == 3


def test_failed_model_call_does_not_consume_guest_question(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_chat_test(monkeypatch, tmp_path, UnavailableLLMClient())
    start_guest_and_upload(client)

    response = client.post(
        "/api/v1/ask",
        json={"question": "Câu hỏi sẽ lỗi"},
    )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "LLM_UNAVAILABLE"
    assert client.get("/api/v1/guest/usage").json()["question_count"] == 0


def test_user_cannot_ask_another_users_document(
    client: TestClient,
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    configure_chat_test(monkeypatch, tmp_path, FakeLLMClient())

    first_user = client.post(
        "/api/v1/auth/register",
        json={
            "email": "first-chat-owner@example.com",
            "password": "strong-password",
        },
    ).json()
    first_headers = {
        "Authorization": f"Bearer {first_user['access_token']}",
    }
    upload_response = client.post(
        "/api/v1/documents",
        headers=first_headers,
        files={
            "file": (
                "private.pdf",
                create_test_pdf("private content"),
                "application/pdf",
            ),
        },
    )
    assert upload_response.status_code == 201

    second_user = client.post(
        "/api/v1/auth/register",
        json={
            "email": "second-chat-owner@example.com",
            "password": "strong-password",
        },
    ).json()
    second_headers = {
        "Authorization": f"Bearer {second_user['access_token']}",
    }

    response = client.post(
        "/api/v1/ask",
        headers=second_headers,
        json={"question": "Nội dung là gì?"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "DOCUMENT_REQUIRED"
