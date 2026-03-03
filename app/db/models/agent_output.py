"""Stores structured output from each agent step."""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
import enum


class AgentType(str, enum.Enum):
    PDF_ANALYZER = "PDF_ANALYZER"
    EMAIL_COMPOSER = "EMAIL_COMPOSER"
    EMAIL_DELIVERY = "EMAIL_DELIVERY"


class AgentOutput(Base):
    __tablename__ = "agent_outputs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("processing_jobs.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    agent_type: Mapped[AgentType] = mapped_column(Enum(AgentType), nullable=False)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    structured_output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(nullable=True)
    execution_time_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    success: Mapped[bool] = mapped_column(default=True, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["ProcessingJob"] = relationship("ProcessingJob", back_populates="agent_outputs")  # noqa: F821
