from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.guest_session import GuestSession
from app.models.user import User
from app.repositories.document_repository import (
    DocumentRepository,
)
from app.schemas.document import DocumentResponse


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(engine)

    try:
        with Session(engine) as db:
            yield db
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def create_user(
    db_session: Session,
    email: str,
) -> User:
    user = User(
        email=email,
        password_hash="password-hash",
        full_name=None,
    )

    db_session.add(user)
    db_session.flush()

    return user


def create_guest(
    db_session: Session,
    *,
    token_character: str,
    identity_character: str,
) -> GuestSession:
    guest_session = GuestSession(
        token_hash=token_character * 64,
        identity_hash=identity_character * 64,
    )

    db_session.add(guest_session)
    db_session.flush()

    return guest_session


def test_user_can_only_access_owned_document(
    db_session: Session,
) -> None:
    first_user = create_user(
        db_session,
        "first@example.com",
    )
    second_user = create_user(
        db_session,
        "second@example.com",
    )

    repository = DocumentRepository(db_session)

    document = repository.create(
        user_id=first_user.id,
        guest_session_id=None,
        original_filename="contract.pdf",
        storage_key="users/first/contract.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        file_hash="a" * 64,
    )

    db_session.commit()

    assert (
        repository.get_by_id_for_user(
            document.id,
            first_user.id,
        )
        is not None
    )
    assert (
        repository.get_by_id_for_user(
            document.id,
            second_user.id,
        )
        is None
    )


def test_guest_can_only_access_owned_document(
    db_session: Session,
) -> None:
    first_guest = create_guest(
        db_session,
        token_character="a",
        identity_character="b",
    )
    second_guest = create_guest(
        db_session,
        token_character="c",
        identity_character="d",
    )

    repository = DocumentRepository(db_session)

    document = repository.create(
        user_id=None,
        guest_session_id=first_guest.id,
        original_filename="report.pdf",
        storage_key="guests/first/report.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        file_hash="e" * 64,
    )

    db_session.commit()

    assert (
        repository.get_by_id_for_guest(
            document.id,
            first_guest.id,
        )
        is not None
    )
    assert (
        repository.get_by_id_for_guest(
            document.id,
            second_guest.id,
        )
        is None
    )


def test_document_status_and_response_schema(
    db_session: Session,
) -> None:
    user = create_user(
        db_session,
        "user@example.com",
    )

    repository = DocumentRepository(db_session)

    document = repository.create(
        user_id=user.id,
        guest_session_id=None,
        original_filename="manual.pdf",
        storage_key="users/user/manual.pdf",
        content_type="application/pdf",
        size_bytes=4096,
        file_hash="f" * 64,
    )

    repository.update_status(
        document,
        status="READY",
        page_count=4,
    )

    db_session.commit()
    db_session.refresh(document)

    response = DocumentResponse.model_validate(document)
    response_data = response.model_dump()

    assert response.status == "READY"
    assert response.page_count == 4
    assert "storage_key" not in response_data
    assert "file_hash" not in response_data
    assert "user_id" not in response_data
    assert "guest_session_id" not in response_data