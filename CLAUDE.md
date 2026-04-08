# CLAUDE.md — Codebase Atlas

## Project Overview

AI-powered developer intelligence platform for public GitHub repositories. The product now has four tools:
- `RepoScout` — search and rank GitHub/GitLab repos
- `Atlas` — architecture analysis and Mermaid diagrams
- `Map` — API surface extraction and grouping
- `Review` — deep evidence-backed repo quality assessment

**Stack:** FastAPI (Python 3.11+) + Next.js 14 (TypeScript) + Anthropic Claude Sonnet 4.6 + SQLite (dev) / Supabase Postgres (prod) + Railway (backend) + Vercel (frontend) + Docker (staging/local).

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

## SRE Rules

These decisions were made deliberately — do not revert them.

- **Non-root containers** — both Docker images run as unprivileged users (`appuser` / `nextjs`). Never switch back to root.
- **Exec-form CMD/ENTRYPOINT always** — shell form swallows signals, causing force-kills on `docker stop`. Always use `["uvicorn", ...]` not `"uvicorn ..."`.
- **Healthchecks on every container** — backend probes `/health`, frontend probes `/`. Required for `depends_on: service_healthy` in compose and any future orchestration.
- **Migrations before server start** — `backend/docker-entrypoint.sh` runs `alembic upgrade head` then `exec "$@"`. Never remove this or bake migrations into the image build.
- **Secrets never in images** — env vars come from `.env.staging` on the server at runtime, never `COPY`-ed into the image. `.dockerignore` enforces this.
- **Job execution is in-process today** — Atlas/Review/public jobs use FastAPI `BackgroundTasks`, so production should run a single backend web process unless/until a real queue/worker tier is added.

---

## Development Setup

```bash
# Backend (local, no Docker)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # add ANTHROPIC_API_KEY
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (local, no Docker)
cd frontend
npm install
cp .env.local.example .env.local  # set NEXT_PUBLIC_API_URL
npm run dev

# Both services via Docker (staging stack)
cp .env.staging.example .env.staging  # fill in values
docker compose up --build
```

---

## Testing

```bash
# Backend (full pytest suite — legacy + unit + integration, no real API calls)
cd backend && pytest

# Frontend
cd frontend && npm run lint && npm run build
```

**Critical:** Backend tests use a placeholder `ANTHROPIC_API_KEY`. Never add tests that make real Anthropic API calls. All LLM-dependent code must be mocked or excluded from the test suite.

---

## Database

- **Dev:** SQLite via `aiosqlite` (default, no setup needed)
- **Staging:** SQLite (`staging.db`) — defined in `.env.staging`
- **Prod:** Postgres via `postgresql+asyncpg://` (Supabase)
- **Migrations:** Always use Alembic — never modify schema directly
- **Startup behavior:** The app no longer calls `Base.metadata.create_all()` on boot. Schema changes must come from Alembic migrations.

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

---

## Deployment

| Environment | Platform | Trigger |
|-------------|----------|---------|
| Production backend | Railway | Push to `main` (nixpacks, runs Procfile) |
| Production frontend | Vercel | Push to `main` (Next.js auto-build) |
| Staging (both) | Home server (Docker) | Push to `main` → `staging.yml` GitHub Action SSHes in and rebuilds |
| Database (prod) | Supabase | Manual: `alembic upgrade head` against prod DB URL |

Environment variables are set through Railway/Vercel/Supabase UIs for production — never committed to the repo. Staging vars live in `.env.staging` on the home server only.
Keep the backend as a single web process in production while jobs still run via `BackgroundTasks`.

---

## Docker

### Images
- `backend/Dockerfile` — 2-stage Python build (`python:3.11-slim`)
- `frontend/Dockerfile` — 3-stage Node build (`node:20-alpine`)
- Both have `.dockerignore` files — secrets and build artifacts are excluded

### Compose
`docker-compose.yml` at repo root wires both services for staging:
- Frontend waits for backend healthcheck before starting
- Both restart automatically on crash
- Secrets injected from `.env.staging` (never committed)

### Staging server one-time setup
```bash
git clone <repo> /srv/atlas
cp /srv/atlas/.env.staging.example /srv/atlas/.env.staging
# fill in real values
cd /srv/atlas && docker compose up --build -d
```

After that, every push to `main` auto-deploys via `.github/workflows/staging.yml`.

---

## CI/CD (`.github/workflows/`)

- `backend.yml` — ruff lint + pytest on pushes to `backend/**`
- `frontend.yml` — eslint + next build on pushes to `frontend/**`
- `staging.yml` — SSH deploy to home server on push to `main`
- CI uses a placeholder `ANTHROPIC_API_KEY=test` — keep it that way

### GitHub Secrets required for staging
| Secret | Value |
|--------|-------|
| `STAGING_HOST` | Home server IP or hostname |
| `STAGING_USER` | SSH username |
| `STAGING_SSH_KEY` | Private SSH key |

---

## LLM Integration

- Atlas: `summary_service.py` uses `claude-sonnet-4-6` for Mermaid + summary generation
- Map: endpoint grouping/descriptions use Claude after deterministic route extraction
- Review: `ContextReviewer` uses conditional LLM review only for evidence-gated files
- Scout: relevance scoring uses Claude after deterministic quality scoring
- Confidence scores in output reflect how much file evidence supports each inference
- When modifying prompts or tool schemas, test with a real repo end-to-end — unit tests won't catch regressions here

---

## Key Files

| File | Purpose |
|------|---------|
| `backend/app/services/analysis_pipeline.py` | Orchestrates GitHub fetch → parse → LLM analyze |
| `backend/app/services/intelligence_pipeline.py` | Deep deterministic scan + conditional LLM review + scoring |
| `backend/app/services/github_service.py` | GitHub API client, fetches repo tree + priority files |
| `backend/app/services/manifest_parser.py` | Deterministic dependency extraction (no LLM) |
| `backend/app/services/framework_detector.py` | Heuristic framework detection (no LLM) |
| `backend/app/services/summary_service.py` | All LLM calls live here |
| `backend/app/api/routes_review.py` | Review submission, polling, and report retrieval |
| `backend/app/api/routes_map.py` | API surface mapping endpoint |
| `backend/app/core/config.py` | Pydantic Settings — all env vars defined here |
| `backend/docker-entrypoint.sh` | Runs migrations then starts uvicorn |
| `docker-compose.yml` | Staging stack — wires backend + frontend |
| `frontend/app/review/page.tsx` | Review UI and report rendering |
| `frontend/lib/` | API client + shared TypeScript types |

---

## Skills

### Code quality
- `/simplify` — Use after adding features to pipeline services to catch over-engineering
- `/claude-api` — Use when modifying `summary_service.py` or any Anthropic SDK integration

### SRE / Operations
- `/staging-status` — SSH to home server, show `docker compose ps` + last 30 log lines
- `/staging-deploy` — Manually trigger staging deployment via `gh workflow run`
- `/health-check` — Compare `/health` response between production (Railway) and staging
- `/db-migrate` — Run `alembic upgrade head` against staging or production with confirmation guard

### Utilities
- `/loop` — Useful for polling Railway health checks during deployment (`/loop 5m /health`)
