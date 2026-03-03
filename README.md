# 🧠 Trinetra Labs: AI Agent Orchestration Backend

> **Senior Backend Engineering Submission**  
> A production-grade, distributed system for PDF-to-Email AI agent orchestration.  
> **Tech Stack:** FastAPI · CrewAI · LangChain · Celery · PostgreSQL · Redis · Docker

---

## 🏗️ System Architecture

```text
┌────────────────┐       ┌─────────────────┐       ┌──────────────────┐
│  CLIENT LAYER  │ ─────▶│    API LAYER    │ ─────▶│  TASK BROKER     │
│  (Swagger/UI)  │       │    (FastAPI)    │       │  (Redis/Celery)  │
└────────────────┘       └────────┬────────┘       └────────┬─────────┘
                                  │                         │
                                  ▼                         ▼
                         ┌─────────────────┐       ┌──────────────────┐
                         │   PERSISTENCE   │◀─────▶│  WORKER LAYER    │
                         │  (PostgreSQL)   │       │  (PDF/Email/AI)  │
                         └─────────────────┘       └────────┬─────────┘
                                                            │
                                                            ▼
                                                   ┌──────────────────┐
                                                   │ ORCHESTRATION    │
                                                   │ (CrewAI Agents)  │
                                                   └──────────────────┘
```

---

## 🔄 AI Agent Workflow

```text
  1. PDF UPLOAD   ──▶   2. ANALYZER AGENT   ──▶   3. COMPOSER AGENT   ──▶   4. DELIVERY AGENT
     (FastAPI)         (Data Extraction)        (Email Drafting)          (SMTP/SendGrid)
         │                     │                        │                         │
         └─────────────────────┴──────────┬─────────────┴─────────────────────────┘
                                          ▼
                                 [PostgreSQL History]
```

---

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- Groq API Key (Primary) or Google Gemini API Key
- SMTP Credentials (e.g., Gmail App Password)

### 1. Configure Environment
```bash
cp .env.example .env
# Add your GROQ_API_KEY and SMTP settings
```

### 2. Launch Services
```bash
docker-compose up --build
```
This starts FastAPI (8000), PostgreSQL (5433), Redis (6379), Celery Workers, and **Flower** (5555) for monitoring.

### 3. Run Migrations
```bash
docker-compose exec api alembic upgrade head
```

---

## 📘 Architectural Justifications

| Component | Decision | Justification |
|---|---|---|
| **FastAPI** | Async Core | Handles high-concurrency PDF uploads without blocking the event loop. |
| **Celery + Redis** | Distributed Tasks | Offloads heavy LLM orchestration (10s+) to workers, ensuring API responsiveness. |
| **PostgreSQL** | Relational Data | Ensures referential integrity between Jobs, Agent Outputs, and Execution Logs. |
| **CrewAI** | Sequential Process | Guarantees deterministic state transfer between agents, preventing circular hallucination. |
| **SELECT FOR UPDATE** | Pessimistic Locking | Prevents race conditions during concurrent document processing attempts. |

---

## 🔒 Security & Resilience

*   **File Validation:** Magic byte verification (`%PDF`) and 50MB chunked streaming upload.
*   **LLM Fallback:** Automatic chain: **Groq (Llama 3.3 70B) → Gemini 1.5 → Local Ollama**.
*   **Observability:** Unique `X-Request-ID` tracing across API, Workers, and Database logs.
*   **Resiliency:** Exponential backoff retries for LLM rate limits (429) and SMTP failures.

---

## 🚀 Deployment (Free Tier Recommendation)

For a backend with this complexity (Postgres + Redis + Workers), **Render.com** is the best free option:

1.  **PostgreSQL & Redis:** Provision via Render's free managed services.
2.  **Web Service:** Deploy the `api` (FastAPI).
3.  **Background Worker:** Deploy the `worker_pdf` as a non-HTTP service.
4.  **Environment:** Copy `.env` variables to Render's "Environment Groups".

---

## 📡 API Reference

*   **Auth:** `POST /api/v1/auth/register` | `POST /api/v1/auth/login`
*   **Upload:** `POST /api/v1/documents/upload` (Multipart)
*   **Status:** `GET /api/v1/jobs/{job_id}` (Poll for results)
*   **Logs:** `GET /api/v1/jobs/{job_id}/logs` (Real-time agent steps)
*   **Health:** `GET /health` | `GET /metrics` (Prometheus)

---

## 🛠️ Local Development

```bash
# Start Celery Worker locally
celery -A app.workers.celery_app worker --loglevel=info -Q pdf,email

# Start Flower (Monitor)
celery -A app.workers.celery_app flower --port=5555
```

---

Built with ❤️ by **Rahul**  
📧 [rahulsagar280103@gmail.com](mailto:rahulsagar280103@gmail.com)
