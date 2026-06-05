#!/bin/bash
# Quick start for migration

cd backend

# 1. Show current status
echo "=== Current Migration Status ==="
alembic current

# 2. Apply migration
echo ""
echo "=== Applying Migration 0024 ==="
alembic upgrade head

# 3. Verify
echo ""
echo "=== Verifying Tables ==="
alembic current

# 4. Optional: Check database directly (if using Postgres)
echo ""
echo "=== Database Tables ==="
psql -c "\dt+ devcontainers audit_logs analysis_embeddings" 2>/dev/null || echo "(Skipped - PostgreSQL not available)"

echo ""
echo "✅ Migration complete!"
