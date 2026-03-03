"""Fine-grained agent step execution logs for observability."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
import enum


class LogLevel(str, enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    level: Mapped[LogLevel] = mapped_column(Enum(LogLevel), default=LogLevel.INFO, nullable=False)
    step: Mapped[str] = mapped_column(Text, nullable=False)        # e.g. "pdf_analyzer.extract"
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["ProcessingJob"] = relationship("ProcessingJob", back_populates="execution_logs")  # noqa: F821
