#!/bin/sh
set -e

configure_git_key() {
    private_key=$1
    key_path=$2
    key_path_variable=$3
    ssh_dir=${HOME:-/tmp}/.ssh

    [ -n "$private_key" ] || return

    umask 077
    mkdir -p "$(dirname "$key_path")" "$ssh_dir"
    chmod 700 "$ssh_dir"
    printf '%s\n' "$private_key" > "$key_path"
    chmod 600 "$key_path"
    export "$key_path_variable=$key_path"
}

if [ "${REGISTRY_DATA_BACKEND:-}" = "git" ]; then
    configure_git_key \
        "$REGISTRY_DATA_BACKEND_GIT_SSH_PRIVATE_KEY" \
        "${REGISTRY_DATA_BACKEND_GIT_SSH_KEY_PATH:-/tmp/.ssh_deploy_key}" \
        REGISTRY_DATA_BACKEND_GIT_SSH_KEY_PATH
fi

AUTHZ_BACKEND="${REGISTRY_AUTHZ_BACKEND:-${REGISTRY_DATA_BACKEND:-local}}"
if [ "$AUTHZ_BACKEND" = "git" ]; then
    configure_git_key \
        "$REGISTRY_AUTHZ_BACKEND_GIT_SSH_PRIVATE_KEY" \
        "${REGISTRY_AUTHZ_BACKEND_GIT_SSH_KEY_PATH:-/tmp/.ssh_authz_deploy_key}" \
        REGISTRY_AUTHZ_BACKEND_GIT_SSH_KEY_PATH
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
