import json
import uuid

import httpx

from app.clients.llm_client import LLMClient
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

        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": "Có 12 ngày nghỉ phép [1].",
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
