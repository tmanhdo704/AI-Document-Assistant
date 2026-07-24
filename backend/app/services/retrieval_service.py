"""Lightweight local retrieval used before the vector index is introduced."""

import re
import unicodedata
import uuid
from collections import Counter
from dataclasses import dataclass

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
