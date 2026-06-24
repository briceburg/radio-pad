# AGENTS.md

Guidance for coding agents working in `radio-pad/macropad-control`.

- Never assume a `/dev/ttyACM*` number. Use `bin/data-port` to discover the
  CircuitPython CDC2 data interface after firmware changes have settled.
- Use `bin/console-port` or `bin/console` for the CircuitPython REPL console;
  the console port is not the CDC2 data interface used by the player.
- Use `bin/doctor` for a read-only hardware readiness check before physical
  iteration.
- Only `bin/mount` is privileged. Ask the user to run it when `sudo` prompts.
- `bin/sync` is non-interactive and fails rather than mounting implicitly.
- Sync firmware before creating or recreating the compose player. CircuitPython
  may reboot and expose a different host device number during the sync.
- Resets, safe mode, and unplug/replug cycles can also re-enumerate both the
  storage device and tty names. Re-run `bin/mount` and `bin/doctor` after those
  operations rather than trusting an old `/mnt/CIRCUITPY` mount.
- Verify physical connectivity from both sides: the player must log a connection
  to `/dev/macropad`, and the CircuitPython console must receive player events.
- Keep LED animations low-brightness and bounded. If LED hardware behavior is
  suspect, isolate it in CircuitPython safe mode with direct `MacroPad().pixels`
  or raw `neopixel.NeoPixel(board.NEOPIXEL, ...)` tests, and separately verify
  key events before changing application logic.

- Device discovery commands print their value to stdout and diagnostics to
  stderr. A missing or ambiguous device is an error.
- Keep mount, sync, and serial discovery self-contained; do not add shared shell
  libraries for unrelated operations.
- Compose must not mount storage or write firmware.
