# Migration 0024: Add Devcontainer, Audit Logs, and Embeddings

This migration adds three new tables to support the **Hybrid Model** (devcontainer generation + security).

## What Gets Created

### **1. `devcontainers` table**
- Stores generated devcontainer configurations (versioned)
- Fields: `id`, `job_id`, `org_id`, `version_number`, `config` (JSON), `features`, `repo_url`
- Unique constraint: only one version per job
- Indexes: `org_id`, `job_id`

### **2. `audit_logs` table**
- Immutable audit trail for SOC2 compliance
- Fields: `id`, `user_id`, `org_id`, `action`, `resource_type`, `resource_id`, `ip_address`, `user_agent`, `result`, `details`, `error_message`, `created_at`
- Indexes: `user_id`, `org_id`, `action`, `resource_id`, `created_at`
- Purpose: "Who did what, when?" for compliance

### **3. `analysis_embeddings` table**
- Vector embeddings for semantic search
- Fields: `id`, `job_id`, `org_id`, `chunk_type`, `chunk_text`, `embedding` (vector)
- Special: pgvector extension for similarity search
- Index: ivfflat index for efficient cosine similarity queries

---

## Prerequisites

### **Development (SQLite)**
Migration will fail gracefully on SQLite (pgvector not supported). Switch to Postgres for production features.

### **Production (Postgres)**
Ensure `pgvector` extension can be installed:

```bash
# On the database server (one-time setup)
sudo apt-get install postgresql-contrib
psql -U postgres -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Or via your cloud provider (Supabase, Railway, etc.)
# Usually available by default
```

---

## How to Run

### **Option 1: Quick Script**

```bash
cd backend
bash quick-migrate.sh
```

### **Option 2: Manual Steps**

```bash
cd backend

# 1. Check current status
alembic current

# 2. Apply migration
alembic upgrade head

# 3. Verify
alembic current

# 4. Check tables (Postgres only)
psql -c "\dt+ devcontainers audit_logs analysis_embeddings"
```

### **Option 3: Via Docker Compose**

If deploying via Docker, migration runs automatically on startup:

```bash
docker-compose up --build

# The entrypoint script runs: alembic upgrade head
```

---

## Verification

### **Check Migration Applied**

```bash
alembic current
# Output should show: 0024_add_devcontainer_audit_embeddings
```

### **Check Tables Exist**

```bash
# PostgreSQL
psql -c "SELECT tablename FROM pg_tables WHERE tablename IN ('devcontainers', 'audit_logs', 'analysis_embeddings');"

# Or via SQLAlchemy
python -c "from app.models.devcontainer import Devcontainer, AuditLog, AnalysisEmbedding; print('✅ Tables defined')"
```

### **Check Indexes**

```bash
# PostgreSQL
psql -c "SELECT indexname FROM pg_indexes WHERE tablename = 'audit_logs';"
```

---

## Rollback (If Needed)

```bash
# Downgrade to previous version
alembic downgrade -1

# Or to specific version
alembic downgrade 0023_add_queue_claim_indexes
```

---

## Next Steps

After migration:

1. ✅ **Done:** Database tables created
2. ⏳ **Next:** Import new models in your app
   ```python
   from app.models.devcontainer import Devcontainer, AuditLog, AnalysisEmbedding
   ```

3. ⏳ **Next:** Wire API routes
   ```python
   from app.api.routes import devcontainer, audit
   app.include_router(devcontainer.router)
   app.include_router(audit.router)
   ```

4. ⏳ **Next:** Implement route handlers (currently stubbed with `# TODO:`)

---

## Troubleshooting

### **Error: pgvector not available**

```
ModuleNotFoundError: No module named 'pgvector'
```

**Solution:** Install on database server (one-time):
```bash
# On your PostgreSQL server
sudo apt-get install postgresql-contrib
sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### **Error: Could not find revisions**

```
alembic.util.exc.CommandError: Can't locate revision identified by '0024_...'
```

**Solution:** Ensure file exists:
```bash
ls backend/alembic/versions/0024_*.py
```

### **Error: Revision referenced to wrong parent**

```
Requested downgrade from 0024_... to 0023_..., but ancestor 0022_... is not an ancestor of 0024_...
```

**Solution:** File is out of order. Check latest revision:
```bash
alembic history --verbose | head -5
```

---

## Migration Details (For Reference)

| Table | Rows (Initially) | Indexes | Foreign Keys |
|-------|------------------|---------|--------------|
| devcontainers | 0 | 2 | 1 (atlas_jobs) |
| audit_logs | 0 | 5 | 0 |
| analysis_embeddings | 0 | 3 | 1 (atlas_jobs) |

**Total indexes added:** 10
**Extension enabled:** pgvector
**Estimated size:** ~5 MB (empty)

---

## Related Files

- Skeleton code: `SKELETON_CODE_GUIDE.md`
- Models: `backend/app/models/devcontainer.py`
- Services: `backend/app/services/{audit_service,devcontainer_generator,embedding_service}.py`
- Routes: `backend/app/api/routes/{audit,devcontainer}.py`

---

**Questions?** See `SKELETON_CODE_GUIDE.md` for full integration guide.
