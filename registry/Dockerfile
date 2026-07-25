FROM python:3.13-alpine AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

RUN apk add --no-cache git openssh-client

ENV \
  HOME=/tmp \
  PATH="/venv/bin:$PATH" \
  PYTHONPATH=/app/src \
  UV_PROJECT_ENVIRONMENT=/venv \
  REGISTRY_BIND_HOST=0.0.0.0 \
  REGISTRY_BIND_PORT=8000 \
  REGISTRY_LOG_LEVEL=info \
  REGISTRY_DATA_BACKEND_PATH=/tmp/data

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev && uv cache clean

HEALTHCHECK --interval=2s --timeout=2s --start-period=2s --retries=5 \
  CMD wget --spider -q http://127.0.0.1:${REGISTRY_BIND_PORT}/healthz || exit 1

CMD ["bin/docker/entrypoint.sh"]

FROM base AS dev
RUN uv sync --locked && uv cache clean
ENV REGISTRY_ENV=development
USER nobody

FROM base AS prod
COPY . .
USER nobody
