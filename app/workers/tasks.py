"""
Celery tasks.
"""
import json
import time
from datetime import datetime, timezone
from uuid import UUID

from celery import current_task
from celery.exceptions import MaxRetriesExceededError
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app
from app.core.config import settings
from app.core.exceptions import AgentExecutionError, PDFProcessingError

logger = get_task_logger(__name__)


def _get_sync_db():
    from app.db.session import get_sync_db
    return get_sync_db()


def _log_execution(db, job_id: str, level: str, step: str, message: str) -> None:
    try:
        from app.db.models.execution_log import ExecutionLog, LogLevel
        log = ExecutionLog(
            job_id=UUID(job_id),
            level=LogLevel[level],
            step=step,
            message=message,
        )
        db.add(log)
        db.commit()
    except Exception as e:
        logger.warning(f"Failed to persist execution log: {e}")


def _save_agent_output(agent_role: str, output_text: str, job_id: str, tokens: int = 0, exec_time: float = 0.0):
    """Callback used by CrewAI to save partial results."""
    db = _get_sync_db()
    try:
        from app.db.models.agent_output import AgentOutput, AgentType
        
        # Map role string to Enum
        role_map = {
            "PDF_ANALYZER": AgentType.PDF_ANALYZER,
            "EMAIL_COMPOSER": AgentType.EMAIL_COMPOSER,
            "EMAIL_DELIVERY": AgentType.EMAIL_DELIVERY,
            "Senior PDF Document Analyst": AgentType.PDF_ANALYZER,
            "Professional Email Composer": AgentType.EMAIL_COMPOSER,
            "Email Delivery Coordinator": AgentType.EMAIL_DELIVERY,
        }
        
        agent_type = role_map.get(agent_role, AgentType.PDF_ANALYZER)
        
        # Check if output already exists (avoid duplicates on retry)
        existing = db.query(AgentOutput).filter(
            AgentOutput.job_id == UUID(job_id),
            AgentOutput.agent_type == agent_type
        ).first()
        
        if not existing:
            output = AgentOutput(
                job_id=UUID(job_id),
                agent_type=agent_type,
                raw_output=output_text,
                structured_output=_safe_parse_output(output_text),
                tokens_used=tokens if tokens > 0 else None,
                execution_time_ms=exec_time if exec_time > 0 else None,
                success=True,
            )
            db.add(output)
            db.commit()
            _log_execution(db, job_id, "INFO", f"agent.{agent_role.lower().replace(' ', '_')}", f"Agent {agent_role} finished.")
        else:
            # Update existing with metadata if it was missing
            if tokens > 0: existing.tokens_used = tokens
            if exec_time > 0: existing.execution_time_ms = exec_time
            db.commit()
            
    except Exception as e:
        logger.error(f"Failed to save partial agent output: {e}")
    finally:
        db.close()


@celery_app.task(
    bind=True,
    name="app.workers.tasks.process_document_task",
    max_retries=3,
    default_retry_delay=5,
    soft_time_limit=settings.AGENT_TIMEOUT_SECONDS + 30,
    time_limit=settings.AGENT_TIMEOUT_SECONDS + 60,
    queue="pdf",
)
def process_document_task(self, job_id: str, document_id: str, file_path: str, recipient_email: str):
    db = _get_sync_db()
    task_id = self.request.id

    try:
        from app.db.models.job import ProcessingJob, JobStatus
        from app.db.models.email_record import EmailRecord, EmailStatus
        from app.db.models.document import Document
        from app.services.pdf_service import extract_pdf_data

        job = db.query(ProcessingJob).filter(
            ProcessingJob.id == UUID(job_id),
            ProcessingJob.status.in_([JobStatus.PENDING, JobStatus.FAILED, JobStatus.PROCESSING]),
        ).with_for_update().first()

        if not job:
            return

        job.status = JobStatus.PROCESSING
        job.celery_task_id = task_id
        if not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        
        db.commit()

        _log_execution(db, job_id, "INFO", "task.start", f"Processing attempt {self.request.retries + 1}")

        # ── 1. Update Metadata ─────────────────────────────────────
        try:
            pdf_data = extract_pdf_data(file_path)
            job.metadata_ = pdf_data.get("metadata", {})
            doc = db.query(Document).filter(Document.id == UUID(document_id)).first()
            if doc:
                doc.page_count = pdf_data.get("page_count")
            db.commit()
            _log_execution(db, job_id, "INFO", "pdf.parsed", f"PDF parsed: {pdf_data.get('page_count')} pages")
        except Exception as e:
            logger.warning(f"Metadata extraction failed: {e}")

        # ── 2. Run Agent Pipeline ──────────────────────────────────
        from app.agents.crew import run_agent_pipeline

        pipeline_result = run_agent_pipeline(
            file_path=file_path,
            recipient_email=recipient_email,
            on_task_complete=lambda role, out: _save_agent_output(role, out, job_id)
        )

        # ── 3. Post-Process Metadata (Tokens/Timing) ───────────────
        usage = pipeline_result.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)
        
        # Distribute tokens roughly across tasks for visualization
        avg_tokens = total_tokens // 3 if total_tokens > 0 else 0
        
        for task_out in pipeline_result.get("tasks_output", []):
            _save_agent_output(
                agent_role=task_out["agent"],
                output_text=task_out["output"],
                job_id=job_id,
                tokens=avg_tokens,
                exec_time=pipeline_result["elapsed_ms"] / 3 # Simple estimation
            )

        # ── 4. Persist Email Record ────────────────────────────────
        delivery = pipeline_result.get("delivery_result", {})
        
        if recipient_email:
            email_rec = EmailRecord(
                job_id=UUID(job_id),
                recipient=recipient_email,
                subject=delivery.get("subject", "Document Analysis") if isinstance(delivery, dict) else "Document Analysis",
                body=delivery.get("body", "") if isinstance(delivery, dict) else str(delivery),
                status=EmailStatus.SENT if isinstance(delivery, dict) and delivery.get("success") else EmailStatus.FAILED,
                provider=settings.EMAIL_PROVIDER,
                message_id=delivery.get("message_id") if isinstance(delivery, dict) else None,
                provider_response=delivery.get("provider_response") if isinstance(delivery, dict) else None,
                sent_at=datetime.now(timezone.utc) if isinstance(delivery, dict) and delivery.get("success") else None,
            )
            db.add(email_rec)

        # ── 5. Mark COMPLETED ──────────────────────────────────────
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

        _log_execution(db, job_id, "INFO", "task.complete", "Job completed successfully")
        return {"status": "COMPLETED", "job_id": job_id}

    except (AgentExecutionError, PDFProcessingError, Exception) as exc:
        if db:
            db.rollback()
        logger.error(f"Job {job_id} failed: {exc}")
        
        _mark_job_failed(db, job_id, str(exc))
        _log_execution(db, job_id, "ERROR", "task.error", str(exc))

        try:
            countdown = 2 ** self.request.retries * 5
            raise self.retry(exc=exc, countdown=countdown)
        except MaxRetriesExceededError:
            _mark_job_dead_letter(db, job_id)
            _log_execution(db, job_id, "ERROR", "task.dead_letter", "Max retries exceeded")

    finally:
        if db:
            db.close()


def _mark_job_failed(db, job_id: str, error: str) -> None:
    from app.db.models.job import ProcessingJob, JobStatus
    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job:
        job.retry_count += 1
        job.status = JobStatus.FAILED
        job.error_message = error[:2000]
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


def _mark_job_dead_letter(db, job_id: str) -> None:
    from app.db.models.job import ProcessingJob, JobStatus
    job = db.query(ProcessingJob).filter(ProcessingJob.id == UUID(job_id)).first()
    if job:
        job.status = JobStatus.DEAD_LETTER
        job.completed_at = datetime.now(timezone.utc)
        db.commit()


def _safe_parse_output(text: str) -> dict | None:
    import re
    if not text or not isinstance(text, str):
        return {"raw": str(text)}
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"raw": text[:5000]}
