import uuid
from collections.abc import Sequence
from functools import lru_cache
from typing import Literal

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    Record,
    ScoredPoint,
    VectorParams,
)

from app.core.config import Settings, get_settings

OwnerType = Literal["user", "guest"]


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

    def search(
        self,
        *,
        query_vector: Sequence[float],
        owner_type: OwnerType,
        owner_id: uuid.UUID,
        limit: int,
    ) -> tuple[ScoredPoint, ...]:
        """Find the most relevant chunks owned by one user or guest."""
        if limit <= 0:
            return ()

        if len(query_vector) != self.settings.embedding_dimension:
            raise ValueError(
                "Query vector dimension does not match "
                "the Qdrant collection dimension.",
            )

        response = self.client.query_points(
            collection_name=self.settings.qdrant_collection_name,
            query=list(query_vector),
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="owner_type",
                        match=MatchValue(value=owner_type),
                    ),
                    FieldCondition(
                        key="owner_id",
                        match=MatchValue(value=str(owner_id)),
                    ),
                ],
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return tuple(response.points)

    def get_opening_chunks(
        self,
        *,
        owner_type: OwnerType,
        owner_id: uuid.UUID,
        limit: int = 10,
    ) -> tuple[Record, ...]:
        """Load the opening chunk of each document owned by one owner."""
        if limit <= 0:
            return ()

        points, _ = self.client.scroll(
            collection_name=self.settings.qdrant_collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="owner_type",
                        match=MatchValue(value=owner_type),
                    ),
                    FieldCondition(
                        key="owner_id",
                        match=MatchValue(value=str(owner_id)),
                    ),
                    FieldCondition(
                        key="chunk_index",
                        match=MatchValue(value=0),
                    ),
                ],
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        return tuple(points)

    def get_chunks(
        self,
        *,
        owner_type: OwnerType,
        owner_id: uuid.UUID,
        references: Sequence[tuple[uuid.UUID, int]],
    ) -> tuple[Record, ...]:
        """Load known chunks and verify that they still belong to the owner."""
        unique_references = tuple(dict.fromkeys(references))

        if not unique_references:
            return ()

        point_ids = [
            str(uuid.uuid5(document_id, str(chunk_index)))
            for document_id, chunk_index in unique_references
            if chunk_index >= 0
        ]

        if not point_ids:
            return ()

        points = self.client.retrieve(
            collection_name=self.settings.qdrant_collection_name,
            ids=point_ids,
            with_payload=True,
            with_vectors=False,
        )

        return tuple(
            point
            for point in points
            if self._belongs_to_owner(
                point,
                owner_type=owner_type,
                owner_id=owner_id,
            )
        )

    @staticmethod
    def _belongs_to_owner(
        point: Record,
        *,
        owner_type: OwnerType,
        owner_id: uuid.UUID,
    ) -> bool:
        payload = point.payload

        return (
            isinstance(payload, dict)
            and payload.get("owner_type") == owner_type
            and payload.get("owner_id") == str(owner_id)
        )


@lru_cache
def get_qdrant_client() -> QdrantVectorClient:
    """Return the shared, initialized Qdrant client."""
    qdrant = QdrantVectorClient()
    qdrant.ensure_collection()
    return qdrant
