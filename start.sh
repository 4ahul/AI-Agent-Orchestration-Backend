#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting AI Agent Orchestration Stack (Optimized for Free Tier)..."

# 1. Run migrations
echo "📌 Running database migrations..."
alembic upgrade head

# 2. Start Celery Worker with LIMITED concurrency to save RAM
# We use --concurrency=1 because Render Free Tier has only 512MB RAM
echo "👷 Starting Celery Worker (Concurrency=1)..."
celery -A app.workers.celery_app worker --loglevel=info --concurrency=1 -Q pdf,email &

# 3. Start FastAPI via Uvicorn in the foreground
echo "🌐 Starting FastAPI API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
