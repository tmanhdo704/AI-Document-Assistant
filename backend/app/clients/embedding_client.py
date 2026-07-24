import math
from collections.abc import Sequence
from dataclasses import dataclass
from threading import Lock
from typing import Any

from fastembed import TextEmbedding
from fastembed.common.model_description import (
    ModelSource,
    PoolingType,
)

from app.core.config import Settings, get_settings
from app.core.exceptions import ApplicationError

CUSTOM_E5_MODEL = "intfloat/multilingual-e5-small"
CUSTOM_E5_DIMENSION = 384

_MODEL_CACHE: dict[tuple[str, str], TextEmbedding] = {}
_MODEL_LOCK = Lock()


@dataclass(frozen=True)
class EmbeddingDocument:
    title: str
    text: str


EmbeddingVector = tuple[float, ...]


def _register_custom_model(model_name: str) -> None:
    supported_models = {
        item.get("model")
        for item in TextEmbedding.list_supported_models()
    }

    if model_name in supported_models:
        return

    if model_name != CUSTOM_E5_MODEL:
        raise ValueError(
            f"FastEmbed model is not supported: {model_name}",
        )

    TextEmbedding.add_custom_model(
        model=CUSTOM_E5_MODEL,
        pooling=PoolingType.MEAN,
        normalization=True,
        sources=ModelSource(hf=CUSTOM_E5_MODEL),
        dim=CUSTOM_E5_DIMENSION,
        model_file="onnx/model.onnx",
        description="Multilingual E5 small",
        license="mit",
    )


def _get_embedding_model(
    model_name: str,
    cache_directory: str,
) -> TextEmbedding:
    cache_key = (model_name, cache_directory)

    with _MODEL_LOCK:
        cached_model = _MODEL_CACHE.get(cache_key)

        if cached_model is not None:
            return cached_model

        _register_custom_model(model_name)

        model = TextEmbedding(
            model_name=model_name,
            cache_dir=cache_directory,
        )

        _MODEL_CACHE[cache_key] = model
        return model


class EmbeddingClient:
    def __init__(
        self,
        settings: Settings | None = None,
        model: TextEmbedding | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._validate_configuration()

        try:
            self.model = model or _get_embedding_model(
                self.settings.embedding_model,
                self.settings.embedding_cache_directory,
            )
        except Exception as exc:
            raise ApplicationError(
                "EMBEDDING_MODEL_LOAD_FAILED",
                "The local embedding model could not be loaded.",
                status_code=503,
            ) from exc

    def embed_query(self, query: str) -> EmbeddingVector:
        """Create one local vector for a search question."""
        normalized_query = query.strip()

        if not normalized_query:
            raise ApplicationError(
                "EMBEDDING_INPUT_INVALID",
                "The embedding query cannot be empty.",
            )

        vectors = self._embed_texts(
            (f"query: {normalized_query}",),
        )

        return vectors[0]

    def embed_documents(
        self,
        documents: Sequence[EmbeddingDocument],
    ) -> tuple[EmbeddingVector, ...]:
        """Create local vectors for document chunks."""
        if not documents:
            return ()

        prepared_documents = tuple(
            self._prepare_document(document)
            for document in documents
        )

        return self._embed_texts(prepared_documents)

    def _embed_texts(
        self,
        texts: Sequence[str],
    ) -> tuple[EmbeddingVector, ...]:
        try:
            generated_vectors = self.model.embed(
                list(texts),
                batch_size=max(
                    1,
                    self.settings.embedding_batch_size,
                ),
            )

            vectors = tuple(
                self._to_vector(vector)
                for vector in generated_vectors
            )
        except ApplicationError:
            raise
        except Exception as exc:
            raise ApplicationError(
                "EMBEDDING_UNAVAILABLE",
                "The local embedding model is currently unavailable.",
                status_code=503,
            ) from exc

        if len(vectors) != len(texts):
            self._raise_invalid_output()

        return vectors

    def _to_vector(
        self,
        vector: Any,
    ) -> EmbeddingVector:
        raw_values = (
            vector.tolist()
            if hasattr(vector, "tolist")
            else vector
        )

        if not isinstance(raw_values, (list, tuple)):
            self._raise_invalid_output()

        try:
            values = tuple(
                float(value)
                for value in raw_values
            )
        except (TypeError, ValueError) as exc:
            raise ApplicationError(
                "EMBEDDING_INVALID_RESPONSE",
                "The local embedding model returned invalid values.",
                status_code=502,
            ) from exc

        if len(values) != self.settings.embedding_dimension:
            self._raise_invalid_output()

        if not all(math.isfinite(value) for value in values):
            self._raise_invalid_output()

        return values

    def _validate_configuration(self) -> None:
        if self.settings.embedding_provider != "fastembed":
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                "EMBEDDING_PROVIDER must be fastembed.",
                status_code=503,
            )

        if not self.settings.embedding_model:
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                "EMBEDDING_MODEL has not been configured.",
                status_code=503,
            )

        if self.settings.embedding_dimension <= 0:
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                "EMBEDDING_DIMENSION must be positive.",
                status_code=503,
            )

        if (
            self.settings.embedding_model == CUSTOM_E5_MODEL
            and self.settings.embedding_dimension
            != CUSTOM_E5_DIMENSION
        ):
            raise ApplicationError(
                "EMBEDDING_NOT_CONFIGURED",
                (
                    "multilingual-e5-small requires "
                    "EMBEDDING_DIMENSION=384."
                ),
                status_code=503,
            )

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

        return (
            f"passage: title: {title} | "
            f"text: {text}"
        )

    @staticmethod
    def _raise_invalid_output() -> None:
        raise ApplicationError(
            "EMBEDDING_INVALID_RESPONSE",
            "The local embedding model returned an invalid vector.",
            status_code=502,
        )