"""
AI Agent Orchestration Backend
FastAPI application entry point.

Architecture layers (bottom-up):
  Persistence  →  Repository  →  Service  →  Agent  →  Worker  →  API
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import auth, documents, health, jobs
from app.core.config import settings
from app.core.exceptions import AppBaseError
from app.core.logging_config import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware

# Initialize structured logging before anything else
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle manager."""
    logger.info("🚀 Agent Backend starting", env=settings.APP_ENV)

    # Ensure upload directory exists
    from pathlib import Path
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)

    yield

    logger.info("Agent Backend shutting down")


# ── Application Factory ────────────────────────────────────────────────────────
app = FastAPI(
    title="AI Agent Orchestration API",
    description=(
        "Production-grade backend for PDF-to-Email AI agent pipeline. "
        "Features: CrewAI multi-agent orchestration, async PDF processing, "
        "Celery background workers, JWT auth, structured logging."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── Middleware ─────────────────────────────────────────────────────────────────
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handler ───────────────────────────────────────────────────
# No raw tracebacks returned to clients — ever.
@app.exception_handler(AppBaseError)
async def app_exception_handler(request: Request, exc: AppBaseError) -> JSONResponse:
    logger.warning("Application error", detail=exc.detail, path=request.url.path)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )

# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(jobs.router, prefix="/api/v1")


# ── Prometheus metrics ────────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    logger.info("Prometheus metrics enabled at /metrics")
except ImportError:
    logger.warning("prometheus_fastapi_instrumentator not installed, metrics disabled")
