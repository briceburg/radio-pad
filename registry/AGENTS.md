# AGENTS.md

Guidance for coding agents working in `radio-pad/registry`.

## Project shape

- FastAPI + Pydantic service for storing and serving radio-pad registry data.
- Data is stored as JSON documents through typed datastore layers built on backend `ObjectStore` implementations.
- The project is in active development. Prefer clean replacements over compatibility shims for older clients or older internal code.
- The registry is a component of the `radio-pad` monorepo, providing the core API and real-time switchboard relay for connected players and remote controls.

## Runtime and tooling

- The checked-in project target is Python `3.13`, even if the local environment is newer.
- Run commands from an activated virtual environment: `source venv/bin/activate`.
- `bin/ci` runs static checks (mypy, ruff) and `pytest`.

## Dependency workflow

- Edit runtime dependencies in `requirements-latest.txt` first.
- Re-freeze runtime dependencies into `requirements.txt`:
  ```sh
  python -m venv /tmp/freeze-venv
  /tmp/freeze-venv/bin/pip install -r requirements-latest.txt
  /tmp/freeze-venv/bin/pip freeze > requirements.txt
  rm -rf /tmp/freeze-venv
  ```
- Development-only tools belong in `requirements-dev.txt`.

## Datastore and backend conventions

- `REGISTRY_BACKEND_PATH` is the shared path setting for both `local` and `git` backends.
- For the Git backend, `REGISTRY_BACKEND_PATH` is the local checkout path and defaults to `tmp/data`.
- The Git-backed data repository should keep the same logical layout used by the registry API:
  - `accounts/<account>.json`
  - `accounts/<account>/players/<player>.json`
  - `accounts/<account>/presets/<preset>.json`
  - `presets/<preset>.json`
- For Git-backed storage, prefer leaving `REGISTRY_BACKEND_PREFIX` unset so data lives at the repository root.
- `REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY` is a deployment secret used by Fly deploy setup; the runtime env var table documents `REGISTRY_BACKEND_GIT_SSH_KEY_PATH` for file-based key usage.

## Auth and seeding conventions

- Write-route auth verifies OIDC bearer tokens against a configured client-id allowlist; reads remain public.
- Private authz data is stored separately from public content data and currently uses a local backend configured by `REGISTRY_AUTHZ_PATH`.
- Checked-in seed data lives under `seed-data/`, with:
  - `store/...` for public datastore seeds
  - `auth/...` for private authz seeds
- Checked-in authz seed documents live under `seed-data/auth/`, with:
  - `global-admins.json`
  - `accounts/<account>.json`
- Reuse the shared `seed_from_path(...)` helper for both public content and authz seed loading so seeding behavior stays consistent across local, S3, and Git backends.
- When changing auth or control semantics, ensure any root architecture diagrams or related components (player, remote-control) are updated too.

## Testing conventions

- CI runs `bin/ci`, which executes static checks followed by `pytest`.
- Default `pytest` excludes performance tests via `-m 'not performance'`.
- Run functional tests directly with:
  - `pytest tests/functional -m 'not performance'`
- Run performance tests directly with:
  - `pytest tests/functional/test_performance.py -m performance`
  - add `--log-cli-level=INFO` to see timing output
- Current performance tests are observational; they log timings and assert result shapes, but they do not enforce numeric thresholds.

## Switchboard and broadcast

- The switchboard is a WebSocket relay that connects players and remote controls in per-player channels keyed by `{account_id}/{player_id}`.
- Pub-sub uses an in-tree broadcast module (`src/switchboard/broadcast.py`) — no external broker dependency.
- The in-memory backend is sufficient for single-instance and for multi-instance deployments with **path-based sticky sessions** (all connections for a given `/{account_id}/{player_id}` path land on the same process).
- If stateless horizontal scaling is needed later, add a backend (e.g. NATS) behind the existing `Broadcast` interface.
- The deprecated `run_until_first_complete` from Starlette was replaced with `asyncio.wait(..., return_when=asyncio.FIRST_COMPLETED)` in the switchboard endpoint to properly propagate and catch single `WebSocketDisconnect` exceptions.

## Change preferences

- Prefer small shared helpers over repeated route or test boilerplate.
- Reuse existing validation and datastore helpers before adding new abstractions.
- Keep tests explicit, but centralize repeated cross-resource behavior in shared helpers or common suites when coverage is genuinely duplicated.
- Do not add broad exception swallowing or silent fallbacks.
