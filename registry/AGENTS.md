# AGENTS.md

Guidance for coding agents working in `radio-pad/registry`.

## Project shape

- FastAPI + Pydantic component that serves the RadioPad API and real-time switchboard.
- Data is stored as JSON documents through typed datastore layers built on backend `ObjectStore` implementations.
- The project is in active development. Prefer clean replacements over compatibility shims for older clients or older internal code.

## Runtime and tooling

- Use `bin/ci` for validation. It runs mypy, Ruff format/lint checks, and pytest through `uv run --locked`.
- Use `bin/registry` for local execution. It and the container entrypoint delegate server settings to `bin/serve`, which uses Uvicorn's standard CLI and WebSocket backend selection.
- Dependency updates and standalone test commands are documented in the [README](README.md#development); inherited Python tooling and container fallbacks are in the [root guidance](../AGENTS.md#agent-workflow).

## Datastore and backend conventions

- Storage configuration and defaults live in the [README](README.md#data-and-authz-storage).
- Every backend stores registry documents under `data/` and authz documents under `authz/`. A Git-backed data repository therefore uses:
  - `data/accounts/<account>.json`
  - `data/accounts/<account>/players/<player>.json`
  - `data/accounts/<account>/stations.json`
  - `data/accounts/<account>/radio-dials/<radio-dial>.json`
- A Station call sign is canonical uppercase and unique within an account. RadioDials use qualified Station keys (`<account>/<CALL_SIGN>`) and may not repeat a call sign, even across Station-owning accounts.
- `*Spec` models are writable persisted shapes without path identity; unsuffixed models are complete resources; `*Summary` models exist only for genuinely reduced list/discovery projections.
- Player `radio_dial` values are qualified RadioDial identities, not URLs or backend paths.
- The Git backend uses the system Git executable with fixed subprocess argument lists; do not add a Python Git implementation or shell command construction without a concrete need.

## Auth and seeding conventions

- Write and player-control auth exchanges a verified OIDC ID token for a rolling session and short-lived registry bearer token; registry API reads are currently unauthenticated.
- Authz data uses the same local, S3, and Git implementations as registry data. It inherits the data backend's physical configuration when the backend types match; `REGISTRY_AUTHZ_BACKEND_*` values configure only what differs.
- Authz data may share the registry backend unless that backend is public; authz documents must remain private.
- Keep OIDC authentication under `src/auth/` and persisted authorization models and stores under `src/authz/`.
- Keep session invalidation in the authz backend and cache shared policy reads rather than adding per-session storage.
- Checked-in seed data lives under `seed-data/`, with:
  - `data/...` for registry seeds
  - `authz/...` for authz seeds
- Account-owner seeds initialize local authz; update persistent owner documents through their configured private backend.
- Reuse the shared `seed_from_path(...)` helper for both registry and authz seed loading so seeding behavior stays consistent across local, S3, and Git backends.
- When changing auth or control semantics, ensure any root architecture diagrams or related components (player, remote-control) are updated too.
- At transport boundaries, map expected authentication, authz, and not-found failures to client errors; map infrastructure and unexpected failures to generic internal errors.
- Log unexpected failures with stack traces and non-sensitive resource context. Never log bearer tokens, authenticated identities, or authz allowlists.

## Switchboard and broadcast

- WebSocket relay connecting players and remote controls in per-player channels keyed by `{account_id}/{player_id}`.
- Player connections provide their RadioDial source and ETag in `RadioPad-Radio-Dial-Url` and `RadioPad-Radio-Dial-Revision` headers. The switchboard retains revisioned `radio_dial_state` and conditionally watches each unique active Registry RadioDial, independent of the configured data backend.
- Pub-sub uses an in-tree broadcast module (`src/switchboard/broadcast.py`) — no external broker.
- Pub-sub queues, retained state, and active-player membership are process-local, so a switchboard deployment uses one worker and scales across instances with player-path affinity or registry-assigned shard URLs.
- A shared event bus alone is insufficient for interchangeable processes; distributed retained state and active-player coordination would also be required.
- The switchboard endpoint uses `asyncio.TaskGroup` with `except*` for concurrent send/receive — tasks auto-cancel when one exits.
- Standard broadcast traffic currently reaches every subscriber in a room. Preserve protocol behavior when introducing audience-aware player/controller routing.

## Change preferences

- Prefer small shared helpers over repeated route or test boilerplate.
- Reuse existing validation and datastore helpers before adding new abstractions.
- Keep tests explicit, but centralize repeated cross-resource behavior in shared helpers or common suites when coverage is genuinely duplicated.
- Do not add broad exception swallowing or silent fallbacks.
