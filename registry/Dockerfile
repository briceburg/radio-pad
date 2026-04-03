FROM python:3.13-alpine AS base

WORKDIR /app
COPY requirements.txt ./
RUN apk add --no-cache openssh-client \
  && pip install --no-cache-dir -r requirements.txt \
  && mkdir -p /app/tmp && chmod 777 /app/tmp

ENV \
  PYTHONPATH=/app/src \
  REGISTRY_BIND_HOST=0.0.0.0 \
  REGISTRY_BIND_PORT=8000 \
  REGISTRY_LOG_LEVEL=info

HEALTHCHECK --interval=2s --timeout=2s --start-period=2s --retries=5 \
  CMD wget --spider -q http://127.0.0.1:${REGISTRY_BIND_PORT}/healthz || exit 1

CMD ["bin/docker/entrypoint.sh"]

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
ENV REGISTRY_ENV=development

FROM base AS prod
COPY . .
USER nobody
