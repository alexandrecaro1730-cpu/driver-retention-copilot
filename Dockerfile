# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /build

COPY pyproject.toml README.md requirements-runtime.lock ./
COPY app ./app
RUN python -m pip install --upgrade pip && \
    python -m pip wheel --wheel-dir /wheels -r requirements-runtime.lock && \
    python -m pip wheel --wheel-dir /wheels --no-deps .

FROM python:3.13-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/app/data \
    STATE_DB_PATH=/app/var/copilot_state.sqlite3

RUN groupadd --system copilot && useradd --system --gid copilot --home /app copilot
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir --no-index --find-links=/wheels \
      driver-retention-copilot==0.1.0 && \
    rm -rf /wheels
COPY data ./data
RUN mkdir -p /app/var && chown -R copilot:copilot /app
USER copilot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["uvicorn", "app.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
