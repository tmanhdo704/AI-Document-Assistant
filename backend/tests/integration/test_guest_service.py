from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.exceptions import ApplicationError
from app.core.security import hash_guest_token
from app.db.base import Base
from app.models.guest_session import GuestSession
from app.services.guest_service import GuestService


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


def test_create_new_guest_session(
    db_session: Session,
) -> None:
    result = GuestService(db_session).create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    guest_session = db_session.scalar(
        select(GuestSession),
    )

    assert guest_session is not None
    assert guest_session.token_hash == hash_guest_token(
        result.guest_token,
    )
    assert result.response.question_count == 0
    assert result.response.questions_remaining == 3
    assert result.response.document_count == 0
    assert result.response.documents_remaining == 1


def test_valid_cookie_reuses_existing_session(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    first_result = service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    guest_session = db_session.scalar(
        select(GuestSession),
    )

    assert guest_session is not None

    guest_session.question_count = 2
    guest_session.document_count = 1
    db_session.commit()

    second_result = service.create_or_restore_session(
        guest_token=first_result.guest_token,
        ip_address="10.0.0.50",
        user_agent="Different Browser",
        accept_language="en-US",
    )

    session_count = db_session.scalar(
        select(func.count()).select_from(GuestSession),
    )

    assert session_count == 1
    assert second_result.guest_token == first_result.guest_token
    assert second_result.response.question_count == 2
    assert second_result.response.questions_remaining == 1
    assert second_result.response.document_count == 1
    assert second_result.response.documents_remaining == 0


def test_deleted_cookie_restores_session_without_resetting_usage(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    first_result = service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    guest_session = db_session.scalar(
        select(GuestSession),
    )

    assert guest_session is not None

    guest_session.question_count = 2
    guest_session.document_count = 1
    db_session.commit()

    restored_result = service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="chrome on windows",
        accept_language="VI-vn",
    )

    session_count = db_session.scalar(
        select(func.count()).select_from(GuestSession),
    )

    assert session_count == 1
    assert restored_result.guest_token != first_result.guest_token
    assert restored_result.response.question_count == 2
    assert restored_result.response.questions_remaining == 1
    assert restored_result.response.document_count == 1
    assert restored_result.response.documents_remaining == 0

    with pytest.raises(ApplicationError) as error_info:
        service.get_usage(first_result.guest_token)

    assert error_info.value.code == "INVALID_GUEST_SESSION"

    restored_usage = service.get_usage(
        restored_result.guest_token,
    )
    assert restored_usage.question_count == 2


def test_different_identity_creates_new_session(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.21",
        user_agent="Firefox on Linux",
        accept_language="en-US",
    )

    session_count = db_session.scalar(
        select(func.count()).select_from(GuestSession),
    )

    assert session_count == 2


def test_invalid_guest_token_is_rejected(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    with pytest.raises(ApplicationError) as error_info:
        service.get_usage("invalid-token")

    assert error_info.value.code == "INVALID_GUEST_SESSION"
    assert error_info.value.status_code == 401
    
def test_guest_can_consume_only_one_document(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    result = service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    usage = service.consume_document(
        result.guest_token,
    )

    assert usage.document_count == 1
    assert usage.documents_remaining == 0

    with pytest.raises(ApplicationError) as error_info:
        service.consume_document(
            result.guest_token,
        )

    assert (
        error_info.value.code
        == "GUEST_DOCUMENT_LIMIT_REACHED"
    )
    assert error_info.value.status_code == 403

    current_usage = service.get_usage(
        result.guest_token,
    )
    assert current_usage.document_count == 1


def test_guest_can_consume_only_three_questions(
    db_session: Session,
) -> None:
    service = GuestService(db_session)

    result = service.create_or_restore_session(
        guest_token=None,
        ip_address="192.168.1.20",
        user_agent="Chrome on Windows",
        accept_language="vi-VN",
    )

    expected_remaining = [2, 1, 0]

    for remaining in expected_remaining:
        usage = service.consume_question(
            result.guest_token,
        )
        assert usage.questions_remaining == remaining

    assert usage.question_count == 3

    with pytest.raises(ApplicationError) as error_info:
        service.consume_question(
            result.guest_token,
        )

    assert (
        error_info.value.code
        == "GUEST_QUESTION_LIMIT_REACHED"
    )
    assert error_info.value.status_code == 403

    current_usage = service.get_usage(
        result.guest_token,
    )
    assert current_usage.question_count == 3