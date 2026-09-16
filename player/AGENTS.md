# AGENTS.md

Guidance for coding agents working in `radio-pad/player`.

## Project shape

- Python application that plays internet radio stations on a host device (e.g. Raspberry Pi).
- Connects to the registry switchboard via WebSocket to receive station requests and broadcast currently playing station.
- Uses `mpv` as the audio backend (system dependency, installed through APT in Docker).
- Raspberry Pi deployment is auxiliary tooling under `deploy/raspberry-pi`; `bin/rpi-flash` writes the pinned base image and `bin/rpi-provision` runs its Ansible playbook without adding deployment tools to the player runtime.
- Unit tests live in `tests/` and cover macropad serial-port selection and serial message handling with fake readers/writers.

## Runtime and tooling

- Python dependencies and tool settings live in `pyproject.toml`.
- Use `bin/ci` for validation. It checks the yt-dlp/Deno URL resolver and runs mypy, Ruff format/lint checks, and pytest through `uv run --locked`.
- Use `bin/player` or `uv run python src/player.py` for local execution.
- The Docker image installs dependencies with `uv sync` from `pyproject.toml` and `uv.lock`.
- Validate provisioning changes with the pinned Ansible Core and collection versions under `deploy/raspberry-pi`; keep the playbook idempotent.

## Conventions

- The player identifies itself to the switchboard with `User-Agent: RadioPad/...`, `RadioPad-Radio-Dial-Url`, and `RadioPad-Radio-Dial-Revision` headers.
- Registry player configuration carries a qualified `radio_dial` identity. The running player carries the source `radio_dial_url` from which it loaded a complete RadioDial.
- The player reloads its resolved RadioDial in response to revisioned `radio_dial_state` events. Station changes replace the local Macropad menu without interrupting active playback.
- The player is a WebSocket client, not a server — it has no HTTP endpoints of its own (the container healthcheck runs `python3 src/healthcheck.py`, which checks a readiness file).

## Change preferences

- Keep the player lightweight — it's designed to run on low-resource devices.
- Keep provisioning dependencies auxiliary; do not add Ansible or image-building tools to `pyproject.toml`.
- Keep `bin/rpi-flash` conservative: detect at most one candidate, validate an unmounted removable whole-disk device, and require exact confirmation before invoking Raspberry Pi Imager.
- When changing switchboard protocol (events, headers), coordinate with `registry/src/switchboard/` and `tests/integration/`.
