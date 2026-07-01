# AGENTS.md

Guidance for coding agents working in `radio-pad/registry`.

## Project shape

- FastAPI + Pydantic service for storing and serving radio-pad registry data.
- Data is stored as JSON documents through typed datastore layers built on backend `ObjectStore` implementations.
- The project is in active development. Prefer clean replacements over compatibility shims for older clients or older internal code.
- The registry is a component of the `radio-pad` monorepo, providing the core API and real-time switchboard relay for connected players and remote controls.

## Runtime and tooling

- Python dependencies and tool settings live in `pyproject.toml`.
- Use `bin/ci` for validation. It runs `uv run mypy`,
  `uv run ruff format --check`, `uv run ruff check`, and `uv run pytest`.
- Use `bin/registry` or `uv run python src/registry.py` for local execution.
- If host Python tooling or cache permissions are unreliable, run the same
  checks inside the component image with:
  `docker compose run --rm --build --no-deps --user "$(id -u):$(id -g)" registry ./bin/ci`
- uv, pytest, Ruff, and mypy caches live under the ignored project-local
  `tmp/` directory by default. `bin/ci` also places uv's project environment
  there. A checkout used for development or CI should be writable.

## Dependency workflow

- Edit runtime and development dependencies in `pyproject.toml`.
- Regenerate `uv.lock` with `uv lock` after dependency changes.
- Do not reintroduce component-level `requirements*.txt` files.

## Datastore and backend conventions

- `REGISTRY_BACKEND_PATH` is the shared path setting for both `local` and `git` backends.
- For the Git backend, `REGISTRY_BACKEND_PATH` is the local checkout path and defaults to `tmp/data`.
- The Git-backed data repository should keep the same logical layout used by the registry API:
  - `accounts/<account>.json`
  - `accounts/<account>/players/<player>.json`
  - `accounts/<account>/stations.json`
  - `accounts/<account>/radio-dials/<radio-dial>.json`
- A Station call sign is canonical uppercase and unique within an account. RadioDials use qualified Station keys
  (`<account>/<CALL_SIGN>`) and may not repeat a call sign, even across Station-owning accounts.
- `*Spec` models are writable persisted shapes without path identity; unsuffixed models are complete resources;
  `*Summary` models exist only for genuinely reduced list/discovery projections.
- Player `radio_dial` values are qualified RadioDial identities, not URLs or backend paths.
- For Git-backed storage, prefer leaving `REGISTRY_BACKEND_PREFIX` unset so data lives at the repository root.
- The Git backend uses the system Git executable with fixed subprocess argument lists; do not add a Python Git implementation or shell command construction without a concrete need.
- `REGISTRY_BACKEND_GIT_SSH_PRIVATE_KEY` is a deployment secret used by Fly deploy setup; the runtime env var table documents `REGISTRY_BACKEND_GIT_SSH_KEY_PATH` for file-based key usage.

## Auth and seeding conventions

- Write and player-control auth verifies OIDC bearer tokens against a configured client-id allowlist; resource reads remain public.
- Private authz data is stored separately from public content data and currently uses a local backend configured by `REGISTRY_AUTHZ_PATH`.
- Checked-in seed data lives under `seed-data/`, with:
  - `store/...` for public datastore seeds
  - `auth/...` for private authz seeds
- Checked-in account-owner documents live under `seed-data/auth/accounts/<account>.json`.
- Reuse the shared `seed_from_path(...)` helper for both public content and authz seed loading so seeding behavior stays consistent across local, S3, and Git backends.
- When changing auth or control semantics, ensure any root architecture diagrams or related components (player, remote-control) are updated too.
- At transport boundaries, map expected authentication, authorization, and not-found failures to client errors; map infrastructure and unexpected failures to generic internal errors.
- Log unexpected failures with stack traces and non-sensitive resource context. Never log bearer tokens, authenticated identities, or authorization allowlists.

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

- WebSocket relay connecting players and remote controls in per-player channels keyed by `{account_id}/{player_id}`.
- Player connections provide their RadioDial source in the
  `RadioPad-Radio-Dial-Url` header; the switchboard retains that URL as the
  `radio_dial_url` event for controllers.
- Pub-sub uses an in-tree broadcast module (`src/switchboard/broadcast.py`) — no external broker.
- The in-memory backend works for single-instance and multi-instance with **path-based sticky sessions**.
- If stateless horizontal scaling is needed later, add a backend (e.g. NATS) behind the `Broadcast` interface.
- The switchboard endpoint uses `asyncio.TaskGroup` with `except*` for concurrent send/receive — tasks auto-cancel when one exits.

## Change preferences

- Prefer small shared helpers over repeated route or test boilerplate.
- Reuse existing validation and datastore helpers before adding new abstractions.
- Keep tests explicit, but centralize repeated cross-resource behavior in shared helpers or common suites when coverage is genuinely duplicated.
- Do not add broad exception swallowing or silent fallbacks.
