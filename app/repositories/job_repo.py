"""
Job repository with atomic state transitions.
Uses SELECT FOR UPDATE to prevent race conditions under concurrent load.
"""
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.job import JobStatus, ProcessingJob
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[ProcessingJob]):
    def __init__(self, db: AsyncSession):
        super().__init__(ProcessingJob, db)

    async def get_by_document(self, document_id: UUID) -> list[ProcessingJob]:
        result = await self.db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.document_id == document_id)
            .order_by(ProcessingJob.created_at.desc())
        )
        return list(result.scalars().all())

    async def has_active_job(self, document_id: UUID) -> bool:
        """Prevent duplicate processing of the same document."""
        result = await self.db.execute(
            select(ProcessingJob).where(
                and_(
                    ProcessingJob.document_id == document_id,
                    ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.PROCESSING]),
                )
            )
        )
        return result.scalar_one_or_none() is not None

    async def transition_to_processing(self, job_id: UUID, celery_task_id: str) -> ProcessingJob | None:
        """Atomic transition: PENDING → PROCESSING (with lock)."""
        result = await self.db.execute(
            select(ProcessingJob)
            .where(
                and_(
                    ProcessingJob.id == job_id,
                    ProcessingJob.status == JobStatus.PENDING,
                )
            )
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if job:
            job.status = JobStatus.PROCESSING
            job.celery_task_id = celery_task_id
            job.started_at = datetime.now(timezone.utc)
            await self.db.flush()
        return job

    async def mark_completed(self, job_id: UUID) -> ProcessingJob | None:
        job = await self.get(job_id)
        if job:
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
        return job

    async def mark_failed(
        self, job_id: UUID, error: str, increment_retry: bool = True
    ) -> ProcessingJob | None:
        result = await self.db.execute(
            select(ProcessingJob)
            .where(ProcessingJob.id == job_id)
            .with_for_update()
        )
        job = result.scalar_one_or_none()
        if job:
            if increment_retry:
                job.retry_count += 1
            if job.retry_count >= job.max_retries:
                job.status = JobStatus.DEAD_LETTER
            else:
                job.status = JobStatus.FAILED
            job.error_message = error
            job.completed_at = datetime.now(timezone.utc)
            await self.db.flush()
        return job
