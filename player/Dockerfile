FROM python:3.13-alpine AS base

# TODO: use a backend w/o X/Wayland reqs
RUN apk add --no-cache mpv

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONPATH=/app/src

HEALTHCHECK --interval=2s --timeout=2s --start-period=5s --retries=5 \
  CMD pgrep -f 'python3 src/player.py' > /dev/null || exit 1

CMD ["python3", "src/player.py"]

FROM base AS dev
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
USER nobody

FROM base AS prod
COPY . .
USER nobody
