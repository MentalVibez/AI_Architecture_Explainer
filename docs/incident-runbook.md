# Incident Runbook — Codebase Atlas

## 1. First thing: check the ops dashboard

Call the ops endpoint **directly on the Railway backend** — do not go through the Vercel proxy
(`www.codebaseatlas.com`), which may strip custom headers.

```
GET https://aiarchitectureexplainer-production-030b.up.railway.app/api/ops/summary
Header: x-atlas-admin-key: <ADMIN_API_KEY>
```

Read the `status` field:
- `steady` — everything is idle and healthy
- `active` — jobs are running normally
- `watch` — something needs attention (read `attention_message`)

Check `workers.status`:
- `ok` — at least one fresh worker heartbeat
- `stale` — worker ran recently but heartbeat is old (> 90 s); likely crashed
- `missing` — no worker has ever registered; worker service is not deployed or not pointed at this database

Check `github.status`:
- `ok` — authenticated with a GitHub token
- `unauthenticated` — `GITHUB_TOKEN` is not set; requests are rate-limited to 60/hr per IP

---

## 2. Jobs stuck in queue (no worker)

**Symptom:** `atlas.queued > 0`, `atlas.running == 0`, `workers.status != ok`

**Fix on Railway:**
1. Go to Railway dashboard → Project → `worker` service
2. Check that the service is deployed and not crashed (View logs)
3. If it shows a crash loop: read the last error in logs, fix the cause, redeploy
4. If it shows "No deployments": the worker service was never created → deploy `python -m app.worker` as a separate Railway service using the same `backend` image and env vars

**Fix on staging (Docker):**
```bash
ssh <staging-server>
cd /srv/atlas
docker compose ps
docker compose logs worker --tail=50
docker compose restart worker
```

---

## 3. Backend is returning 503 / not healthy

**Check:**
```
curl https://www.codebaseatlas.com/ready
```

Expected: `{"status":"ok","checks":{"database":"ok"}}`

If `database` is `unreachable`:
- Check Supabase dashboard → Project health
- Check Railway → `backend` env vars → `DATABASE_URL` is set and correct
- Check Supabase connection pool limits (Free plan: 60 connections max)

If the backend process itself is down:
- Railway → `web` service → Deployments → check for crash or failed healthcheck
- View logs for the last startup error
- First verify required env vars are present on both backend services:
  `ATLAS_JWT_SECRET`, `REDIS_URL`, `SENTRY_DSN`, `DATABASE_URL`, `ANTHROPIC_API_KEY`

---

## 4. Frontend is down (Vercel)

```
curl -I https://www.codebaseatlas.com
```

- If DNS fails: check domain DNS settings in your registrar
- If Vercel returns 5xx: go to Vercel dashboard → Deployments → check latest build logs
- If the build failed after a push: check the GitHub Actions `frontend.yml` run for the error

---

## 5. Sentry shows a spike in errors

1. Open the Sentry project → Issues → sort by "First seen" or "Events"
2. Check if the error is in `backend` (FastAPI) or `frontend` (Next.js)
3. If backend: look for the `job_id` or route in the Sentry breadcrumbs, then check Railway logs for the same timestamp
4. If frontend: use the Sentry session replay (enabled on errors) to reproduce

---

## 6. GitHub rate limit hit

**Symptom:** Atlas jobs fail with `403` or `rate limit` in the error message

**Fix:**
- Go to Railway → `web` service → Variables → verify `GITHUB_TOKEN` is set
- If it is set: the token may be expired or revoked → generate a new one at GitHub → Settings → Developer settings → Personal access tokens
- Set the new token in Railway: `GITHUB_TOKEN=<new-token>` → Redeploy

---

## 7. Database restore from backup

> **Warning: this replaces all data in the target database. Do not run against production unless the production database is actually corrupted or lost.**

### Restore drill policy

- Run a restore drill at least once per quarter and after any major schema migration sequence.
- Restore into a non-production database first, never directly into production for drills.
- Record:
  - backup artifact timestamp
  - restore start and finish times
  - whether `alembic upgrade head` succeeded after restore
  - whether `/ready` returned `200`
  - whether one Atlas job and one Review job completed successfully after restore
- Current operating target:
  - `RPO`: 24 hours or less
  - `RTO`: 2 hours or less
- If a drill exceeds the target or fails validation, open a follow-up issue before the next release.

### From GitHub Actions artifact (Free plan)

1. Go to GitHub → Actions → `Database Backup` → find the most recent successful run
2. Download the artifact (`db-backup-<run-id>`) → extract the `.dump` file
3. Run the restore against a target database:

```bash
pg_restore \
  --dbname="postgresql://postgres.<ref>:<password>@db.<ref>.supabase.co:5432/postgres" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  atlas-backup-<date>.dump
```

4. After restore: run `alembic upgrade head` to apply any migrations that postdate the backup
5. Verify `GET /ready` returns healthy before allowing application traffic
6. Submit one Atlas job and one Review job as post-restore smoke validation

### From Supabase PITR (Pro plan only)

Supabase dashboard → Project → Backups → Point in Time Recovery → select timestamp → Restore

---

## 8. Emergency: roll back a Railway deployment

Railway → Service → Deployments → find the last known-good deployment → click "Redeploy"

For the database: if a bad migration was applied, run:
```bash
# From a machine with the backend venv active and DATABASE_URL set:
alembic downgrade -1
```
Then redeploy the previous backend image.

---

## 9. Railway service environment variables

| Variable | Service | Why it matters |
|----------|---------|----------------|
| `DATABASE_URL` | web, worker | Postgres connection string (Supabase pooled URL) |
| `DIRECT_URL` | web, worker | Non-pooled URL — used by Alembic migrations |
| `ANTHROPIC_API_KEY` | web, worker | Required for all LLM calls |
| `GITHUB_TOKEN` | web, worker | Avoids 60 req/hr anonymous GitHub rate limit |
| `ATLAS_JWT_SECRET` | web, worker | Required for session signing and validation; startup fails if weak or missing |
| `ADMIN_API_KEY` | web | Protects `/api/ops/summary` |
| `REDIS_URL` | web, worker | Required for shared production rate limiting; startup fails if missing |
| `SENTRY_DSN` | web, worker | Required for error capture; startup fails if missing |
| `ENVIRONMENT` | web, worker | Must be `production` |
| `CORS_ORIGINS` | web | Comma-separated list of allowed frontend origins |

---

## 10. External monitoring

- **UptimeRobot** (recommended): set up a free HTTP monitor targeting `https://www.codebaseatlas.com/live` with 5-minute polling and email/Slack alerts
- **Production smoke**: runs automatically via GitHub Actions daily at 15:00 UTC and on every push to `main`; failures auto-create a GitHub issue labeled `production-alert`
- **Ops dashboard**: `GET /api/ops/summary` — check manually before and after deploying
