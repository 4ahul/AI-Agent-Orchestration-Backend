"""Health check endpoints for load balancers and monitoring."""
import time

import redis as redis_lib
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import settings
from app.db.session import async_engine

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    return {"status": "ok", "service": settings.APP_NAME, "env": settings.APP_ENV}


@router.get("/health/deep")
async def deep_health():
    """
    Deep health check — verifies DB and Redis connectivity.
    Used by orchestrators (Kubernetes readiness probe).
    """
    checks = {}

    # DB check
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis check
    try:
        r = redis_lib.from_url(settings.REDIS_URL, socket_timeout=2)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "checks": checks,
        "timestamp": time.time(),
    }
