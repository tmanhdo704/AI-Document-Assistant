import re
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass, replace

from app.clients.embedding_client import EmbeddingClient
from app.clients.qdrant_client import (
    OwnerType,
    QdrantVectorClient,
    get_qdrant_client,
)
from app.core.config import get_settings

TOKEN_PATTERN = re.compile(r"\w+", re.UNICODE)
STOP_WORDS = {
    "a",
    "an",
    "and",
    "các",
    "cho",
    "của",
    "document",
    "gì",
    "hãy",
    "is",
    "là",
    "những",
    "này",
    "of",
    "the",
    "tài",
    "to",
    "trong",
    "và",
    "về",
}
OVERVIEW_MARKERS = (
    "tài liệu này nói về",
    "tài liệu nói về",
    "chủ đề chính",
    "nội dung chính",
    "mục đích của",
    "tóm tắt tài liệu",
    "tổng quan tài liệu",
    "what is this document about",
    "main topic",
    "purpose of",
    "summarize the document",
    "document overview",
)
MULTI_DOCUMENT_OVERVIEW_MARKERS = (
    "các tài liệu",
    "những tài liệu",
    "tất cả tài liệu",
    "these documents",
    "all documents",
)
AMBIGUOUS_DOCUMENT_MARKERS = (
    "tài liệu này",
    "tài liệu đó",
    "this document",
    "that document",
)
MINIMUM_CANDIDATE_LIMIT = 20
MAX_CHUNKS_PER_PAGE = 2
MAX_NEIGHBOR_SEEDS = 3
NEIGHBOR_SCORE_PENALTY = 0.01
LEXICAL_RERANK_WEIGHT = 0.03
DOCUMENT_RELEVANCE_MARGIN = 0.05


@dataclass(frozen=True)
class SourceChunk:
    document_id: uuid.UUID
    filename: str
    page_number: int
    text: str


@dataclass(frozen=True)
class RetrievedChunk:
    document_id: uuid.UUID
    filename: str
    page_number: int
    text: str
    score: float
    chunk_index: int = 0


class RetrievalService:
    def retrieve(
        self,
        question: str,
        chunks: tuple[SourceChunk, ...],
        *,
        limit: int = 6,
    ) -> tuple[RetrievedChunk, ...]:
        if limit <= 0 or not chunks:
            return ()

        query_tokens = self._tokens(question)
        scored: list[tuple[float, int, SourceChunk]] = []

        for index, chunk in enumerate(chunks):
            chunk_tokens = Counter(self._tokens(chunk.text))
            overlap_score = sum(
                min(chunk_tokens[token], query_count)
                for token, query_count in Counter(query_tokens).items()
            )
            coverage = (
                overlap_score / max(len(set(query_tokens)), 1)
                if query_tokens
                else 0.0
            )
            scored.append((coverage, index, chunk))

        ranked = sorted(
            scored,
            key=lambda item: (-item[0], item[1]),
        )
        selected = ranked[:limit]

        return tuple(
            RetrievedChunk(
                document_id=chunk.document_id,
                filename=chunk.filename,
                page_number=chunk.page_number,
                text=chunk.text,
                score=score,
            )
            for score, _, chunk in selected
        )

    @staticmethod
    def _tokens(text: str) -> list[str]:
        normalized = unicodedata.normalize("NFKC", text).casefold()
        return [
            token
            for token in TOKEN_PATTERN.findall(normalized)
            if len(token) > 1 and token not in STOP_WORDS
        ]


class VectorRetrievalService:
    """Retrieve and diversify relevant chunks with local embeddings."""

    def __init__(
        self,
        embedding_client: EmbeddingClient | None = None,
        qdrant_client: QdrantVectorClient | None = None,
    ) -> None:
        self.settings = get_settings()
        self.embedding_client = embedding_client or EmbeddingClient()
        self.qdrant = qdrant_client or get_qdrant_client()

    def retrieve(
        self,
        question: str,
        *,
        user_id: uuid.UUID | None = None,
        guest_session_id: uuid.UUID | None = None,
        limit: int | None = None,
    ) -> tuple[RetrievedChunk, ...]:
        """Find relevant chunks across all documents owned by one owner."""
        owner_type, owner_id = self._resolve_owner(
            user_id=user_id,
            guest_session_id=guest_session_id,
        )

        result_limit = (
            limit
            if limit is not None
            else self.settings.retrieval_top_k
        )

        if result_limit <= 0:
            return ()

        if self.is_overview_question(question):
            return self._retrieve_overview(
                question,
                owner_type=owner_type,
                owner_id=owner_id,
                limit=result_limit,
            )

        query_vector = self.embedding_client.embed_query(question)

        points = self.qdrant.search(
            query_vector=query_vector,
            owner_type=owner_type,
            owner_id=owner_id,
            limit=max(
                MINIMUM_CANDIDATE_LIMIT,
                result_limit * 3,
            ),
        )

        candidates = tuple(
            chunk
            for point in points
            if (chunk := self._point_to_chunk(point)) is not None
        )
        reranked_candidates = self._rerank_candidates(
            question,
            candidates,
        )
        relevant_candidates = self._filter_relevant_documents(
            question,
            reranked_candidates,
        )
        seeds = self._select_diverse_chunks(
            relevant_candidates,
            limit=result_limit,
        )

        return self._expand_neighbors(
            seeds,
            owner_type=owner_type,
            owner_id=owner_id,
            limit=result_limit,
        )

    @classmethod
    def is_overview_question(cls, question: str) -> bool:
        normalized = cls._normalize_question(question)
        return any(
            marker in normalized
            for marker in OVERVIEW_MARKERS
        )

    @classmethod
    def requires_document_clarification(
        cls,
        question: str,
        *,
        document_count: int,
    ) -> bool:
        if document_count <= 1 or not cls.is_overview_question(question):
            return False

        normalized = cls._normalize_question(question)
        asks_for_multiple_documents = any(
            marker in normalized
            for marker in MULTI_DOCUMENT_OVERVIEW_MARKERS
        )
        uses_ambiguous_reference = any(
            marker in normalized
            for marker in AMBIGUOUS_DOCUMENT_MARKERS
        )

        return (
            uses_ambiguous_reference
            and not asks_for_multiple_documents
        )

    def _retrieve_overview(
        self,
        question: str,
        *,
        owner_type: OwnerType,
        owner_id: uuid.UUID,
        limit: int,
    ) -> tuple[RetrievedChunk, ...]:
        opening_points = self.qdrant.get_opening_chunks(
            owner_type=owner_type,
            owner_id=owner_id,
            limit=max(limit, 10),
        )
        opening_chunks = self._rerank_candidates(
            question,
            tuple(
                chunk
                for point in opening_points
                if (
                    chunk := self._point_to_chunk(
                        point,
                        default_score=1.0,
                    )
                )
                is not None
            ),
        )

        if len(opening_chunks) != 1 or limit == 1:
            return tuple(opening_chunks[:limit])

        opening = opening_chunks[0]
        neighbor_points = self.qdrant.get_chunks(
            owner_type=owner_type,
            owner_id=owner_id,
            references=(
                (opening.document_id, opening.chunk_index + 1),
            ),
        )
        next_chunks = tuple(
            chunk
            for point in neighbor_points
            if (
                chunk := self._point_to_chunk(
                    point,
                    default_score=0.99,
                )
            )
            is not None
        )

        return (opening, *next_chunks)[:limit]

    @staticmethod
    def _rerank_candidates(
        question: str,
        candidates: tuple[RetrievedChunk, ...],
    ) -> tuple[RetrievedChunk, ...]:
        question_tokens = set(RetrievalService._tokens(question))
        reranked: list[RetrievedChunk] = []

        for candidate in candidates:
            candidate_tokens = set(
                RetrievalService._tokens(
                    f"{candidate.filename} {candidate.text}",
                ),
            )
            lexical_coverage = (
                len(question_tokens & candidate_tokens)
                / len(question_tokens)
                if question_tokens
                else 0.0
            )
            reranked.append(
                replace(
                    candidate,
                    score=(
                        candidate.score
                        + lexical_coverage * LEXICAL_RERANK_WEIGHT
                    ),
                ),
            )

        return tuple(
            sorted(
                reranked,
                key=lambda chunk: (
                    -chunk.score,
                    str(chunk.document_id),
                    chunk.chunk_index,
                ),
            ),
        )

    @staticmethod
    def _select_diverse_chunks(
        candidates: tuple[RetrievedChunk, ...],
        *,
        limit: int,
    ) -> tuple[RetrievedChunk, ...]:
        selected: list[RetrievedChunk] = []
        page_counts: Counter[tuple[uuid.UUID, int]] = Counter()
        document_counts: Counter[uuid.UUID] = Counter()
        fingerprints: set[tuple[uuid.UUID, str]] = set()
        max_chunks_per_document = max(3, limit // 2)

        for candidate in candidates:
            page_key = (
                candidate.document_id,
                candidate.page_number,
            )
            fingerprint = (
                candidate.document_id,
                " ".join(candidate.text.split()).casefold(),
            )

            if fingerprint in fingerprints:
                continue
            if page_counts[page_key] >= MAX_CHUNKS_PER_PAGE:
                continue
            if (
                document_counts[candidate.document_id]
                >= max_chunks_per_document
            ):
                continue

            selected.append(candidate)
            fingerprints.add(fingerprint)
            page_counts[page_key] += 1
            document_counts[candidate.document_id] += 1

            if len(selected) >= limit:
                break

        return tuple(selected)

    @staticmethod
    def _filter_relevant_documents(
        question: str,
        candidates: tuple[RetrievedChunk, ...],
    ) -> tuple[RetrievedChunk, ...]:
        if not candidates:
            return ()

        document_scores: dict[uuid.UUID, float] = {}
        document_filenames: dict[uuid.UUID, str] = {}

        for candidate in candidates:
            document_scores[candidate.document_id] = max(
                candidate.score,
                document_scores.get(
                    candidate.document_id,
                    float("-inf"),
                ),
            )
            document_filenames[candidate.document_id] = (
                candidate.filename
            )

        best_score = max(document_scores.values())
        question_tokens = set(RetrievalService._tokens(question))
        explicitly_named_documents = {
            document_id
            for document_id, filename in document_filenames.items()
            if question_tokens
            & set(RetrievalService._tokens(filename))
        }
        relevant_document_ids = {
            document_id
            for document_id, score in document_scores.items()
            if (
                score >= best_score - DOCUMENT_RELEVANCE_MARGIN
                or document_id in explicitly_named_documents
            )
        }

        return tuple(
            candidate
            for candidate in candidates
            if candidate.document_id in relevant_document_ids
        )

    def _expand_neighbors(
        self,
        seeds: tuple[RetrievedChunk, ...],
        *,
        owner_type: OwnerType,
        owner_id: uuid.UUID,
        limit: int,
    ) -> tuple[RetrievedChunk, ...]:
        if not seeds:
            return ()

        neighbor_seed_list: list[RetrievedChunk] = []
        seeded_documents: set[uuid.UUID] = set()

        for seed in seeds:
            if seed.document_id in seeded_documents:
                continue

            neighbor_seed_list.append(seed)
            seeded_documents.add(seed.document_id)

            if len(neighbor_seed_list) >= MAX_NEIGHBOR_SEEDS:
                break

        for seed in seeds:
            if seed in neighbor_seed_list:
                continue

            neighbor_seed_list.append(seed)

            if len(neighbor_seed_list) >= MAX_NEIGHBOR_SEEDS:
                break

        neighbor_seeds = tuple(neighbor_seed_list)
        references = tuple(
            (
                seed.document_id,
                neighbor_index,
            )
            for seed in neighbor_seeds
            for neighbor_index in range(
                max(seed.chunk_index - 1, 0),
                seed.chunk_index + 2,
            )
        )
        neighbor_points = self.qdrant.get_chunks(
            owner_type=owner_type,
            owner_id=owner_id,
            references=references,
        )
        neighbor_scores: dict[tuple[uuid.UUID, int], float] = {}

        for seed in neighbor_seeds:
            for neighbor_index in range(
                max(seed.chunk_index - 1, 0),
                seed.chunk_index + 2,
            ):
                distance = abs(neighbor_index - seed.chunk_index)
                key = (seed.document_id, neighbor_index)
                score = (
                    seed.score
                    - distance * NEIGHBOR_SCORE_PENALTY
                )
                neighbor_scores[key] = max(
                    score,
                    neighbor_scores.get(key, float("-inf")),
                )

        chunks_by_key = {
            (seed.document_id, seed.chunk_index): seed
            for seed in seeds
        }

        for point in neighbor_points:
            payload = getattr(point, "payload", None)

            if not isinstance(payload, dict):
                continue

            try:
                key = (
                    uuid.UUID(str(payload["document_id"])),
                    int(payload["chunk_index"]),
                )
            except (KeyError, TypeError, ValueError):
                continue

            chunk = self._point_to_chunk(
                point,
                default_score=neighbor_scores.get(key),
            )

            if chunk is not None:
                chunks_by_key[key] = chunk

        ordered: list[RetrievedChunk] = []
        seen: set[tuple[uuid.UUID, int]] = set()

        for seed in neighbor_seeds:
            for neighbor_index in range(
                max(seed.chunk_index - 1, 0),
                seed.chunk_index + 2,
            ):
                key = (seed.document_id, neighbor_index)
                chunk = chunks_by_key.get(key)

                if chunk is not None and key not in seen:
                    ordered.append(chunk)
                    seen.add(key)

        for seed in seeds:
            key = (seed.document_id, seed.chunk_index)

            if key not in seen:
                ordered.append(seed)
                seen.add(key)

        return tuple(ordered[:limit])

    @staticmethod
    def _resolve_owner(
        *,
        user_id: uuid.UUID | None,
        guest_session_id: uuid.UUID | None,
    ) -> tuple[OwnerType, uuid.UUID]:
        has_user = user_id is not None
        has_guest = guest_session_id is not None

        if has_user == has_guest:
            raise ValueError(
                "Retrieval requires exactly one owner.",
            )

        if user_id is not None:
            return "user", user_id

        if guest_session_id is None:
            raise ValueError("Guest session id is missing.")

        return "guest", guest_session_id

    @staticmethod
    def _point_to_chunk(
        point: object,
        *,
        default_score: float | None = None,
    ) -> RetrievedChunk | None:
        payload = getattr(point, "payload", None)
        score = getattr(point, "score", None)

        if score is None:
            score = default_score

        if not isinstance(payload, dict):
            return None

        try:
            document_id = uuid.UUID(str(payload["document_id"]))
            filename = payload["filename"]
            page_number = payload["page_number"]
            chunk_index = payload.get("chunk_index", 0)
            text = payload["text"]
        except (KeyError, TypeError, ValueError):
            return None

        if not isinstance(filename, str) or not filename:
            return None

        if (
            not isinstance(page_number, int)
            or isinstance(page_number, bool)
            or page_number < 1
        ):
            return None

        if (
            not isinstance(chunk_index, int)
            or isinstance(chunk_index, bool)
            or chunk_index < 0
        ):
            return None

        if not isinstance(text, str) or not text:
            return None

        if (
            not isinstance(score, (int, float))
            or isinstance(score, bool)
        ):
            return None

        return RetrievedChunk(
            document_id=document_id,
            filename=filename,
            page_number=page_number,
            text=text,
            score=float(score),
            chunk_index=chunk_index,
        )

    @staticmethod
    def _normalize_question(question: str) -> str:
        return unicodedata.normalize(
            "NFKC",
            question,
        ).casefold()
