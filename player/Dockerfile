FROM python:3.13-alpine AS base

# TODO: use a backend w/o X/Wayland reqs
RUN apk add --no-cache mpv \
  && python3 -m venv /venv \
  && chown -R nobody:nobody /venv

ENV \
  PATH="/venv/bin:$PATH" \
  PYTHONPATH=/app/src \
  PYTHONPYCACHEPREFIX=/tmp/pycache

WORKDIR /app
USER nobody

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

HEALTHCHECK --interval=2s --timeout=2s --start-period=8s --retries=5 \
  CMD python3 src/healthcheck.py

CMD ["python3", "src/player.py"]

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt

FROM base AS prod
COPY . .
