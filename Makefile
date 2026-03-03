.PHONY: up down build migrate worker flower logs test clean sample-pdf

# ── Docker ─────────────────────────────────────────────────────────
up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

restart:
	docker-compose down && docker-compose up -d

# ── Database ───────────────────────────────────────────────────────
migrate:
	docker-compose exec api alembic upgrade head

migration:
	docker-compose exec api alembic revision --autogenerate -m "$(name)"

# ── Development ────────────────────────────────────────────────────
dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ── Monitoring ─────────────────────────────────────────────────────
logs:
	docker-compose logs -f api

logs-worker:
	docker-compose logs -f worker_pdf worker_email

# ── Utilities ──────────────────────────────────────────────────────
sample-pdf:
	python sample/generate_sample.py

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache .mypy_cache
