FROM python:3.13-alpine AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

# TODO: use a backend w/o X/Wayland reqs
RUN apk add --no-cache mpv

ENV \
  PATH="/venv/bin:$PATH" \
  PYTHONPATH=/app/src \
  UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev && uv cache clean

HEALTHCHECK --interval=2s --timeout=2s --start-period=8s --retries=5 \
  CMD python3 src/healthcheck.py

CMD ["python3", "src/player.py"]

FROM base AS dev
RUN apk add --no-cache bash
RUN uv sync --locked && uv cache clean
USER nobody

FROM base AS prod
COPY . .
USER nobody
