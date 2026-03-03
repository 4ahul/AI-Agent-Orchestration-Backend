"""
Document upload routes.
POST /documents/upload  — Upload PDF, create job, queue processing
GET  /documents/         — List user's documents
GET  /documents/{id}    — Get single document
"""
import hashlib
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.config import settings
from app.core.exceptions import DuplicateJobError, FileSizeError, InvalidFileTypeError, PDFProcessingError
from app.core.logging_config import get_logger
from app.db.models.document import Document
from app.db.models.job import JobStatus, ProcessingJob
from app.db.models.user import User
from app.db.session import get_async_db
from app.repositories.document_repo import DocumentRepository
from app.repositories.job_repo import JobRepository
from app.services.pdf_service import compute_checksum, validate_pdf_bytes

logger = get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


class UploadResponse(BaseModel):
    document_id: str
    job_id: str
    filename: str
    file_size: int
    status: str
    message: str


class DocumentResponse(BaseModel):
    id: str
    filename: str
    original_name: str
    file_size: int
    page_count: int | None
    created_at: str

    class Config:
        from_attributes = True


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile = File(...),
    recipient_email: EmailStr = Form(...),
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a PDF and trigger the AI agent processing pipeline.
    Processing is async — use /jobs/{job_id} to poll status.
    Uses chunked streaming to handle 50MB+ files without memory bloat.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=415, detail="Only PDF files are accepted")

    # ── Prepare paths ─────────────────────────────────────────────
    upload_dir = Path(settings.UPLOAD_DIR) / str(current_user.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    safe_name = f"{uuid.uuid4().hex}.pdf"
    file_path = upload_dir / safe_name

    # ── Stream directly to disk while hashing ──────────────────────
    sha256_hash = hashlib.sha256()
    total_size = 0
    first_chunk = True

    try:
        async with aiofiles.open(str(file_path), "wb") as f:
            async for chunk in _stream_upload(file):
                total_size += len(chunk)
                
                # Validation: Size limit
                if total_size > settings.MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit")
                
                # Validation: Magic bytes (first chunk only)
                if first_chunk:
                    if not chunk.startswith(b"%PDF"):
                        raise HTTPException(status_code=422, detail="File is not a valid PDF")
                    first_chunk = False

                sha256_hash.update(chunk)
                await f.write(chunk)
    except Exception as e:
        if file_path.exists():
            os.remove(file_path)
        if isinstance(e, HTTPException):
            raise e
        logger.error("Upload failed", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save uploaded file")

    checksum = sha256_hash.hexdigest()
    doc_repo = DocumentRepository(db)
    job_repo = JobRepository(db)

    # ── Create Document record ─────────────────────────────────────
    document = Document(
        owner_id=current_user.id,
        filename=safe_name,
        original_name=file.filename,
        file_path=str(file_path),
        file_size=total_size,
        checksum=checksum,
        mime_type="application/pdf",
    )
    document = await doc_repo.create(document)

    # ── Check for duplicate active job ────────────────────────────
    if await job_repo.has_active_job(document.id):
        raise HTTPException(status_code=409, detail="This document already has an active processing job")

    # ── Create ProcessingJob ───────────────────────────────────────
    job = ProcessingJob(
        document_id=document.id,
        status=JobStatus.PENDING,
        recipient_email=str(recipient_email),
    )
    job = await job_repo.create(job)

    # ── Dispatch Celery task (non-blocking) ────────────────────────
    from app.workers.tasks import process_document_task
    process_document_task.apply_async(
        kwargs={
            "job_id": str(job.id),
            "document_id": str(document.id),
            "file_path": str(file_path),
            "recipient_email": str(recipient_email),
        },
        queue="pdf",
    )

    logger.info("Job queued", job_id=str(job.id), document_id=str(document.id), size=total_size)

    return UploadResponse(
        document_id=str(document.id),
        job_id=str(job.id),
        filename=file.filename,
        file_size=total_size,
        status="PENDING",
        message="Document uploaded successfully. Processing started in background.",
    )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    repo = DocumentRepository(db)
    docs = await repo.get_by_owner(current_user.id, limit=limit, offset=offset)
    return [
        DocumentResponse(
            id=str(d.id),
            filename=d.filename,
            original_name=d.original_name,
            file_size=d.file_size,
            page_count=d.page_count,
            created_at=d.created_at.isoformat(),
        )
        for d in docs
    ]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_user),
):
    from uuid import UUID
    repo = DocumentRepository(db)
    doc = await repo.get(UUID(document_id))
    if not doc or doc.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse(
        id=str(doc.id),
        filename=doc.filename,
        original_name=doc.original_name,
        file_size=doc.file_size,
        page_count=doc.page_count,
        created_at=doc.created_at.isoformat(),
    )


async def _stream_upload(file: UploadFile, chunk_size: int = 1024 * 1024):
    """Stream file upload in 1MB chunks to avoid memory pressure."""
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        yield chunk
