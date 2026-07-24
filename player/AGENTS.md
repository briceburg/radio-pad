# AGENTS.md

Guidance for coding agents working in `radio-pad/player`.

## Project shape

- Python application that plays internet radio stations on a host device (e.g. Raspberry Pi).
- Connects to the registry switchboard via WebSocket to receive station requests and broadcast currently playing station.
- Uses `mpv` as the audio backend (system dependency, installed via `apk` in Docker).
- Unit tests live in `tests/` and cover macropad serial-port selection and serial message handling with fake readers/writers.

## Runtime and tooling

- Python dependencies and tool settings live in `pyproject.toml`.
- Use `bin/ci` for validation. It runs mypy, Ruff format/lint checks, and pytest through `uv run --locked`.
- Use `bin/player` or `uv run python src/player.py` for local execution.
- The Docker image installs dependencies with `uv sync` from `pyproject.toml` and `uv.lock`.

## Conventions

- The player identifies itself to the switchboard with `User-Agent: RadioPad/...` and `RadioPad-Radio-Dial-Url` headers.
- Registry player configuration carries a qualified `radio_dial` identity. The running player carries the source `radio_dial_url` from which it loaded a complete RadioDial.
- The player is a WebSocket client, not a server — it has no HTTP endpoints of its own (the container healthcheck runs `python3 src/healthcheck.py`, which checks a readiness file).

## Change preferences

- Keep the player lightweight — it's designed to run on low-resource devices.
- When changing switchboard protocol (events, headers), coordinate with `registry/src/switchboard/` and `tests/integration/`.
