"""Email delivery records with full audit trail."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
import enum


class EmailStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class EmailRecord(Base):
    __tablename__ = "email_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    recipient: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(512), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[EmailStatus] = mapped_column(
        Enum(EmailStatus), default=EmailStatus.QUEUED, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    provider_response: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["ProcessingJob"] = relationship("ProcessingJob", back_populates="email_records")  # noqa: F821
