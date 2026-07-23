"""Document API schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    original_filename: str
    content_type: str
    size_bytes: int = Field(ge=0)
    status: str
    page_count: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime