#!/bin/sh
set -e

if [ "${REGISTRY_BACKEND:-}" = "git" ] && [ -n "${REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY:-}" ]; then
    KEY_PATH="${REGISTRY_BACKEND_GIT_SSH_KEY_PATH:-/tmp/.ssh_deploy_key}"
    umask 077
    mkdir -p "$(dirname "$KEY_PATH")"
    printf '%s\n' "$REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY" > "$KEY_PATH"
    chmod 600 "$KEY_PATH"
    export REGISTRY_BACKEND_GIT_SSH_KEY_PATH="$KEY_PATH"
    export GIT_SSH_COMMAND="ssh -i $KEY_PATH -o StrictHostKeyChecking=accept-new"
fi

CPU_COUNT=$(bin/docker/get_cpus.sh)
UVICORN_WORKERS=${UVICORN_WORKERS:-$CPU_COUNT}

if [ "$#" -gt 0 ]; then
    exec "$@"
fi

UVICORN_ARGS="registry:app --host $REGISTRY_BIND_HOST --port $REGISTRY_BIND_PORT --log-level $REGISTRY_LOG_LEVEL"

if [ "${REGISTRY_ENV:-production}" = "development" ]; then
    echo "starting uvicorn in development mode (--reload)" >&2
    exec uvicorn $UVICORN_ARGS --reload
else
    echo "starting uvicorn: $UVICORN_WORKERS workers ($CPU_COUNT detected cpus)" >&2
    exec uvicorn $UVICORN_ARGS --workers "$UVICORN_WORKERS"
fi
