#!/bin/sh
set -e

if [ "${REGISTRY_BACKEND:-}" = "git" ] && [ -n "${REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY:-}" ]; then
    mkdir -p /root/.ssh
    chmod 700 /root/.ssh

    KEY_PATH="${REGISTRY_BACKEND_GIT_SSH_KEY_PATH:-/root/.ssh/radio_pad_registry_data}"
    umask 077
    printf '%s\n' "$REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY" > "$KEY_PATH"
    chmod 600 "$KEY_PATH"
    export REGISTRY_BACKEND_GIT_SSH_KEY_PATH="$KEY_PATH"

    ssh-keyscan github.com > /root/.ssh/known_hosts
    chmod 644 /root/.ssh/known_hosts
fi

CPU_COUNT=$(bin/docker/get_cpus.sh)
UVICORN_WORKERS=${UVICORN_WORKERS:-$CPU_COUNT}

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

echo "starting uvicorn: $UVICORN_WORKERS workers ($CPU_COUNT detected cpus)" >&2
exec uvicorn registry:app \
  --host "$REGISTRY_BIND_HOST" \
  --port "$REGISTRY_BIND_PORT" \
  --workers "$UVICORN_WORKERS" \
  --log-level "$REGISTRY_LOG_LEVEL"
