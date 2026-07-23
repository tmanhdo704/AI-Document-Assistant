from pydantic import BaseModel, Field


class GuestUsageResponse(BaseModel):
    question_count: int = Field(ge=0)
    question_limit: int = Field(ge=1)
    questions_remaining: int = Field(ge=0)
