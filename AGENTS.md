# AGENTS.md

Guidance for coding agents working in `radio-pad` (monorepo root).

## Project shape

- Monorepo containing four components: `player`, `registry`, `remote-control`, `macropad-control`.
- Docker Compose provides the local development and integration test environment.
- `compose.yaml` runs unified mode (registry serves API + switchboard in one process).
- `compose.split.yaml` runs split mode (registry and switchboard as separate services).
- `compose.prod-smoke.yaml` builds all services with `target: prod` and verifies healthchecks.
- Each component has its own `bin/ci`, `README.md`, and (where applicable) `AGENTS.md`.

## Runtime and tooling

- Root `bin/ci` runs compose-based integration tests (`tests/integration/`).
- GitHub Actions CI (`.github/workflows/ci.yml`) runs three parallel jobs:
  - `python-ci`: matrix over `macropad-control`, `player`, `registry` — runs `bin/ci` + `pytest`.
  - `node-ci`: `remote-control` — runs `bin/ci` (prettier + vitest).
  - `integration-ci`: matrix over all three compose files — runs root `bin/ci`.
- There is no `bin/ci-all`. Run component checks individually or rely on CI.

## Compose conventions

- The integration test service is `integration-tests` (profile: `tests`).
- `COMPOSE_FILE` and `COMPOSE_PROJECT_NAME` control which topology runs.
- Ports default to ephemeral. Pin them via `.env` (`RADIOPAD_REGISTRY_PORT`, `RADIOPAD_REMOTE_CONTROL_PORT`).
- Services use healthchecks; the integration test container `depends_on` with `condition: service_healthy`.

## Integration test conventions

- Tests live in `tests/integration/` and run inside a container built from `tests/integration/Dockerfile`.
- They use `httpx` for HTTP and `websockets` + `pytest-asyncio` for WebSocket tests.
- Environment variables (`REGISTRY_URL`, `SWITCHBOARD_URL`, `REMOTE_CONTROL_URL`) are injected by compose.
- Tests cover cross-service behavior that unit tests cannot: message routing through the broadcaster, auth enforcement in the running stack, and service reachability.

## Change preferences

- Keep compose files minimal — avoid duplicating service config between `compose.yaml` and `compose.split.yaml` (use `extends`). `compose.prod-smoke.yaml` is standalone (no extends) since prod images don't share dev config.
- Prefer editing component-level AGENTS.md for component-specific guidance; keep this file focused on orchestration.
- When renaming services or test directories, update all references: compose files, `bin/ci`, `README.md`, `ci.yml`.
