# Stage 1: install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

COPY pyproject.toml .
# Install into an explicit prefix so we can copy the layer cleanly
RUN pip install --no-cache-dir --prefix=/install .


# Stage 2: minimal runtime image
FROM python:3.11-slim

WORKDIR /app

# Non-root user — a compromised process shouldn't own the filesystem
RUN adduser --disabled-password --gecos '' appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application source
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
COPY docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Give appuser ownership of the workdir (needed for SQLite dev.db writes)
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Liveness probe — curl must be available (python:3.11-slim includes it)
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Entrypoint runs migrations then hands off to uvicorn (exec form = proper signal handling)
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
