"""Google Gemini large language model provider boundary."""

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.services.retrieval_service import RetrievedChunk


@dataclass(frozen=True)
class LLMAnswer:
    text: str


class LLMClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def answer(
        self,
        *,
        question: str,
        sources: tuple[RetrievedChunk, ...],
    ) -> LLMAnswer:
        if not self.settings.gemini_api_key:
            raise ApplicationError(
                "LLM_NOT_CONFIGURED",
                "GEMINI_API_KEY has not been configured.",
                status_code=503,
            )

        if not self.settings.gemini_model:
            raise ApplicationError(
                "LLM_NOT_CONFIGURED",
                "GEMINI_MODEL has not been configured.",
                status_code=503,
            )

        if not sources:
            return LLMAnswer(
                text=(
                    "Tôi không tìm thấy đủ thông tin trong tài liệu "
                    "để trả lời câu hỏi này."
                ),
            )

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.gemini_api_key,
        }

        payload = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": self._system_prompt(),
                    },
                ],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": self._user_prompt(
                                question,
                                sources,
                            ),
                        },
                    ],
                },
            ],
            "generationConfig": {
                "maxOutputTokens": (
                    self.settings.llm_max_output_tokens
                ),
            },
        }

        try:
            with httpx.Client(
                base_url=(
                    self.settings.gemini_base_url.rstrip("/") + "/"
                ),
                timeout=self.settings.llm_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = client.post(
                    (
                        f"models/{self.settings.gemini_model}"
                        ":generateContent"
                    ),
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                "LLM_TIMEOUT",
                "The answer model took too long to respond.",
                status_code=504,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApplicationError(
                "LLM_UNAVAILABLE",
                "The answer model is currently unavailable.",
                status_code=503,
            ) from exc

        text = self._response_text(body)
        if not text:
            raise ApplicationError(
                "LLM_INVALID_RESPONSE",
                "The answer model returned an invalid response.",
                status_code=502,
            )

        return LLMAnswer(text=text)

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Bạn là DocAlly, trợ lý hỏi đáp tài liệu. Chỉ trả lời từ "
            "các nguồn được cung cấp. Mỗi ý có căn cứ phải gắn citation "
            "dạng [1], [2]. Không được tự tạo dữ kiện hoặc số trang. "
            "Nếu nguồn không đủ để trả lời, hãy nói đúng câu: "
            "\"Tôi không tìm thấy đủ thông tin trong tài liệu để trả lời "
            "câu hỏi này.\" Trả lời bằng ngôn ngữ của câu hỏi."
        )

    @staticmethod
    def _user_prompt(
        question: str,
        sources: tuple[RetrievedChunk, ...],
    ) -> str:
        source_text = "\n\n".join(
            (
                f"[{index}] Tài liệu: {source.filename} | "
                f"Trang {source.page_number}\n{source.text}"
            )
            for index, source in enumerate(sources, start=1)
        )
        return f"Nguồn:\n{source_text}\n\nCâu hỏi: {question}"

    @staticmethod
    def _response_text(body: Any) -> str:
        try:
            parts = body["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError, TypeError):
            return ""

        if not isinstance(parts, list):
            return ""

        content = "".join(
            part.get("text", "")
            for part in parts
            if isinstance(part, dict)
            and isinstance(part.get("text"), str)
        )
        return content.strip()
