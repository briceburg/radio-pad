# Source after changing to the player directory; preserve deployment overrides.
export UV_CACHE_DIR="${UV_CACHE_DIR:-$PWD/tmp/.uv_cache}"
export UV_PROJECT_ENVIRONMENT="${UV_PROJECT_ENVIRONMENT:-tmp/.venv}"
export UV_TOOL_DIR="${UV_TOOL_DIR:-$PWD/tmp/.uv_tools}"
