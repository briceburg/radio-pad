# AGENTS.md

Guidance for coding agents working in `radio-pad/macropad-control`.

## Runtime and tooling

- Python-side tests and tooling are `uv`/`pyproject.toml` driven. Run `bin/ci`; it runs mypy, Ruff format/lint checks, and pytest through `uv run --locked`.
- Never assume a `/dev/ttyACM*` number. Use `bin/data-port` to discover the CircuitPython CDC2 data interface after firmware changes have settled.
- Use `bin/console-port` or `bin/console` for the CircuitPython REPL console; the console port is not the CDC2 data interface used by the player.
- Use `bin/doctor` for a read-only hardware readiness check before physical iteration.

## Hardware workflow

- Only `bin/mount` is privileged. Ask the user to run it when `sudo` prompts.
- Treat its write probe—not a running display backed by RAM—as the storage-readiness check.
- `bin/sync` is non-interactive and fails rather than mounting implicitly.
- Sync firmware before creating or recreating the Compose player. CircuitPython may reboot and expose a different host device number during the sync.
- Unmount CIRCUITPY before reset, unplug, or `fsck.vfat -n`. A dirty bit alone is not structural corruption; if no damage is reported, reset while unmounted, then rediscover devices and rerun `bin/mount` and `bin/doctor`.
- Verify physical connectivity from both sides: the player must log a connection to `/dev/macropad`, and the CircuitPython console must receive player events.
- Keep LED animations low-brightness and bounded. If LED hardware behavior is suspect, isolate it in CircuitPython safe mode with direct `MacroPad().pixels` or raw `neopixel.NeoPixel(board.NEOPIXEL, ...)` tests, and separately verify key events before changing application logic.

## Change preferences

- Device discovery commands print their value to stdout and diagnostics to stderr. A missing or ambiguous device is an error.
- Keep mount, sync, and serial discovery self-contained; do not add shared shell libraries for unrelated operations.
- Compose must not mount storage or write firmware.
