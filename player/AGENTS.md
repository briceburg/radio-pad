# AGENTS.md

Guidance for coding agents working in `radio-pad/player`.

## Project shape

- Python application that plays internet radio stations on a host device (e.g. Raspberry Pi).
- Connects to the registry switchboard via WebSocket to receive station requests and broadcast currently playing station.
- Uses `mpv` as the audio backend (system dependency, installed via `apk` in Docker).
- No test directory currently — only static analysis via `bin/ci`.

## Runtime and tooling

- The checked-in project target is Python `3.13`.
- `bin/ci` runs `black` (formatting), `isort` (import order), and `autoflake` (unused imports/variables) on `src/`.
- Development dependencies are in `requirements-dev.txt` (`autoflake`, `black`, `isort`).
- Runtime dependencies are in `requirements.txt`.

## Conventions

- The player identifies itself to the switchboard with a `User-Agent: RadioPad/...` header and a `RadioPad-Stations-Url` header.
- Station presets are fetched from the registry API via the URL configured at startup.
- The player is a WebSocket client, not a server — it has no HTTP endpoints of its own (healthcheck uses `pgrep`).

## Change preferences

- Keep the player lightweight — it's designed to run on low-resource devices.
- When changing switchboard protocol (events, headers), coordinate with `registry/src/switchboard/` and `tests/integration/`.
