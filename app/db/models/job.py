"""
Processing job model.
Implements state machine: PENDING → PROCESSING → COMPLETED | FAILED
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"
    DEAD_LETTER = "DEAD_LETTER"


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_jobs_document_status", "document_id", "status"),
        Index("ix_jobs_celery_task", "celery_task_id"),
        Index("ix_jobs_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    celery_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING, nullable=False, index=True
    )
    recipient_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["Document"] = relationship("Document", back_populates="jobs")  # noqa: F821
    agent_outputs: Mapped[list["AgentOutput"]] = relationship(  # noqa: F821
        "AgentOutput", back_populates="job", cascade="all, delete-orphan"
    )
    email_records: Mapped[list["EmailRecord"]] = relationship(  # noqa: F821
        "EmailRecord", back_populates="job", cascade="all, delete-orphan"
    )
    execution_logs: Mapped[list["ExecutionLog"]] = relationship(  # noqa: F821
        "ExecutionLog", back_populates="job", cascade="all, delete-orphan",
        order_by="ExecutionLog.created_at",
    )

    def __repr__(self) -> str:
        return f"<ProcessingJob id={self.id} status={self.status}>"
