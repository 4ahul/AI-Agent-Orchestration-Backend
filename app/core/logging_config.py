"""
Structured logging setup using structlog.
Every log entry carries: request_id, timestamp, level, event, caller info.
"""
import logging
import sys

import structlog
from structlog.types import EventDict, Processor

from app.core.config import settings


def add_app_context(logger: logging.Logger, method: str, event_dict: EventDict) -> EventDict:
    event_dict["app"] = settings.APP_NAME
    event_dict["env"] = settings.APP_ENV
    return event_dict


def configure_logging() -> None:
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_app_context,
    ]

    if settings.APP_ENV == "production":
        # JSON output in production
        renderer = structlog.processors.JSONRenderer()
    else:
        # Human-readable in development
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO if settings.is_production else logging.DEBUG)

    # Silence noisy libraries
    for lib in ["uvicorn.access", "httpx", "httpcore"]:
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
