from fastapi import APIRouter, Cookie, Depends
from sqlalchemy.orm import Session

from app.api.deps import (
    GUEST_COOKIE_NAME,
    get_db,
    get_document_owner,
    get_llm_client,
)
from app.clients.llm_client import LLMClient
from app.schemas.chat import AnswerResponse, QuestionRequest
from app.services.chat_service import ChatService
from app.services.document_service import DocumentOwner

router = APIRouter(tags=["chat"])


@router.post(
    "/ask",
    response_model=AnswerResponse,
)
def ask_documents(
    payload: QuestionRequest,
    owner: DocumentOwner = Depends(get_document_owner),
    guest_token: str | None = Cookie(
        default=None,
        alias=GUEST_COOKIE_NAME,
    ),
    db: Session = Depends(get_db),
    llm_client: LLMClient = Depends(get_llm_client),
) -> AnswerResponse:
    return ChatService(db, llm_client).ask(
        owner=owner,
        question=payload.question,
        guest_token=guest_token,
    )
