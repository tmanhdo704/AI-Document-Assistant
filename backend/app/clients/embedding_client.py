"""Google Gemini embedding provider boundary."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError


@dataclass(frozen=True)
class EmbeddingDocument:
    title: str
    text: str


EmbeddingVector = tuple[float, ...]


class EmbeddingClient:
    def __init__(
        self,
        settings: Settings | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.transport = transport

    def embed_query(self, query: str) -> EmbeddingVector:
        """Create one vector for a user's search question."""
        query = query.strip()
        if not query:
            raise ApplicationError(
                "EMBEDDING_INPUT_INVALID",
                "The embedding query cannot be empty.",
            )

        prepared_query = f"task: search result | query: {query}"
        return self._embed_batch((prepared_query,))[0]

    def embed_documents(
        self,
        documents: Sequence[EmbeddingDocument],
    ) -> tuple[EmbeddingVector, ...]:
        """Create vectors for document chunks in configured batches."""
        if not documents:
            return ()

        prepared_documents = tuple(
            self._prepare_document(document)
            for document in documents
        )

        vectors: list[EmbeddingVector] = []
        batch_size = max(1, self.settings.embedding_batch_size)

        for start in range(0, len(prepared_documents), batch_size):
            batch = prepared_documents[start : start + batch_size]
            vectors.extend(self._embed_batch(batch))

        return tuple(vectors)

    def _embed_batch(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        self._validate_configuration()

        model_name = self._model_name()

        payload = {
            "requests": [
                {
                    "model": model_name,
                    "content": {
                        "parts": [
                            {
                                "text": text,
                            },
                        ],
                    },
                    "output_dimensionality": (
                        self.settings.embedding_dimension
                    ),
                }
                for text in texts
            ],
        }

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.settings.gemini_api_key,
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
                    f"{model_name}:batchEmbedContents",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.TimeoutException as exc:
            raise ApplicationError(
                "EMBEDDING_TIMEOUT",
                "The embedding model took too long to respond.",
                status_code=504,
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApplicationError(
                "EMBEDDING_UNAVAILABLE",
                "The embedding model is currently unavailable.",
                status_code=503,
            ) from exc

        return self._parse_vectors(body, expected_count=len(texts))

    def _parse_vectors(
        self,
        body: Any,
        *,
        expected_count: int,
    ) -> tuple[EmbeddingVector, ...]:
        if not isinstance(body, dict):
            self._raise_invalid_response()

        embeddings = body.get("embeddings")
        if (
            not isinstance(embeddings, list)
            or len(embeddings) != expected_count
        ):
            self._raise_invalid_response()

        vectors: list[EmbeddingVector] = []

        for embedding in embeddings:
            if not isinstance(embedding, dict):
                self._raise_invalid_response()

            values = embedding.get("values")
            if (
                not isinstance(values, list)
                or len(values) != self.settings.embedding_dimension
                or not all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    for value in values
                )
            ):
                self._raise_invalid_response()

            vectors.append(tuple(float(value) for value in values))

        return tuple(vectors)

    def _validate_configuration(self) -> None:
        if not self.settings.gemini_api_key:
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                "GEMINI_API_KEY has not been configured.",
                status_code=503,
            )

        if not self.settings.embedding_model:
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                "EMBEDDING_MODEL has not been configured.",
                status_code=503,
            )

    def _model_name(self) -> str:
        model = self.settings.embedding_model.strip()

        if model.startswith("models/"):
            return model

        return f"models/{model}"

    @staticmethod
    def _prepare_document(
        document: EmbeddingDocument,
    ) -> str:
        title = document.title.strip() or "none"
        text = document.text.strip()

        if not text:
            raise ApplicationError(
                "EMBEDDING_INPUT_INVALID",
                "Document text cannot be empty.",
            )

        return f"title: {title} | text: {text}"

    @staticmethod
    def _raise_invalid_response() -> None:
        raise ApplicationError(
            "EMBEDDING_INVALID_RESPONSE",
            "The embedding model returned an invalid response.",
            status_code=502,
        )