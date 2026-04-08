# Deployment Guide

Codebase Atlas deploys across three services:

| Service | Platform | Purpose |
|---------|----------|---------|
| Database | [Supabase](https://supabase.com) | Postgres (free tier) |
| Backend API | [Railway](https://railway.app) | FastAPI + background tasks |
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

## 2. Railway — Backend API

### Initial deploy

1. Go to [railway.app](https://railway.app) → **New Project → Deploy from GitHub repo**
2. Select the `AI_Architecture_Explainer` repo
3. Railway auto-detects the `backend/` directory — set the **Root Directory** to `backend`
4. Railway uses `railway.toml` and `Procfile` already in the repo — no extra config needed
5. Keep the backend at a single web instance for now. Atlas/Review/public jobs still run via in-process `BackgroundTasks`, not an external queue.

### Environment variables

In Railway → your service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | Your key from [console.anthropic.com](https://console.anthropic.com) |
| `GITHUB_TOKEN` | A GitHub PAT with `public_repo` scope (increases API rate limit) |
| `DATABASE_URL` | The `postgresql+asyncpg://...` URI from Supabase |
| `ENVIRONMENT` | `production` |
| `CORS_ORIGINS` | Your Vercel frontend URL, e.g. `https://codebase-atlas.vercel.app` |

> After adding variables, Railway will redeploy automatically.

### Verify

- Visit `https://your-railway-app.up.railway.app/health` — should return `{"status": "ok"}`
- Check the Railway deploy logs for any startup errors
- Confirm the deploy log includes `alembic upgrade head` before `uvicorn`
- Confirm `/health` reports `"execution_mode": "in_process_background_tasks"`

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
| `NEXT_PUBLIC_API_URL` | `https://your-railway-app.up.railway.app` | Production, Preview, Development |
| `API_URL` | `https://your-railway-app.up.railway.app` | Production, Preview |

> `NEXT_PUBLIC_API_URL` is exposed to the browser (client components).
> `API_URL` is used only by Next.js server components and can point to an internal URL if needed.

### Verify

- Visit your Vercel URL → homepage should load
- Submit a public GitHub repo URL → job should transition `queued → running → completed`

---

## 4. Updating CORS after deploy

Once you have the Vercel URL, update the Railway env var:

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

# Frontend (separate terminal)
cd frontend
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).
