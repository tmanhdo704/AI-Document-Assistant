"""Qdrant vector database boundary."""

from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import Settings, get_settings


class QdrantVectorClient:
    """Create and configure the Qdrant collection used by the application."""

    def __init__(
        self,
        settings: Settings | None = None,
        client: QdrantClient | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or QdrantClient(
            url=self.settings.qdrant_url,
            api_key=self.settings.qdrant_api_key or None,
        )

    def ensure_collection(self) -> None:
        """Create the document chunk collection when it does not exist."""
        collection_name = self.settings.qdrant_collection_name
        if self.client.collection_exists(collection_name):
            return

        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=self.settings.embedding_dimension,
                distance=Distance.COSINE,
            ),
        )


@lru_cache
def get_qdrant_client() -> QdrantVectorClient:
    """Return the shared, initialized Qdrant client."""
    qdrant = QdrantVectorClient()
    qdrant.ensure_collection()
    return qdrant
