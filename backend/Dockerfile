# Multi-stage build for PCG Engine Backend
FROM python:3.12-slim AS builder

WORKDIR /build

# every dependency ships a prebuilt wheel for Python 3.12 (x86-64 and arm64): no compiler needed
COPY pyproject.toml .
# a virtualenv works for any user (a --user install is only found under the installing user's HOME)
RUN python -m venv /opt/venv && /opt/venv/bin/pip install --no-cache-dir .

FROM python:3.12-slim AS runner

WORKDIR /app

# Security: non-root user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

COPY --from=builder /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONUNBUFFERED=1
# LIME imports matplotlib, which needs a writable cache directory (appuser has no home)
ENV MPLCONFIGDIR=/tmp/matplotlib

COPY --chown=appuser:appgroup app/ ./app/
COPY --chown=appuser:appgroup alembic/ ./alembic/
COPY --chown=appuser:appgroup alembic.ini pyproject.toml ./

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')" || exit 1

# One worker: the explanation caches and the limit on concurrent explanations are per process
# (rate limits are shared through Redis when REDIS_URL is set).
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
