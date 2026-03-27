# 🧠 Resume Optimizer AI

An intelligent resume optimization platform powered by AI. Users upload their resume and a job description, and the system analyzes, scores, and rewrites their resume to maximize ATS compatibility and relevance.

---

## 📌 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Folder Structure](#folder-structure)
- [System Design](#system-design)
- [API Design](#api-design)
- [Database Schema](#database-schema)
- [Environment Variables](#environment-variables)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Roadmap](#roadmap)

---

## Overview

Resume Optimizer AI allows users to:

- Upload a resume (PDF or DOCX)
- Paste or upload a job description
- Receive an AI-generated score and gap analysis
- Get a rewritten, optimized resume tailored to the role
- Download the optimized resume as a PDF or DOCX

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                        Client                           │
│              (Browser / Mobile App)                     │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP (port 80)
                       ▼
┌─────────────────────────────────────────────────────────┐
│                     Nginx (Reverse Proxy)               │
│         Routes /api/* → FastAPI backend                 │
│         Serves static frontend assets                   │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│               FastAPI Backend (port 8000)               │
│                                                         │
│   ┌─────────────┐   ┌──────────────┐  ┌─────────────┐  │
│   │   Auth &    │   │  Resume      │  │  AI         │  │
│   │   Users     │   │  Processing  │  │  Analysis   │  │
│   └─────────────┘   └──────────────┘  └─────────────┘  │
│                                                         │
│   ┌──────────────────────────────────────────────────┐  │
│   │              Celery Task Queue                   │  │
│   │   (Handles async AI processing jobs)             │  │
│   └──────────────────────────────────────────────────┘  │
└─────────┬────────────────┬────────────────┬─────────────┘
          │                │                │
          ▼                ▼                ▼
   ┌────────────┐   ┌────────────┐  ┌────────────────┐
   │  MariaDB   │   │   Redis    │  │  AI Provider   │
   │ (primary   │   │ (cache +   │  │ (Anthropic /   │
   │  database) │   │  queue)    │  │  OpenAI)       │
   └────────────┘   └────────────┘  └────────────────┘
```

### Request Flow

1. User uploads resume + job description via frontend
2. Nginx forwards the request to FastAPI
3. FastAPI validates, stores metadata in MariaDB, and enqueues an AI job via Celery
4. Celery worker picks up the job, calls the AI provider, processes results
5. Results are cached in Redis and stored in MariaDB
6. Frontend polls or receives a webhook when the job is complete
7. User downloads their optimized resume

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Reverse Proxy | Nginx | Routing, SSL termination, static files |
| Backend | FastAPI (Python 3.11) | REST API, business logic |
| Task Queue | Celery + Redis | Async AI job processing |
| Database | MariaDB 11 | Persistent storage |
| Cache / Broker | Redis | Job queue broker + response caching |
| AI | Anthropic Claude / OpenAI | Resume analysis and rewriting |
| File Parsing | PyPDF2, python-docx | Extract text from uploaded files |
| Auth | JWT (python-jose) + bcrypt | Secure user authentication |
| Containerization | Docker + Docker Compose | Local dev and deployment |

---

## Folder Structure

```
resume-optimizer-ai/
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── config.py                # Settings from .env
│   │   ├── database.py              # SQLAlchemy engine & session
│   │   ├── celery_app.py            # Celery instance & config
│   │   │
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── __init__.py          # makes this a Python package
│   │   │   └── user.py              # User model
│   │   │
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── __init__.py
│   │   │   └── auth.py              # Register/Login schemas
│   │   │
│   │   ├── routers/                 # API route handlers
│   │   │   ├── __init__.py
│   │   │   └── auth.py              # /api/auth/*
│   │   │
│   │   ├── services/                # Business logic layer
│   │   │   ├── __init__.py
│   │   │   └── email_service.py     # Verification email sender
│   │   │
│   │   ├── tasks/                   # Celery async tasks (future)
│   │   │   └── __init__.py
│   │   │
│   │   └── utils/                   # Helpers (future)
│   │       └── __init__.py
│   │
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                        # Static HTML/CSS/JS frontend
│   └── index.html                   # Landing page
│   └── optimize.html                # Does the optimization
│
├── nginx/
│   └── default.conf                 # Nginx routing config
│
├── db/
│   └── init.sql                     # Database schema — runs on first startup
│
├── .env                             # Environment variables (never commit)
├── .gitignore
├── docker-compose.yml
└── README.md
```

### Python Package Structure

Every subfolder inside `app/` that contains Python files needs an empty `__init__.py` file. This tells Python to treat the folder as a **package** so you can import from it.

```
# Without __init__.py
from routers.auth import router   # ❌ ImportError: No module named 'routers'

# With __init__.py
from routers.auth import router   # ✅ works
```

The root `app/` folder does NOT need `__init__.py` because it is the working directory Python starts from (set by `WORKDIR /app` in the Dockerfile), not a package being imported.

Subfolders that need `__init__.py`:

```
models/__init__.py
routers/__init__.py
schemas/__init__.py
services/__init__.py
tasks/__init__.py
utils/__init__.py
```

---

## System Design

### Authentication Flow

```
POST /api/auth/register  →  Hash password  →  Save user (unverified)
                         →  Send verification email
                         →  User clicks link → account verified

POST /api/auth/login     →  Check verified  →  Verify password
                         →  Return JWT (24hr expiry)
                         →  Frontend redirects to /dashboard.html

All protected routes     →  Validate JWT in Authorization header
```

### Resume Optimization Flow

```
POST /api/resume/upload
  │
  ├── Parse file (PDF/DOCX) → extract plain text
  ├── Store original file metadata in MariaDB
  ├── Enqueue Celery task: analyze_resume(resume_id, job_description)
  └── Return { job_id, status: "processing" }

Celery Worker:
  ├── Build AI prompt (resume text + job description)
  ├── Call AI provider API
  ├── Parse response: score, gaps, optimized resume text
  ├── Generate optimized DOCX file
  ├── Store result in MariaDB
  └── Cache result in Redis

GET /api/jobs/{job_id}
  └── Return status + download URL when complete
```

### AI Prompt Strategy

The AI is prompted to act as a professional resume consultant and return structured JSON containing:

- `ats_score` — compatibility score out of 100
- `missing_keywords` — keywords in the job description not present in the resume
- `improvements` — list of specific suggestions
- `optimized_resume` — full rewritten resume text

---

## API Design

### Auth

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new user |
| POST | `/api/auth/login` | Login and receive JWT |
| GET | `/api/auth/me` | Get current user info |

### Resume

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/resume/upload` | Upload resume + job description |
| GET | `/api/resume/` | List user's resumes |
| GET | `/api/resume/{id}` | Get specific resume details |
| DELETE | `/api/resume/{id}` | Delete a resume |

### Jobs

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/jobs/{job_id}` | Poll processing job status |
| GET | `/api/jobs/{job_id}/download` | Download optimized resume |

---

## Database Schema

### users
| Column | Type | Notes |
|---|---|---|
| id | INT PK | Auto increment |
| email | VARCHAR(255) | Unique |
| hashed_password | VARCHAR(255) | bcrypt |
| created_at | DATETIME | |

### resumes
| Column | Type | Notes |
|---|---|---|
| id | INT PK | Auto increment |
| user_id | INT FK | References users |
| original_filename | VARCHAR(255) | |
| original_text | TEXT | Extracted content |
| job_description | TEXT | Provided by user |
| ats_score | INT | 0–100 |
| optimized_text | TEXT | AI output |
| status | ENUM | pending / processing / done / failed |
| created_at | DATETIME | |

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | JWT signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT expiry duration |
| `DATABASE_URL` | Full SQLAlchemy connection string |
| `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` | Database credentials |
| `DB_ROOT_PASSWORD` | MariaDB root password (docker-compose only) |
| `REDIS_URL` | Redis connection string |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `ALLOWED_ORIGINS` | CORS allowed origins |
| `APP_ENV` | `development` or `production` |

See `.env.example` file for full configuration.

---

## Getting Started

### Prerequisites

- Docker and Docker Compose installed
- An Anthropic or OpenAI API key

### 1. Clone the repo

```bash
git clone https://github.com/your-username/resume-optimizer-ai.git
cd resume-optimizer-ai
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your API keys and secrets
```

### 3. Start all services

```bash
docker compose up --build
```

This starts:
- FastAPI backend on `http://localhost:8000`
- MariaDB on port `3306`
- Redis on port `6379`
- Nginx on `http://localhost:80`
- Celery worker

### 4. Run database migrations

```bash
docker exec -it resume_ai_backend alembic upgrade head
```

### 5. Test the API

```bash
curl http://localhost/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}'
```

---

## Development Workflow

```bash
# Start services
docker compose up

# View backend logs
docker logs -f resume_ai_backend

# View worker logs
docker logs -f resume_ai_worker

# Run a shell inside the backend container
docker exec -it resume_ai_backend bash

# Create a new Alembic migration after model changes
docker exec -it resume_ai_backend alembic revision --autogenerate -m "add column"

# Apply migrations
docker exec -it resume_ai_backend alembic upgrade head

# Stop all services
docker compose down

# Stop and delete volumes (resets the database)
docker compose down -v
```

---

## Roadmap

- [x] Project scaffolding and Docker setup
- [ ] User authentication (register / login / JWT)
- [ ] Resume upload and text extraction
- [ ] AI integration (score + optimize)
- [ ] Celery async processing
- [ ] Optimized resume download (DOCX + PDF)
- [ ] Frontend (React / Next.js)
- [ ] User dashboard with resume history
- [ ] Email notifications on job completion
- [ ] Production deployment (HTTPS, secrets management)

---

## Contributing

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Commit your changes: `git commit -m "feat: add my feature"`
3. Push and open a pull request

---

## License

MIT
