from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_document_owner
from app.schemas.document import DocumentResponse
from app.services.document_service import (
    DocumentOwner,
    DocumentService,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    file: UploadFile = File(...),
    owner: DocumentOwner = Depends(get_document_owner),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    try:
        return await DocumentService(db).upload(file, owner)
    finally:
        await file.close()


@router.get(
    "",
    response_model=list[DocumentResponse],
)
def list_documents(
    owner: DocumentOwner = Depends(get_document_owner),
    db: Session = Depends(get_db),
) -> list[DocumentResponse]:
    return DocumentService(db).list_documents(owner)
