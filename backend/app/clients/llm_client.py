"""Google Gemini large language model provider boundary."""

import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError
from app.services.retrieval_service import RetrievedChunk

NO_ANSWER_TEXT = (
    "Tôi không tìm thấy đủ thông tin trong tài liệu để trả lời câu hỏi này."
)
CITATION_PATTERN = re.compile(r"\[(\d+)]")
MIN_EVIDENCE_LENGTH = 20


@dataclass(frozen=True)
class LLMAnswer:
    text: str
    answerable: bool = True
    cited_indexes: tuple[int, ...] = ()


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
                text=NO_ANSWER_TEXT,
                answerable=False,
            )

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.gemini_api_key,
        }
        generation_config: dict[str, Any] = {
            "maxOutputTokens": (
                self.settings.llm_max_output_tokens
            ),
            "temperature": 0,
            "responseFormat": {
                "text": {
                    "mimeType": "APPLICATION_JSON",
                    "schema": self._response_schema(),
                },
            },
        }

        if self.settings.gemini_model.startswith("gemini-3"):
            generation_config["thinkingConfig"] = {
                "thinkingLevel": "low",
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
            "generationConfig": generation_config,
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

        raw_text = self._response_text(body)
        if not raw_text:
            raise ApplicationError(
                "LLM_INVALID_RESPONSE",
                "The answer model returned an invalid response.",
                status_code=502,
            )

        return self._parse_answer(
            raw_text,
            sources=sources,
        )

    @staticmethod
    def _system_prompt() -> str:
        return (
            "Bạn là DocAlly, trợ lý hỏi đáp tài liệu có tính bảo thủ. "
            "Chỉ được trả lời khi nguồn cung cấp bằng chứng trực tiếp "
            "cho câu hỏi. Không dùng kiến thức bên ngoài, không suy diễn "
            "từ chủ đề tương tự và không tự tạo dữ kiện hoặc số trang. "
            "Nếu thiếu bằng chứng hoặc còn nghi ngờ, đặt answerable=false. "
            "Nếu answerable=true, mỗi ý trong answer phải gắn citation "
            "dạng [1], [2]. Với mỗi nguồn được dùng, evidence phải chứa "
            "một đoạn ngắn sao chép nguyên văn từ đúng nguồn đó. "
            "Trả lời bằng ngôn ngữ của câu hỏi."
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
    def _response_schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "answerable": {
                    "type": "boolean",
                    "description": (
                        "True only when the sources directly support "
                        "the complete answer."
                    ),
                },
                "answer": {
                    "type": "string",
                    "description": (
                        "Grounded answer with [source_index] citations, "
                        "or an empty string when answerable is false."
                    ),
                },
                "evidence": {
                    "type": "array",
                    "description": (
                        "Short verbatim excerpts copied from sources "
                        "that directly prove the answer."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "source_index": {
                                "type": "integer",
                                "minimum": 1,
                            },
                            "quote": {
                                "type": "string",
                                "description": (
                                    "A verbatim excerpt from the source."
                                ),
                            },
                        },
                        "required": [
                            "source_index",
                            "quote",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "answerable",
                "answer",
                "evidence",
            ],
            "additionalProperties": False,
        }

    def _parse_answer(
        self,
        raw_text: str,
        *,
        sources: tuple[RetrievedChunk, ...],
    ) -> LLMAnswer:
        try:
            data = json.loads(raw_text)
        except (TypeError, json.JSONDecodeError) as exc:
            raise self._invalid_response_error() from exc

        if not isinstance(data, dict):
            raise self._invalid_response_error()

        answerable = data.get("answerable")
        answer = data.get("answer")
        evidence = data.get("evidence")

        if (
            not isinstance(answerable, bool)
            or not isinstance(answer, str)
            or not isinstance(evidence, list)
        ):
            raise self._invalid_response_error()

        if not answerable:
            return LLMAnswer(
                text=NO_ANSWER_TEXT,
                answerable=False,
            )

        normalized_answer = answer.strip()
        cited_indexes = self._validated_evidence_indexes(
            evidence,
            sources=sources,
        )

        if not normalized_answer or not cited_indexes:
            return LLMAnswer(
                text=NO_ANSWER_TEXT,
                answerable=False,
            )

        answer_markers = {
            int(match)
            for match in CITATION_PATTERN.findall(normalized_answer)
        }

        if any(
            marker not in cited_indexes
            for marker in answer_markers
        ):
            return LLMAnswer(
                text=NO_ANSWER_TEXT,
                answerable=False,
            )

        missing_markers = [
            index
            for index in cited_indexes
            if index not in answer_markers
        ]

        if missing_markers:
            normalized_answer = (
                f"{normalized_answer} "
                + " ".join(
                    f"[{index}]"
                    for index in missing_markers
                )
            )

        return LLMAnswer(
            text=normalized_answer,
            answerable=True,
            cited_indexes=cited_indexes,
        )

    @classmethod
    def _validated_evidence_indexes(
        cls,
        evidence: list[Any],
        *,
        sources: tuple[RetrievedChunk, ...],
    ) -> tuple[int, ...]:
        if not evidence:
            return ()

        indexes: list[int] = []

        for item in evidence:
            if not isinstance(item, dict):
                return ()

            source_index = item.get("source_index")
            quote = item.get("quote")

            if (
                not isinstance(source_index, int)
                or isinstance(source_index, bool)
                or not 1 <= source_index <= len(sources)
                or not isinstance(quote, str)
            ):
                return ()

            normalized_quote = cls._normalize_evidence(quote)
            normalized_source = cls._normalize_evidence(
                sources[source_index - 1].text,
            )

            if (
                len(normalized_quote) < MIN_EVIDENCE_LENGTH
                or normalized_quote not in normalized_source
            ):
                return ()

            if source_index not in indexes:
                indexes.append(source_index)

        return tuple(indexes)

    @staticmethod
    def _normalize_evidence(text: str) -> str:
        return " ".join(text.split()).casefold()

    @staticmethod
    def _invalid_response_error() -> ApplicationError:
        return ApplicationError(
            "LLM_INVALID_RESPONSE",
            "The answer model returned an invalid response.",
            status_code=502,
        )

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
