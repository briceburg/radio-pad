# AGENTS.md

Guidance for coding agents working in `radio-pad` (monorepo root).

## Project shape

- Monorepo containing four components: `player`, `registry`, `remote-control`, `macropad-control`.
- Docker Compose provides the local development and integration test environment.
- `compose.yaml` runs unified mode (registry serves API + switchboard in one process).
- `compose.split.yaml` runs split mode (registry and switchboard as separate services).
- `compose.prod-smoke.yaml` builds all services with `target: prod` and verifies healthchecks.
- `bin/dev` wraps local compose usage and auto-adds `compose.macropad.yaml` only
  when a macropad CDC2 data port is available, unless `RADIOPAD_MACROPAD=off` or
  `RADIOPAD_MACROPAD=required` is set.
- `bin/dev` also adds `compose.audio.yaml` when host ALSA devices are available.
- Each component has its own `bin/ci`, `README.md`, and (where applicable) `AGENTS.md`.

## Runtime and tooling

- Root `bin/check` runs component checks without starting Compose: `player`, `registry`, `remote-control`, `macropad-control`, and `tests/integration` static checks/collection.
- Root `bin/ci` runs compose-based integration tests (`tests/integration/`).
- GitHub Actions CI (`.github/workflows/ci.yml`) runs three parallel jobs:
  - `python-ci`: matrix over the three Python components plus `tests/integration` — runs each `bin/ci`.
  - `node-ci`: `remote-control` — runs `bin/ci` (prettier + vitest).
  - `integration-ci`: matrix over all three compose files — runs root `bin/ci`.
- Use `bin/check` for local all-component checks; use root `bin/ci` for compose integration.

## Agent workflow

- Use the root [README toolchain policy](README.md#toolchain-and-dependency-policy) for dependency-update scope; keep updates component-local and do not add root workspaces or lockfiles unless intentionally changing repo topology.
- Prefer starting PR work in a dedicated git worktree created from the latest
  `origin/main`, for example: `git fetch origin` then
  `git worktree add ../radio-pad-<topic> -b <topic> origin/main`.
- Before committing, check `git status --short --branch`. Do not commit PR work
  on local `main` or leave local `main` ahead of `origin/main`.
- Python components are `uv`/`pyproject.toml` driven. Use each component
  `bin/ci`; checks run through `uv run` with Ruff and mypy.
- Python projects use a 120-column Ruff format. Registry enforces strict mypy;
  player, macropad-control, and integration tests check typed code plus every
  function body without requiring runtime annotations throughout CircuitPython
  code.
- If host Python tooling, cache permissions, or platform dependencies are
  unreliable, use the component Docker runner where available:
  - `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" player ./bin/ci`
  - `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" registry ./bin/ci`
- `macropad-control` has no compose service; run `bin/ci` locally with `uv`
  installed.
- Python components keep uv environments and tool caches under ignored
  project-local `tmp/` paths. A checkout used for development or CI should be
  writable.
- Keep PR descriptions durable: describe behavior and breaking changes, but
  omit transient validation results and test counts.

## Domain conventions

- A `RadioDial` is a complete, curated collection of resolved Stations. Registry
  players may store its qualified identity (`account/radio-dial`); running players
  expose the source `radio_dial_url` from which they loaded it.
- A Station's qualified `key` is its resource identity. Its `call_sign` is the
  account-local identifier, playback selector, and current UI text. Account,
  player, and RadioDial names remain display labels. The Macropad `station_menu`
  is an ordered call-sign projection, not another RadioDial.
- Coordinate protocol changes across player, switchboard, remote control,
  Macropad, and integration tests. Do not retain legacy event or field aliases
  while the project remains in active development.

## Compose conventions

- The integration test service is `integration-tests` (profile: `tests`).
- Root `bin/ci` accepts a compose file argument; `COMPOSE_FILE` and
  `COMPOSE_PROJECT_NAME` remain available for overrides.
- Root `bin/ci` defaults registry, switchboard, and remote-control host ports to
  ephemeral values and clears `GOOGLE_CLIENT_ID` so local `.env` development
  auth and pinned ports do not affect integration CI.
- Registry and switchboard ports default to ephemeral. The remote-control dev
  server defaults to port 5173 for stable OAuth redirects. Pin them via `.env`
  (`RADIOPAD_REGISTRY_PORT`, `RADIOPAD_SWITCHBOARD_PORT`,
  `RADIOPAD_REMOTE_CONTROL_PORT`).
- Services use healthchecks; the integration test container `depends_on` with `condition: service_healthy`.
- In split mode, `remote-control` depends on both `registry` and `switchboard`
  because its dev server proxies both. `integration-tests` should depend on the
  user-facing services it exercises; avoid adding internal dependencies unless a
  test needs that service directly before those user-facing healthchecks pass.
- `bin/dev` must not mount or sync macropad firmware; use the macropad-control
  helpers explicitly before starting a hardware-backed player.

## Integration test conventions

- Tests live in `tests/integration/` and run inside a container built from `tests/integration/Dockerfile`.
- `tests/integration/bin/ci` runs static checks and collection; root `bin/ci`
  runs the tests against a Compose topology.
- They use `httpx2` for HTTP and `websockets` + `pytest-asyncio` for WebSocket tests.
- Environment variables (`REGISTRY_URL`, `SWITCHBOARD_URL`, `REMOTE_CONTROL_URL`) are injected by compose.
- Tests cover cross-service behavior that unit tests cannot: message routing through the broadcaster, auth enforcement in the running stack, and service reachability.

## Change preferences

- Keep compose files minimal — avoid duplicating service config between `compose.yaml` and `compose.split.yaml` (use `extends`). `compose.prod-smoke.yaml` is standalone (no extends) since prod images don't share dev config.
- Prefer editing component-level AGENTS.md for component-specific guidance; keep this file focused on orchestration.
- When renaming services or test directories, update all references: compose files, `bin/ci`, `README.md`, `ci.yml`.
