# RadioPad Macropad

Use an [Adafruit Macropad RP2040](https://learn.adafruit.com/adafruit-macropad-rp2040/overview) to control RadioPad on a host such as a Raspberry Pi.

![macropad-image](../shared/assets/radio-macropad-ai-image.webp)

## How it works

- The Macropad communicates with the host [player](../player/) over USB serial (CircuitPython CDC2).
- The player sends a compact station menu, heartbeat, playback state, and status events; the Macropad renders them on the OLED and NeoPixel keys.
- Pressing a key sends a playback start command to the player.

### Visual states

| State | OLED title row | NeoPixel keys |
| --- | --- | --- |
| Waiting for player | `Waiting for Player` | Dim grey skeleton animation |
| Loading RadioDial | `Loading RadioDial` or a short status | Grey station-slot skeleton animation |
| Healthy | Station/page name | Blue station keys, with green for the playing station |
| Starting station | `Starting <call sign>` | Amber requested station key; green remains confirmed-only |
| Failed station | `Failed <call sign>` | Red failed station key until the next request |
| RadioDial or switchboard degraded | Station/page name when stations are loaded | Amber warning treatment |
| Playback issue | Short playback status | Existing station key state |

Skeleton animations run at low brightness and settle into a static skeleton after a long unavailable/loading period. Set `ENABLE_SKELETON_ANIMATION = False` in [`src/lib/macropad_keys.py`](./src/lib/macropad_keys.py) while diagnosing LED hardware.

## Controls

- **Station keys:** Start the corresponding Station.
- **Encoder press:** Stop confirmed or pending playback.
- **Encoder turn:** Adjust volume while playing; when stopped with more than 12 Stations, change Station pages.

## Usage

Program the Macropad, then connect it to a host running the [player](../player/).

### Programming the Macropad

A Linux host with the Macropad attached is assumed.

1. Mount CIRCUITPY:

   ```sh
   bin/mount
   ```

   The helper uses synchronous I/O and verifies a small write before reporting the filesystem ready.

2. Sync the local firmware:

   ```sh
   bin/sync
   ```

   Mounting is explicit because it may require `sudo`; syncing never mounts or prompts. Firmware is staged and verified before the installed files are replaced.

3. Verify storage, serial interfaces, firmware, and the optional Compose player:

   ```sh
   bin/doctor
   ```

Edit [`src/main.py`](./src/main.py) only when changing firmware behavior. Station assignments are not hardcoded there: the connected [player](../player/) sends an ordered call-sign menu from its registry [RadioDial](../player/README.md#registry-discovery).

### USB serial console

Use the CircuitPython console to inspect output, exceptions, or the REPL:

```sh
bin/console
```

`bin/console` selects the CircuitPython console port, not the CDC2 data port used by the player. To print the device without attaching:

```sh
bin/console-port
```

Detach from `screen` with `Ctrl-A d`; quit it with `Ctrl-A k`, then `y`.

> The user must have access to `/dev/ttyACM*`; on Arch Linux these devices belong to the `uucp` group.

After a reset, safe-mode session, or reconnect, USB device names and the CIRCUITPY block device may change. Run `bin/mount` and `bin/doctor` again before syncing or recreating the Compose player.

## Troubleshooting

### CIRCUITPY writes

A running display does not prove that CIRCUITPY is writable. If `bin/mount` fails its write probe, do not sync. Unmount and inspect without making changes:

```sh
sudo umount /mnt/CIRCUITPY
sudo fsck.vfat -n /dev/disk/by-label/CIRCUITPY
```

A dirty bit alone is not structural corruption. If no damage is reported, reset or reconnect while unmounted, then rerun `bin/mount` and `bin/doctor`.

### ALSA sound-card ordering

If attaching the Macropad changes your ALSA sound-card order because it also registers as a USB audio device, follow the ALSA guide to [choosing an order for multiple cards](https://alsa.opensrc.org/MultipleCards#The_newer_.22slots.3D.22_method).

For example, add the following to `/etc/modprobe.d/soundcard-order.conf`, where you get the vendor and product IDs from `lsusb` output:

```sh
# creative labs soundblaster: vid 0x041e pid 0x324d
# adafruit macropad: vid 0x239a pid 0x8108
options snd-usb-audio index=0,1 vid=0x041e,0x239a pid=0x324d,0x8108
```

## Development

Run Python-side checks for the Macropad control code with:

```sh
bin/ci
```

## License

[GNU General Public License v3.0](./LICENSE)
