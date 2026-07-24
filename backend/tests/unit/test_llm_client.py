import json
import uuid

import httpx

from app.clients.llm_client import (
    NO_ANSWER_TEXT,
    LLMClient,
)
from app.core.config import Settings
from app.services.retrieval_service import RetrievedChunk


def test_llm_client_sends_grounded_prompt_and_reads_answer() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == (
            "https://generativelanguage.example.test/v1beta/"
            "models/gemini-test:generateContent"
        )
        assert request.headers["x-goog-api-key"] == "secret"

        payload = json.loads(request.content)
        prompt = payload["contents"][0]["parts"][0]["text"]
        assert "Trang 4" in prompt
        assert "Nghỉ phép là bao nhiêu?" in prompt
        assert "DocAlly" in payload["systemInstruction"]["parts"][0]["text"]
        response_format = payload["generationConfig"]["responseFormat"]
        assert response_format["text"]["mimeType"] == "APPLICATION_JSON"
        assert (
            response_format["text"]["schema"]["properties"]["answerable"][
                "type"
            ]
            == "boolean"
        )

        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "answerable": True,
                                            "answer": (
                                                "Có 12 ngày nghỉ phép [1]."
                                            ),
                                            "evidence": [
                                                {
                                                    "source_index": 1,
                                                    "quote": (
                                                        "Nhân viên có 12 "
                                                        "ngày nghỉ phép."
                                                    ),
                                                },
                                            ],
                                        },
                                        ensure_ascii=False,
                                    ),
                                },
                            ],
                        },
                    },
                ],
            },
        )

    settings = Settings(
        _env_file=None,
        jwt_secret_key="test-secret",
        google_client_id="",
        gemini_api_key="secret",
        gemini_base_url=(
            "https://generativelanguage.example.test/v1beta"
        ),
        gemini_model="gemini-test",
    )
    client = LLMClient(
        settings=settings,
        transport=httpx.MockTransport(handler),
    )

    result = client.answer(
        question="Nghỉ phép là bao nhiêu?",
        sources=(
            RetrievedChunk(
                document_id=uuid.uuid4(),
                filename="handbook.pdf",
                page_number=4,
                text="Nhân viên có 12 ngày nghỉ phép.",
                score=1.0,
            ),
        ),
    )

    assert result.text == "Có 12 ngày nghỉ phép [1]."
    assert result.answerable is True
    assert result.cited_indexes == (1,)


def test_llm_client_refuses_when_model_marks_answer_unanswerable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "answerable": False,
                                            "answer": "",
                                            "evidence": [],
                                        },
                                    ),
                                },
                            ],
                        },
                    },
                ],
            },
        )

    client = LLMClient(
        settings=_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = client.answer(
        question="Tài liệu có nói về SAFE không?",
        sources=(_source(),),
    )

    assert result.text == NO_ANSWER_TEXT
    assert result.answerable is False
    assert result.cited_indexes == ()


def test_llm_client_refuses_unverified_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "answerable": True,
                                            "answer": (
                                                "Có hợp đồng SAFE [1]."
                                            ),
                                            "evidence": [
                                                {
                                                    "source_index": 1,
                                                    "quote": (
                                                        "Tài liệu mô tả "
                                                        "hợp đồng SAFE."
                                                    ),
                                                },
                                            ],
                                        },
                                        ensure_ascii=False,
                                    ),
                                },
                            ],
                        },
                    },
                ],
            },
        )

    client = LLMClient(
        settings=_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = client.answer(
        question="Tài liệu có nói về SAFE không?",
        sources=(_source(),),
    )

    assert result.text == NO_ANSWER_TEXT
    assert result.answerable is False
    assert result.cited_indexes == ()


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        jwt_secret_key="test-secret",
        google_client_id="",
        gemini_api_key="secret",
        gemini_base_url=(
            "https://generativelanguage.example.test/v1beta"
        ),
        gemini_model="gemini-test",
    )


def _source() -> RetrievedChunk:
    return RetrievedChunk(
        document_id=uuid.uuid4(),
        filename="handbook.pdf",
        page_number=4,
        text="Nhân viên có 12 ngày nghỉ phép.",
        score=1.0,
    )
