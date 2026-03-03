"""
Job management routes.
GET  /jobs/{job_id}         — Get job status and outputs
GET  /jobs/{job_id}/logs    — Get execution logs
GET  /jobs/                 — List all user jobs
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.db.models.job import ProcessingJob
from app.db.models.user import User
from app.db.session import get_async_db
from app.repositories.job_repo import JobRepository

router = APIRouter(prefix="/jobs", tags=["Jobs"])


class LogEntry(BaseModel):
    level: str
    step: str
    message: str
    created_at: str


class AgentOutputSummary(BaseModel):
    agent_type: str
    success: bool
    execution_time_ms: float | None


class EmailRecordSummary(BaseModel):
    recipient: str
    subject: str
    status: str
    sent_at: str | None


class JobDetailResponse(BaseModel):
    id: str
    document_id: str
    status: str
    recipient_email: str | None
    retry_count: int
    error_message: str | None
    metadata: dict | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    agent_outputs: list[AgentOutputSummary]
    email_records: list[EmailRecordSummary]


@router.get("/{job_id}", response_model=JobDetailResponse)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Get detailed job status including agent outputs and email records."""
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.id == UUID(job_id))
        .options(
            selectinload(ProcessingJob.agent_outputs),
            selectinload(ProcessingJob.email_records),
            selectinload(ProcessingJob.document),
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Ownership check via document
    if str(job.document.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return JobDetailResponse(
        id=str(job.id),
        document_id=str(job.document_id),
        status=job.status.value,
        recipient_email=job.recipient_email,
        retry_count=job.retry_count,
        error_message=job.error_message,
        metadata=job.metadata_,
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        created_at=job.created_at.isoformat(),
        agent_outputs=[
            AgentOutputSummary(
                agent_type=o.agent_type.value,
                success=o.success,
                execution_time_ms=o.execution_time_ms,
            )
            for o in job.agent_outputs
        ],
        email_records=[
            EmailRecordSummary(
                recipient=e.recipient,
                subject=e.subject,
                status=e.status.value,
                sent_at=e.sent_at.isoformat() if e.sent_at else None,
            )
            for e in job.email_records
        ],
    )


@router.get("/{job_id}/logs", response_model=list[LogEntry])
async def get_job_logs(
    job_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """Return all execution log entries for a job (for observability/debugging)."""
    result = await db.execute(
        select(ProcessingJob)
        .where(ProcessingJob.id == UUID(job_id))
        .options(
            selectinload(ProcessingJob.execution_logs),
            selectinload(ProcessingJob.document),
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if str(job.document.owner_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="Access denied")

    return [
        LogEntry(
            level=log.level.value,
            step=log.step,
            message=log.message,
            created_at=log.created_at.isoformat(),
        )
        for log in job.execution_logs
    ]
