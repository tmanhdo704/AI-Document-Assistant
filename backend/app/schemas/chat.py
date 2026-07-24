"""Question, answer and citation schemas."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class QuestionRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    question: str = Field(min_length=1, max_length=2000)


class CitationResponse(BaseModel):
    index: int = Field(ge=1)
    document_id: uuid.UUID
    filename: str
    page_number: int = Field(ge=1)
    excerpt: str


class AnswerResponse(BaseModel):
    answer: str
    citations: list[CitationResponse]
    questions_remaining: int | None = Field(default=None, ge=0)
