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

## 📈 Scaling Plan & Performance Engineering

To handle production-level traffic (1,000+ PDFs/hour), the system follows a horizontal scaling strategy:

1.  **Worker Auto-scaling:** Celery workers can be scaled independently of the API layer. Using a Kubernetes HPA (Horizontal Pod Autoscaler), we can scale worker replicas based on Redis queue length or CPU/Memory usage.
2.  **Database Strategy:** Transition from a single PostgreSQL instance to a managed RDS with **PgBouncer** for efficient connection pooling. Read-replicas can be introduced to offload analytical queries.
3.  **API Layer:** Run multiple Uvicorn instances behind an Nginx or ALB load balancer. Use `Gunicorn` with `UvicornWorker` for better process management.
4.  **Redis Cluster:** For high-throughput task brokering and caching, migrate to a Redis Cluster or a managed service like AWS ElastiCache.
5.  **Multi-Model Orchestration:** Distribute LLM requests across multiple API keys or providers (Groq, Gemini, OpenAI) to bypass individual rate limits.

### 🔍 Identified Bottlenecks
*   **LLM API Rate Limits:** The primary bottleneck is the TPM (Tokens Per Minute) and RPM (Requests Per Minute) limits enforced by free-tier LLM providers like Groq and Gemini.
*   **PDF Parsing (CPU-Bound):** Extracting text from heavy, image-rich, or 50MB+ PDFs consumes significant CPU time, potentially starving worker threads.
*   **Sequential Agent Execution:** CrewAI currently processes the Analyzer → Composer → Delivery steps sequentially, blocking the worker for the entire 3-step duration instead of yielding.

### 🚀 Behavior at 10x Load
Under a simulated 10x load spike:
1.  **API Resilience:** The FastAPI layer will remain responsive, accepting files asynchronously, saving them to disk (or S3), and rapidly enqueueing Jobs in Redis without blocking.
2.  **Queue Backpressure:** Redis will buffer the sudden influx of tasks. Celery workers will continue pulling tasks at their maximum concurrency (`CELERY_CONCURRENCY`). Job states will correctly remain `PENDING` until a worker is free.
3.  **Rate Limit Exhaustion:** As workers hit LLM providers concurrently, 429 Too Many Requests errors will trigger. The system's exponential backoff will automatically re-queue the tasks, effectively spreading the workload over a longer duration.

### ⚖️ Trade-offs Made
*   **Pessimistic vs. Optimistic Locking:** Chose pessimistic locking (`SELECT FOR UPDATE`) for job state transitions to guarantee safety over slightly higher throughput, given the low write-volume of state changes relative to the long processing time of LLMs.
*   **Sequential vs. Parallel Agents:** Kept agent orchestration sequential to prevent circular hallucination and guarantee deterministic data flow from Analyzer to Composer, at the cost of higher latency per job.
*   **Disk Storage vs. Memory:** PDFs are saved to disk (`./uploads`) and streamed during processing rather than kept in RAM, trading disk I/O latency for improved memory stability under concurrent load.

---

## ⚠️ Known Limitations

*   **File Size:** Maximum PDF upload size is capped at **50MB** (configurable in `.env`).
*   **LLM Context Window:** Long PDFs (>100 pages) may exceed the context window of Llama3 or Gemini. Large documents are currently chunked, but summary coherence may vary.
*   **Rate Limiting:** Free-tier API keys (Groq/Gemini) have strict rate limits (RPM/TPM). High-concurrency jobs may trigger 429 errors.
*   **SMTP Constraints:** Single-sender SMTP accounts (e.g., Gmail) may flag high-volume automated emails as spam.
*   **Sequential Processing:** CrewAI's current configuration is sequential; parallel agent execution is not yet implemented for single-job tasks.

---

## 📄 Sample PDF & Testing

The repository includes a script to generate a standard business report for testing the end-to-end pipeline.

### Generate Sample
```bash
# Ensure reportlab is installed
pip install reportlab
# Generate the PDF
python sample/generate_sample.py
```
This creates `sample/sample_report.pdf` which contains financial data and contact emails suitable for the Analyzer and Composer agents.

### Expected Output
See `sample/expected_output.json` for the structure of the JSON response after the agents finish processing.

---

Built with ❤️ by **Rahul**  
📧 [rahulsagar280103@gmail.com](mailto:rahulsagar280103@gmail.com)

