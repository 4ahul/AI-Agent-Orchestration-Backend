"""Import all models so Alembic autogenerate can find them."""
from app.db.models.user import User
from app.db.models.document import Document
from app.db.models.job import ProcessingJob, JobStatus
from app.db.models.agent_output import AgentOutput, AgentType
from app.db.models.email_record import EmailRecord, EmailStatus
from app.db.models.execution_log import ExecutionLog, LogLevel

__all__ = [
    "User",
    "Document",
    "ProcessingJob",
    "JobStatus",
    "AgentOutput",
    "AgentType",
    "EmailRecord",
    "EmailStatus",
    "ExecutionLog",
    "LogLevel",
]
