# AGENTS.md — Codebase Atlas

AI-powered GitHub repository architecture analyzer. Users submit a repo URL and receive a Mermaid diagram, dependency breakdown, and dual summaries (developer + hiring manager).

**Stack:** FastAPI (Python 3.11+) · Next.js 14 (TypeScript) · Anthropic Claude Sonnet 4.6 · SQLite (dev) / Supabase Postgres (prod) · Railway (backend) · Vercel (frontend)

---

## Verification Commands

Always run these before considering a change complete:

```bash
# Backend
cd backend && ruff check . && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

---

## Architecture Constraints

### LLM is Last-Mile Only
The LLM is used **only** for summaries and Mermaid diagram generation. Never add LLM calls to:
- `manifest_parser.py` — deterministic dependency extraction
- `framework_detector.py` — heuristic framework detection
- `github_service.py` — GitHub API client

All LLM calls belong in `summary_service.py`. The LLM receives a structured evidence object; it does not fetch files or invent services.

### Async Only
All database access must use SQLAlchemy async (`asyncpg` / `aiosqlite`). No synchronous DB calls.

### No Real API Calls in Tests
Backend CI uses `ANTHROPIC_API_KEY=test`. Tests must never make real Anthropic API calls. Mock or exclude all LLM-dependent code from tests.

### Database Changes via Alembic Only
Never modify schema directly. Always:
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Deployment Targets are Fixed
- Backend → Railway
- Frontend → Vercel
- Database → Supabase

Do not suggest self-hosted alternatives.

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/analysis_pipeline.py` | Main orchestration: fetch → parse → analyze |
| `backend/app/services/github_service.py` | GitHub API, repo tree + priority file fetching |
| `backend/app/services/manifest_parser.py` | Dependency extraction (no LLM) |
| `backend/app/services/framework_detector.py` | Framework detection (no LLM) |
| `backend/app/services/summary_service.py` | All LLM calls |
| `backend/app/core/config.py` | All environment variables (Pydantic Settings) |
| `frontend/lib/` | API client + shared TypeScript types |

---

## Environment

- **Dev DB:** SQLite (automatic, no setup)
- **Prod DB:** `postgresql+asyncpg://` via Supabase
- **Env vars:** Never committed — set via Railway/Vercel/Supabase UIs
- **Backend entry:** `uvicorn app.main:app` (see `Procfile`)
- **Frontend entry:** `npm run dev` / `npm run build`
