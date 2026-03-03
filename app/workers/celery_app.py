"""
Celery application factory.
Configured with dedicated queues for PDF and email tasks.
"""
from celery import Celery
from kombu import Exchange, Queue

from app.core.config import settings

celery_app = Celery(
    "agent_orchestrator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# ── Queue topology ─────────────────────────────────────────────────────────────
# Separate queues for priority + isolation
default_exchange = Exchange("default", type="direct")
email_exchange = Exchange("email", type="direct")
pdf_exchange = Exchange("pdf", type="direct")
dead_letter_exchange = Exchange("dead_letter", type="direct")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("pdf", pdf_exchange, routing_key="pdf"),
    Queue("email", email_exchange, routing_key="email"),
    Queue("dead_letter", dead_letter_exchange, routing_key="dead_letter"),
)
celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

# ── Task routing ───────────────────────────────────────────────────────────────
celery_app.conf.task_routes = {
    "app.workers.tasks.process_document_task": {"queue": "pdf"},
    "app.workers.tasks.send_email_task": {"queue": "email"},
}

# ── Serialization ──────────────────────────────────────────────────────────────
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# ── Retry & reliability ────────────────────────────────────────────────────────
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.task_acks_late = True           # Ack after task completes (not before)
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.task_max_retries = 3
celery_app.conf.worker_prefetch_multiplier = 1  # Fair task distribution

# ── Result expiry ──────────────────────────────────────────────────────────────
celery_app.conf.result_expires = 86400  # 24 hours

# ── Beat schedule (periodic tasks) ────────────────────────────────────────────
celery_app.conf.beat_schedule = {
    "cleanup-stale-jobs": {
        "task": "app.workers.tasks.cleanup_stale_jobs",
        "schedule": 3600.0,  # Every hour
    },
}
