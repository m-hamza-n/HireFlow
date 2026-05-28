# HireFlow

An AI-powered hiring platform built with FastAPI. Companies post jobs, candidates apply, and an AI agent handles matching, screening, and communication — reducing manual recruiter work.

Built as a portfolio project to demonstrate production-grade backend architecture: async PostgreSQL, JWT auth, Celery background tasks, ChromaDB vector search, Gemini 2.0 Flash tool-use agents, WebSockets, and a simulated payment system.

---

## Screenshots

> _Add screenshots/GIFs here after recording. Suggested captures:_
> - `index.html` — landing/auth page
![alt text](image.png)
> - `recruiter.html` — recruiter console with pipeline and AI Agent tab
![alt text](image-1.png)
> - `candidate.html` — candidate portal with job board and chat
![alt text](image-2.png)
---

## Tech Stack

| Layer          | Technology                                      |
|----------------|-------------------------------------------------|
| Framework      | FastAPI                                         |
| Database       | PostgreSQL (async via asyncpg)                  |
| ORM            | SQLAlchemy 2.0 (`Mapped` / `mapped_column`)     |
| Migrations     | Alembic                                         |
| Auth           | JWT (access + refresh tokens, DB-stored)        |
| Background     | Celery + Redis                                  |
| Vector DB      | ChromaDB (Docker)                               |
| AI             | Google Gemini 2.0 Flash (tool-use + embeddings) |
| Payments       | Simulated (no external API needed)              |
| Realtime       | WebSockets (FastAPI native)                     |
| Containers     | Docker + docker-compose                         |
| Testing        | pytest + pytest-asyncio + httpx                 |
| Frontend       | Vanilla HTML/JS (no framework)                  |

---

## Features

**Auth**
- Register as candidate or recruiter
- JWT access + refresh tokens
- Refresh token stored in DB, revocable on logout

**Companies & Jobs**
- Recruiters create companies and post jobs
- Plan-gated job posting (free / basic / pro)
- Job filtering by location, type, salary range
- Semantic keyword search

**Applications**
- Candidates apply with optional cover letter
- Duplicate application prevention
- Candidate can withdraw pending applications

**AI Layer**
- Resume parsed from PDF on upload
- Candidate resume embedded into ChromaDB on upload
- Job embedded into ChromaDB on creation/update
- AI screening auto-triggered on every application (Gemini 2.0 Flash)
  - Scores 0.0–1.0, auto-sets status: shortlisted / screening / rejected
- Semantic candidate matching for recruiters (`/ai/match/{job_id}`)
- Agentic chatbot with tool-use for both candidates and recruiters

**Notifications**
- In-app notifications created on application status changes and payments
- Real-time delivery via WebSocket (`/notifications/ws?token=...`)

**Payments (Simulated)**
- No Stripe, no external API, no account needed
- `POST /payments/checkout` → creates a pending session
- `POST /payments/confirm/{session_id}` → activates plan
- Plan limits enforced on job posting

**Admin**
- Stats endpoint (total users, jobs, applications, companies)
- Paginated user and job listings

---

## Project Structure

```
hireflow/
├── main.py               # App init, router registration, lifespan (KB seed)
├── config.py             # Settings via pydantic-settings
├── database.py           # Async SQLAlchemy engine + session
├── models.py             # All ORM models (SQLAlchemy 2.0 Mapped style)
├── schemas.py            # All Pydantic schemas
├── auth.py               # JWT + password hashing
├── dependencies.py       # get_db, get_current_user, require_role, etc.
│
├── routers/              # One file per resource
├── services/             # gemini, chromadb, payment, resume parser, ws manager
├── tasks/                # Celery tasks (screening, matching, notifications)
├── knowledge_base/       # hiring_guidelines.txt — seeded into ChromaDB on startup
├── alembic/              # Migrations
├── tests/                # pytest suite
└── static/               # index.html, candidate.html, recruiter.html
```

---

## Local Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- A [Google Gemini API key](https://aistudio.google.com/app/apikey)

### 1. Clone

```bash
git clone https://github.com/m-hamza-n/hireflow.git
cd hireflow
```

### 2. Environment

```bash
cp .env.example .env
```

Edit `.env`:

```env
APP_ENV=development
SECRET_KEY=your-secret-key-minimum-32-characters

DATABASE_URL=postgresql+asyncpg://hireflow:hireflow@localhost:5432/hireflow
REDIS_URL=redis://localhost:6379/0

GEMINI_API_KEY=your-gemini-api-key

CHROMA_HOST=localhost
CHROMA_PORT=8001

ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 3. Start infrastructure

```bash
docker-compose up -d db redis chromadb
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

### 5. Run migrations

```bash
alembic upgrade head
```

### 6. Start the API

```bash
fastapi dev main.py
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs  
Frontend: http://127.0.0.1:8000/static/index.html

### 7. Start Celery worker (AI features)

In a separate terminal:

```bash
celery -A tasks.celery_app worker --loglevel=info
```

The Celery worker is required for:
- AI screening on application submit
- Resume/job embedding into ChromaDB
- Notification creation on background events

---

## API Overview

| Resource        | Key Endpoints                                              |
|-----------------|------------------------------------------------------------|
| Auth            | `POST /auth/register`, `/auth/login`, `/auth/refresh`      |
| Users           | `GET /users/me`, `POST /users/me/resume`                   |
| Companies       | `POST /companies/`, `GET /companies/{id}`                  |
| Jobs            | `POST /jobs/`, `GET /jobs/`, `GET /jobs/search`            |
| Applications    | `POST /applications/`, `GET /applications/mine`            |
| AI              | `GET /ai/match/{job_id}`, `POST /ai/chat`                  |
| Notifications   | `GET /notifications/`, `WS /notifications/ws`              |
| Payments        | `POST /payments/checkout`, `POST /payments/confirm/{id}`   |
| Admin           | `GET /admin/stats`, `GET /admin/users`                     |

Full interactive docs at `/docs`.

---

## Running Tests

```bash
pytest tests/ -v
```

Tests use a separate `hireflow_test` database. Celery tasks are mocked — no worker needed to run the test suite.

---

## Architecture Notes

| Decision | Rationale |
|---|---|
| Simulated payments | No account setup, fully testable locally — swap `payment_service.py` internals for Stripe without touching routers |
| Stateless chatbot | Client sends full message history each request — no server-side session storage |
| Celery sync sessions | Avoids asyncio-in-Celery complexity; tasks use their own sync `SessionLocal` |
| ChromaDB in Docker | Persistent vector storage with a clean HTTP interface |
| Role in JWT payload | Avoids extra DB lookup on every request for role checks |
| Single `models.py` | Full schema visible at a glance |