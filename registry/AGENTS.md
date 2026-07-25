# AGENTS.md

Guidance for coding agents working in `radio-pad/registry`.

## Project shape

- FastAPI + Pydantic component that serves the RadioPad API and real-time switchboard.
- Data is stored as JSON documents through typed datastore layers built on backend `ObjectStore` implementations.
- The project is in active development. Prefer clean replacements over compatibility shims for older clients or older internal code.

## Runtime and tooling

- Python dependencies and tool settings live in `pyproject.toml`.
- Use `bin/ci` for validation. It runs mypy, Ruff format/lint checks, and pytest through `uv run --locked`.
- Use `bin/registry` or `uv run python src/registry.py` for local execution.
- If host Python tooling or cache permissions are unreliable, run the same checks inside the component image with: `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" registry ./bin/ci`
- uv, pytest, Ruff, and mypy caches live under the ignored project-local `tmp/` directory by default. `bin/ci` also places uv's project environment there. A checkout used for development or CI should be writable.

## Dependency workflow

- Edit runtime and development dependencies in `pyproject.toml`.
- Regenerate `uv.lock` with `uv lock` after dependency changes.
- Do not reintroduce component-level `requirements*.txt` files.

## Datastore and backend conventions

- `REGISTRY_DATA_BACKEND_*` configures registry data; `REGISTRY_AUTHZ_BACKEND_*` configures authz data only where it differs.
- `REGISTRY_DATA_BACKEND_PATH` is the data path setting for both `local` and `git` backends.
- For the Git backend, `REGISTRY_DATA_BACKEND_PATH` is the local checkout path and defaults to `tmp/data`.
- Every backend stores registry documents under `data/` and authz documents under `authz/`. A Git-backed data repository therefore uses:
  - `data/accounts/<account>.json`
  - `data/accounts/<account>/players/<player>.json`
  - `data/accounts/<account>/stations.json`
  - `data/accounts/<account>/radio-dials/<radio-dial>.json`
- A Station call sign is canonical uppercase and unique within an account. RadioDials use qualified Station keys (`<account>/<CALL_SIGN>`) and may not repeat a call sign, even across Station-owning accounts.
- `*Spec` models are writable persisted shapes without path identity; unsuffixed models are complete resources; `*Summary` models exist only for genuinely reduced list/discovery projections.
- Player `radio_dial` values are qualified RadioDial identities, not URLs or backend paths.
- The Git backend uses the system Git executable with fixed subprocess argument lists; do not add a Python Git implementation or shell command construction without a concrete need.
- `REGISTRY_DATA_BACKEND_GIT_SSH_PRIVATE_KEY` is a deployment secret used by Fly deploy setup; the runtime env var table documents `REGISTRY_DATA_BACKEND_GIT_SSH_KEY_PATH` for file-based key usage.

## Auth and seeding conventions

- Write and player-control auth verifies OIDC bearer tokens against a configured client-id allowlist; registry API reads are currently unauthenticated.
- Authz data uses the same local, S3, and Git implementations as registry data. It inherits the data backend's physical configuration when the backend types match; `REGISTRY_AUTHZ_BACKEND_*` values configure only what differs.
- Authz data may share the registry backend unless that backend is public; authz documents must remain private.
- Keep OIDC authentication under `src/auth/` and persisted authorization models and stores under `src/authz/`.
- Checked-in seed data lives under `seed-data/`, with:
  - `data/...` for registry seeds
  - `authz/...` for authz seeds
- Account-owner seeds initialize local authz; update persistent owner documents through their configured private backend.
- Reuse the shared `seed_from_path(...)` helper for both registry and authz seed loading so seeding behavior stays consistent across local, S3, and Git backends.
- When changing auth or control semantics, ensure any root architecture diagrams or related components (player, remote-control) are updated too.
- At transport boundaries, map expected authentication, authz, and not-found failures to client errors; map infrastructure and unexpected failures to generic internal errors.
- Log unexpected failures with stack traces and non-sensitive resource context. Never log bearer tokens, authenticated identities, or authz allowlists.

## Testing conventions

- Default `pytest` excludes performance tests via `-m 'not performance'`.
- Run functional tests directly with:
  - `pytest tests/functional -m 'not performance'`
- Run performance tests directly with:
  - `pytest tests/functional/test_performance.py -m performance`
  - add `--log-cli-level=INFO` to see timing output
- Current performance tests are observational; they log timings and assert result shapes, but they do not enforce numeric thresholds.

## Switchboard and broadcast

- WebSocket relay connecting players and remote controls in per-player channels keyed by `{account_id}/{player_id}`.
- Player connections provide their RadioDial source in the `RadioPad-Radio-Dial-Url` header; the switchboard retains that URL as the `radio_dial_url` event for controllers.
- Pub-sub uses an in-tree broadcast module (`src/switchboard/broadcast.py`) — no external broker.
- The in-memory backend works for single-instance and multi-instance with **path-based sticky sessions**.
- If stateless horizontal scaling is needed later, add a backend (e.g. NATS) behind the `Broadcast` interface.
- The switchboard endpoint uses `asyncio.TaskGroup` with `except*` for concurrent send/receive — tasks auto-cancel when one exits.

## Change preferences

- Prefer small shared helpers over repeated route or test boilerplate.
- Reuse existing validation and datastore helpers before adding new abstractions.
- Keep tests explicit, but centralize repeated cross-resource behavior in shared helpers or common suites when coverage is genuinely duplicated.
- Do not add broad exception swallowing or silent fallbacks.
