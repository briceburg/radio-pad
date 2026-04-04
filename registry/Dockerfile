FROM python:3.13-alpine AS base

RUN apk add --no-cache openssh-client \
  && python3 -m venv /venv \
  && chown -R nobody:nobody /venv

ENV \
  PATH="/venv/bin:$PATH" \
  PYTHONPATH=/app/src \
  PYTHONPYCACHEPREFIX=/tmp/pycache \
  REGISTRY_BIND_HOST=0.0.0.0 \
  REGISTRY_BIND_PORT=8000 \
  REGISTRY_LOG_LEVEL=info \
  REGISTRY_BACKEND_PATH=/tmp/registry-data \
  REGISTRY_AUTHZ_PATH=/tmp/registry-authz

WORKDIR /app
USER nobody

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

HEALTHCHECK --interval=2s --timeout=2s --start-period=2s --retries=5 \
  CMD wget --spider -q http://127.0.0.1:${REGISTRY_BIND_PORT}/healthz || exit 1

CMD ["bin/docker/entrypoint.sh"]

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
ENV REGISTRY_ENV=development

FROM base AS prod
COPY . .
