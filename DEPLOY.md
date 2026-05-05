# Deployment Guide

For the exact live rollout order and smoke-test commands, use
[docs/PRODUCTION_ROLLOUT.md](docs/PRODUCTION_ROLLOUT.md).

Codebase Atlas deploys across three services:

| Service | Platform | Purpose |
|---------|----------|---------|
| Database | [Supabase](https://supabase.com) | Postgres (free tier) |
| Backend web | [Railway](https://railway.app) | FastAPI API service |
| Backend worker | [Railway](https://railway.app) | Queue worker for Atlas / Review / public jobs |
| Frontend | [Vercel](https://vercel.com) | Next.js App Router |

---

## 1. Supabase — Database

1. Go to [supabase.com](https://supabase.com) → **New project**
2. Choose a name (e.g. `codebase-atlas`) and a strong database password — **save this password**
3. Wait for the project to provision (~1 min)
4. Go to **Settings → Database** and copy the **Connection string** (URI format).
   - Switch the pooler mode to **Session** (not Transaction) for compatibility with SQLAlchemy
   - The URI looks like: `postgresql://postgres:[PASSWORD]@db.[REF].supabase.co:5432/postgres`
5. Replace `postgresql://` with `postgresql+asyncpg://` — this is your `DATABASE_URL`

> The backend runs `alembic upgrade head` on startup in Railway and Docker. For a fresh database, the schema comes from Alembic migrations, not `create_all()`.

---

## 2. Railway — Backend web + worker

### Initial deploy

1. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
2. Select the `AI_Architecture_Explainer` repo
3. Create the first service as the **web** service:
   - set **Root Directory** to `backend`
   - use the repo `Procfile` or set the start command to `sh ./docker-entrypoint.sh`
4. Duplicate that service or create a second backend service from the same repo for the **worker**:
   - set **Root Directory** to `backend`
   - set the start command to `sh ./docker-entrypoint.sh python -m app.worker`
5. Point both backend services at the same environment variables and database
6. Deploy the web and worker together. The shared entrypoint runs `alembic upgrade head` before either process starts.

### Environment variables

In Railway → both backend services → **Variables**, add:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | Your key from [console.anthropic.com](https://console.anthropic.com) |
| `GITHUB_TOKEN` | A GitHub PAT with `public_repo` scope (increases API rate limit) |
| `DATABASE_URL` | The `postgresql+asyncpg://...` URI from Supabase |
| `ENVIRONMENT` | `production` |
| `CORS_ORIGINS` | Your Vercel frontend URL, e.g. `https://codebase-atlas.vercel.app` |
| `WORKER_POLL_INTERVAL_SECONDS` | Optional — default `2.0` |
| `WORKER_STALE_JOB_SECONDS` | Optional — default `1800` |
| `WORKER_QUEUE_ORDER` | Optional — default `atlas,review` |
| `WORKER_ATLAS_CONCURRENCY` | Optional — default `2` |
| `WORKER_REVIEW_CONCURRENCY` | Optional — default `1` |
| `WORKER_QUEUE_GUARD_SECONDS` | Optional — default `180`; queued jobs older than this are failed with a user-facing reason |
| `OPS_WORKER_QUEUE_ALERT_SECONDS` | Optional — default `120` |

> After adding variables, Railway will redeploy automatically.

### Verify

- Visit `https://your-railway-web.up.railway.app/health` — should return `{"status": "ok"}`
- Check both Railway deploy logs for startup errors
- Confirm both services log `alembic upgrade head` before starting
- Confirm `/health` reports `"execution_mode": "database_worker_queue"`
- Confirm `/api/ops/summary` becomes `active` during jobs and does not show an attention message during normal processing
- Stop the worker temporarily and confirm `/api/ops/summary` flips to `watch` with a worker backlog message

--- 

## 3. Vercel — Frontend

### Initial deploy

1. Go to [vercel.com](https://vercel.com) → **New Project → Import Git Repository**
2. Select `AI_Architecture_Explainer`
3. Set **Root Directory** to `frontend`
4. Framework preset should auto-detect as **Next.js**

### Environment variables

In Vercel → your project → **Settings → Environment Variables**, add:

| Variable | Value | Environment |
|----------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://your-railway-web.up.railway.app` | Production, Preview, Development |
| `API_URL` | `https://your-railway-web.up.railway.app` | Production, Preview |

> `NEXT_PUBLIC_API_URL` is exposed to the browser (client components).
> `API_URL` is used only by Next.js server components and can point to an internal URL if needed.

### Verify

- Visit your Vercel URL → homepage should load
- Submit a public GitHub repo URL → Atlas job should transition `queued → running → completed`
- Submit a Review job and confirm it also drains through the worker

--- 

## 4. Updating CORS after deploy

Once you have the Vercel URL, update the Railway env var on both backend services:

```
CORS_ORIGINS=https://your-app.vercel.app
```

If you use a custom domain, add it comma-separated:

```
CORS_ORIGINS=https://your-app.vercel.app,https://yourdomain.com
```

---

## Local development

```bash
# Backend
cd backend
cp .env.example .env          # fill in ANTHROPIC_API_KEY and optionally GITHUB_TOKEN
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload

# Backend worker (separate terminal)
python -m app.worker

# Frontend (separate terminal)
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).
