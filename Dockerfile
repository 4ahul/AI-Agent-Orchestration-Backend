# ─── Build Stage ───────────────────────────────────────────────────
FROM python:3.12-slim as builder

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first (layer caching)
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ─── Final Stage ───────────────────────────────────────────────────
FROM python:3.12-slim

# Install runtime dependencies (only what's needed for postgres/mupdf)
RUN apt-get update && apt-get install -y \
    libpq5 \
    libmupdf-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:${PATH}"

WORKDIR /app

# Create non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser \
    && mkdir -p /app/uploads /app/logs \
    && chown -R appuser:appgroup /app

USER appuser

# Copy installed packages from builder
COPY --from=builder --chown=appuser:appgroup /root/.local /home/appuser/.local
COPY --chown=appuser:appgroup . .

EXPOSE 8000

# Healthcheck for orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]
