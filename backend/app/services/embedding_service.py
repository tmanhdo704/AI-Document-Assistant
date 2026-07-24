import uuid
from collections.abc import Sequence

from qdrant_client.models import PointStruct

from app.clients.embedding_client import (
    EmbeddingClient,
    EmbeddingDocument,
)
from app.clients.qdrant_client import (
    QdrantVectorClient,
    get_qdrant_client,
)
from app.services.chunking_service import TextChunk


class EmbeddingService:
    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        qdrant_client: QdrantVectorClient | None = None,
    ) -> None:
        self.embedding_client = embedding_client or EmbeddingClient()
        self.qdrant = qdrant_client or get_qdrant_client()

    def index_document(
        self,
        *,
        document_id: uuid.UUID,
        filename: str,
        chunks: Sequence[TextChunk],
        user_id: uuid.UUID | None = None,
        guest_session_id: uuid.UUID | None = None,
    ) -> int:
        """Create and store vectors for every chunk in one document."""
        owner_type, owner_id = self._resolve_owner(
            user_id=user_id,
            guest_session_id=guest_session_id,
        )

        if not chunks:
            return 0

        embedding_documents = tuple(
            EmbeddingDocument(
                title=filename,
                text=chunk.text,
            )
            for chunk in chunks
        )

        vectors = self.embedding_client.embed_documents(
            embedding_documents,
        )

        points = [
            PointStruct(
                id=str(
                    uuid.uuid5(
                        document_id,
                        str(chunk_index),
                    ),
                ),
                vector=list(vector),
                payload={
                    "owner_type": owner_type,
                    "owner_id": str(owner_id),
                    "document_id": str(document_id),
                    "filename": filename,
                    "page_number": chunk.page_number,
                    "chunk_index": chunk_index,
                    "text": chunk.text,
                },
            )
            for chunk_index, (chunk, vector) in enumerate(
                zip(chunks, vectors, strict=True),
            )
        ]

        self.qdrant.client.upsert(
            collection_name=(
                self.qdrant.settings.qdrant_collection_name
            ),
            points=points,
            wait=True,
        )

        return len(points)

    @staticmethod
    def _resolve_owner(
        *,
        user_id: uuid.UUID | None,
        guest_session_id: uuid.UUID | None,
    ) -> tuple[str, uuid.UUID]:
        has_user = user_id is not None
        has_guest = guest_session_id is not None

        if has_user == has_guest:
            raise ValueError(
                "Document must have exactly one owner.",
            )

        if user_id is not None:
            return "user", user_id

        if guest_session_id is None:
            raise ValueError("Guest session id is missing.")

        return "guest", guest_session_id