import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Document(Base):
    __tablename__ = "documents"

    __table_args__ = (
        CheckConstraint(
            "("
            "user_id IS NOT NULL "
            "AND guest_session_id IS NULL"
            ") OR ("
            "user_id IS NULL "
            "AND guest_session_id IS NOT NULL"
            ")",
            name="ck_documents_exactly_one_owner",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    guest_session_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey(
            "guest_sessions.id",
            ondelete="CASCADE",
        ),
        nullable=True,
        index=True,
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
    )

    storage_key: Mapped[str] = mapped_column(
        String(1024),
        unique=True,
    )

    content_type: Mapped[str] = mapped_column(
        String(100),
    )

    size_bytes: Mapped[int] = mapped_column(
        BigInteger,
    )

    file_hash: Mapped[str] = mapped_column(
        String(64),
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default="PENDING",
        index=True,
    )

    page_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        String(1000),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )