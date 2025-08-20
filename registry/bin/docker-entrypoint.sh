#!/bin/sh
set -e

CPU_COUNT=$(nproc)
UVICORN_WORKERS=${UVICORN_WORKERS:-${WORKERS:-$CPU_COUNT}}

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "starting uvicorn: $UVICORN_WORKERS workers ($CPU_COUNT detected cpus)" >&2
exec uvicorn registry:app \
  --host "$REGISTRY_BIND_HOST" \
  --port "$REGISTRY_BIND_PORT" \
  --workers "$UVICORN_WORKERS"
