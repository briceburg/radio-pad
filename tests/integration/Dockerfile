FROM python:3.13-alpine
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

ENV \
  PATH="/venv/bin:$PATH" \
  UV_PROJECT_ENVIRONMENT=/venv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev && uv cache clean

USER nobody
