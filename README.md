# Codebase Atlas

AI-powered architecture analysis for public GitHub repositories.

Paste a GitHub URL and get an architecture diagram, dependency breakdown, and audience-specific summaries for developers and hiring managers.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind |
| Backend | FastAPI, Python 3.11+, SQLAlchemy, Alembic |
| LLM | Anthropic claude-sonnet-4-6 |
| Database | SQLite (dev) → Supabase Postgres (prod) |

## Quickstart

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env             # fill in ANTHROPIC_API_KEY
alembic upgrade head
uvicorn app.main:app --reload
```

Backend runs at http://localhost:8000
API docs at http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Frontend runs at http://localhost:3000

## Project structure

```
├── backend/
│   ├── app/
│   │   ├── api/          API routes
│   │   ├── core/         Config + database
│   │   ├── llm/          LLM provider abstraction (Anthropic)
│   │   ├── models/       SQLAlchemy models
│   │   ├── schemas/      Pydantic request/response schemas
│   │   ├── services/     Analysis pipeline + GitHub fetching
│   │   └── utils/        URL parsing, helpers
│   ├── alembic/          DB migrations
│   └── tests/
├── frontend/
│   ├── app/              Next.js pages (App Router)
│   ├── components/       UI components
│   └── lib/              API client + TypeScript types
```

## API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/analyze` | Submit a repo URL for analysis |
| `GET` | `/api/analyze/{job_id}` | Poll job status |
| `GET` | `/api/results/{result_id}` | Fetch completed analysis |
| `GET` | `/health` | Health check |
