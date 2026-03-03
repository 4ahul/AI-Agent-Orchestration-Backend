"""
Middleware layer:
  - Injects a unique request_id into every request
  - Adds execution time header
  - Binds request context to structlog
"""
import time
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging_config import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()

        # Bind request_id to all log records in this request context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response = None
        try:
            response = await call_next(request)
        except Exception as exc:
            logger.exception("Unhandled exception", exc_info=exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            status_code = getattr(response, "status_code", 500) if response else 500
            logger.info(
                "Request completed",
                status_code=status_code,
                duration_ms=round(elapsed_ms, 2),
            )

        if response:
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time-Ms"] = str(round(elapsed_ms, 2))
            return response
        else:
            # Fallback for when raise re-raises the exception
            # This part is technically unreachable because of 'raise' above, 
            # but it satisfies the linter/return type.
            return Response(status_code=500)
