# Stage 1: install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml .
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Install into an explicit prefix so we can copy the layer cleanly
RUN pip install --no-cache-dir --prefix=/install .


# Stage 2: minimal runtime image
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Non-root user — a compromised process shouldn't own the filesystem
RUN adduser --disabled-password --gecos '' appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY docker-entrypoint.sh .
COPY railway-start.sh .
RUN chmod +x docker-entrypoint.sh railway-start.sh

# Give appuser ownership of the workdir and mounted data path
# (needed for SQLite dev/staging DB writes)
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Liveness probe without extra OS packages
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import os; from urllib.request import urlopen; urlopen(f\"http://127.0.0.1:{os.environ.get('PORT', '8000')}/live\", timeout=3)"

# Entrypoint runs migrations then hands off to uvicorn (exec form = proper signal handling)
ENTRYPOINT ["./docker-entrypoint.sh"]
