# AGENTS.md

Guidance for coding agents working in `radio-pad` (monorepo root).

## Project shape

- Monorepo containing four components (`player`, `registry`, `remote-control`, `macropad-control`), the Compose integration suite in `tests/integration`, and opt-in k6 workloads in `tests/load`.
- Docker Compose provides local development and integration testing; the [README](README.md#development) documents topologies, `bin/dev`, and host audio/USB integration.
- Each component and the integration suite has its own `bin/ci`; components and the load suite also have a `README.md` and (where applicable) `AGENTS.md`.

## Runtime and tooling

- Root `bin/ci` verifies formatting and runs every component's CI concurrently without starting Compose. Run cross-service validation explicitly with `bin/ci integration`.
- `tests/load/bin/run` runs manual capacity workloads against discovered Compose ports or configured remote endpoints; load tests never run in CI. Follow `tests/load/AGENTS.md` for remote-test safety and evidence conventions.
- Root `npm run format` writes repository Markdown plus supported source, configuration, workflow, and data files; `bin/ci` verifies them without writing.
- [GitHub Actions CI](.github/workflows/ci.yml) uses these entry points for component/image and Compose integration checks.
- Use component `bin/ci` scripts for targeted work, root `bin/ci` for routine repository validation, and `bin/ci integration` when changes warrant cross-service validation.

## Agent workflow

- Follow the [README toolchain policy](README.md#toolchain-and-dependency-policy) for dependency ownership and repository structure.
- Review intervening upstream changelogs when upgrading dependencies, including relevant transitive changes. Look for built-in features that can replace custom code, preserve application behavior, and explain useful fixes or simplifications in the PR.
- Prefer starting PR work in a dedicated git worktree created from the latest `origin/main`, for example: `git fetch origin` then `git worktree add ../radio-pad-<topic> -b <topic> origin/main`.
- Before committing, check `git status --short --branch`. Do not commit PR work on local `main` or leave local `main` ahead of `origin/main`.
- Python projects are `uv`/`pyproject.toml` driven. Use each project's `bin/ci`; checks run through `uv run --locked` with Ruff and mypy so stale lockfiles fail CI.
- Python projects use a 120-column Ruff format. Registry enforces strict mypy; player, macropad-control, and integration tests check typed code plus every function body without requiring runtime annotations throughout CircuitPython code.
- Every pytest project dumps all thread stacks and exits if a test, fixture setup, or teardown exceeds 30 seconds. This prevents deadlocks such as a blocked `TestClient` event-loop handshake from hanging CI or managed sandboxes; rerun outside the sandbox or in a component container rather than disabling the watchdog.
- If host Python tooling, cache permissions, or platform dependencies are unreliable, use the component Docker runner where available:
  - `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" player ./bin/ci`
  - `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" registry ./bin/ci`
- `macropad-control` has no compose service; run `bin/ci` locally with `uv` installed.
- Python components keep uv environments and tool caches under ignored project-local `tmp/` paths. A checkout used for development or CI should be writable.
- Keep PR descriptions durable: describe behavior and breaking changes, but omit transient validation results and test counts.
- Keep Markdown paragraphs and individual list items on one source line and let editors wrap them visually.

## Domain conventions

- A `RadioDial` is a complete, curated collection of resolved Stations. Registry players may store its qualified identity (`account/radio-dial`); running players expose the source `radio_dial_url` from which they loaded it.
- A Station's qualified `key` is its resource identity. Its `call_sign` is the account-local identifier, playback selector, and current UI text. Account, player, and RadioDial names remain display labels. The Macropad `station_menu` is an ordered call-sign projection, not another RadioDial.
- Coordinate protocol changes across player, switchboard, remote control, Macropad, and integration tests. Do not retain legacy event or field aliases while the project remains in active development.

## Compose conventions

- The integration test service is `integration-tests` (profile: `tests`).
- `tests/integration/bin/ci` defaults registry, switchboard, and remote-control host ports to ephemeral values and clears `GOOGLE_CLIENT_ID` so local `.env` development auth and pinned ports do not affect integration CI. `COMPOSE_PROJECT_NAME` remains available as an override.
- Registry and switchboard ports default to ephemeral. The remote-control dev server defaults to port 5173 for stable OAuth redirects. Pin them via `.env` (`RADIOPAD_REGISTRY_PORT`, `RADIOPAD_SWITCHBOARD_PORT`, `RADIOPAD_REMOTE_CONTROL_PORT`).
- Services use healthchecks; the integration test container `depends_on` with `condition: service_healthy`.
- In split mode, `remote-control` depends on both `registry` and `switchboard` because its dev server proxies both. `integration-tests` should depend on the user-facing services it exercises; avoid adding internal dependencies unless a test needs that service directly before those user-facing healthchecks pass.
- `bin/dev` must not mount or sync macropad firmware; use the macropad-control helpers explicitly before starting a hardware-backed player.

## Integration test conventions

- Tests live in `tests/integration/` and run inside a container built from `tests/integration/Dockerfile`.
- `tests/integration/bin/ci` runs static checks and collection before exercising the requested Compose files. With no arguments it runs unified, split, authenticated, and production-smoke configurations.
- They use `httpx2` for HTTP and `websockets` + `pytest-asyncio` for WebSocket tests.
- Environment variables (`REGISTRY_URL`, `SWITCHBOARD_URL`, `REMOTE_CONTROL_URL`) are injected by Compose.
- Tests cover cross-service behavior that unit tests cannot: message routing through the broadcaster, auth enforcement in the running stack, and service reachability.

## Change preferences

- Keep Compose files minimal — avoid duplicating service config between `compose.yaml` and `compose.split.yaml` (use `extends`). `compose.prod-smoke.yaml` is standalone (no extends) since prod images don't share dev config.
- Prefer editing component-level AGENTS.md for component-specific guidance; keep this file focused on orchestration.
- When renaming services or test directories, update all references: Compose files, `bin/ci`, `README.md`, and `.github/workflows/ci.yml`.
