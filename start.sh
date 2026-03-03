#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting AI Agent Orchestration Stack..."

# 1. Run migrations
echo "📌 Running database migrations..."
alembic upgrade head

# 2. Start Celery Worker in the background
echo "👷 Starting Celery Worker..."
celery -A app.workers.celery_app worker --loglevel=info -Q pdf,email &

# 3. Start FastAPI via Uvicorn in the foreground
echo "🌐 Starting FastAPI API..."
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
