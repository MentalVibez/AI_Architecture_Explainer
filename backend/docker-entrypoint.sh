#!/bin/sh
set -e

# Run database migrations before starting the server.
# This prevents the backend from booting against a stale schema.
# In production (Supabase Postgres), DATABASE_URL must be set in the environment.
echo "Running database migrations..."
alembic upgrade head

echo "Starting server..."
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
