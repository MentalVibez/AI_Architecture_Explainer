# CLAUDE.md — Codebase Atlas

## Project Overview

AI-powered GitHub repository architecture analyzer. Users submit a repo URL and receive a Mermaid diagram, dependency breakdown, and dual summaries (developer + hiring manager).

**Stack:** FastAPI (Python 3.11+) + Next.js 14 (TypeScript) + Anthropic Claude Sonnet 4.6 + SQLite (dev) / Supabase Postgres (prod) + Railway (backend) + Vercel (frontend).

---

## Core Architecture Rules

### LLM is Last-Mile Only
The LLM (Claude) is used **only** for generating summaries and Mermaid diagrams. It must never be used for:
- Detecting dependencies (handled by `manifest_parser.py`)
- Identifying frameworks (handled by `framework_detector.py`)
- Fetching or interpreting raw file contents (handled by `github_service.py`)

All pre-LLM analysis is deterministic and testable. The LLM receives a structured evidence object built from verified files only — it does not invent files or services.

### Async-First
All database access uses SQLAlchemy async (`asyncpg` for Postgres, `aiosqlite` for SQLite). Never introduce synchronous DB calls into the async pipeline.

### Job-Based Processing
The API returns a `job_id` immediately. Clients poll `/api/analyze/{job_id}` for status. Any jobs stuck in `running` on server restart are automatically marked `failed`.

---

## Development Setup

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add ANTHROPIC_API_KEY
alembic upgrade head
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
cp .env.local.example .env.local  # set NEXT_PUBLIC_API_URL
npm run dev
```

---

## Testing

```bash
# Backend (32 deterministic tests — no real API calls)
cd backend && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

**Critical:** Backend tests use a placeholder `ANTHROPIC_API_KEY`. Never add tests that make real Anthropic API calls. All LLM-dependent code must be mocked or excluded from the test suite.

---

## Database

- **Dev:** SQLite via `aiosqlite` (default, no setup needed)
- **Prod:** Postgres via `postgresql+asyncpg://` (Supabase)
- **Migrations:** Always use Alembic — never modify schema directly

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Deployment

| Service  | Platform | Trigger |
|----------|----------|---------|
| Backend  | Railway  | Push to `main` (nixpacks auto-detects Python, runs Procfile) |
| Frontend | Vercel   | Push to `main` (Next.js auto-build) |
| Database | Supabase | Manual migration via `alembic upgrade head` against prod DB URL |

Environment variables are set through Railway/Vercel/Supabase UIs — never committed to the repo.

Do not suggest self-hosted alternatives for these services.

---

## LLM Integration (`summary_service.py`)

- Model: `claude-sonnet-4-6`
- Uses Claude tool-use for structured output (summaries + Mermaid diagrams)
- Confidence scores in output reflect how much file evidence supports each inference
- When modifying prompts or tool schemas, test with a real repo end-to-end — unit tests won't catch regressions here

---

## CI/CD (`.github/workflows/`)

- `backend.yml`: ruff lint + pytest on pushes to `backend/**`
- `frontend.yml`: eslint + next build on pushes to `frontend/**`
- CI uses a placeholder `ANTHROPIC_API_KEY=test` — keep it that way

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/analysis_pipeline.py` | Orchestrates GitHub fetch → parse → LLM analyze |
| `backend/app/services/github_service.py` | GitHub API client, fetches repo tree + priority files |
| `backend/app/services/manifest_parser.py` | Deterministic dependency extraction (no LLM) |
| `backend/app/services/framework_detector.py` | Heuristic framework detection (no LLM) |
| `backend/app/services/summary_service.py` | All LLM calls live here |
| `backend/app/core/config.py` | Pydantic Settings — all env vars defined here |
| `frontend/components/DiagramPanel.tsx` | Mermaid diagram renderer |
| `frontend/lib/` | API client + shared TypeScript types |

---

## Skills

- `/simplify` — Use after adding features to pipeline services to catch over-engineering
- `/claude-api` — Use when modifying `summary_service.py` or any Anthropic SDK integration
- `/loop` — Useful for polling Railway health checks during deployment (`/loop 5m /health`)
