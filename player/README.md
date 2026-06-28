# radio-pad player

A 🎵 radio station player 🎵 with real-time syncing controllers.

## Usage

### Host Dependencies

- [mpv](https://mpv.io/)
- [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)
- [python-websockets](https://github.com/python-websockets/websockets)

### Running the Player

Start the player through the project script, which uses `uv run` with the
dependencies from `pyproject.toml`.

```sh
./bin/player

# or to run as a particular player, use:
RADIOPAD_PLAYER="briceburg/living-room" ./bin/player
```

On a Raspberry Pi, you can start the listener at boot in a tmux session by adding the following to your auto-logged-in user's `.bashrc` file. the example assumes `radio-pad` exists it your PATH:

```sh
if tmux has-session -t radio-pad 2>/dev/null; then
  echo "radio-pad running. to attach:"
  echo "  tmux attach-session -t radio-pad"
else
  tmux new-session -s radio-pad radio-pad
fi
```

> tmux maintains the tty1 attachment whereas screen drops it if you attach via ssh.

### Environment Variables

name | description | default
--- | --- | ---
`RADIOPAD_AUDIO_CHANNELS` | 'stereo' or 'mono' | `stereo`
`RADIOPAD_ENABLE_DISCOVERY` | Enables discovery based on `RADIOPAD_PLAYER`. Anything other than "true" disables it. | `true`
`RADIOPAD_MPV_SOCKET_PATH` | Path to the mpv IPC socket. | `/tmp/radio-pad-mpv.sock`
`RADIOPAD_HEALTH_PATH` | Path to the player readiness file used by the container healthcheck. | `/tmp/radio-pad-ready`
`RADIOPAD_MACROPAD_PORT` | Explicit macropad CDC2 serial device. | `auto-detected`
`RADIOPAD_PLAYER` | Name of player in `{account_id}/{player_id}` format, used for [registry discovery](#registry-discovery). | `briceburg/living-room`
`RADIOPAD_REGISTRY_URL` | Registry URL for [discovery](#registry-discovery). | `https://registry.radiopad.dev/api`
`RADIOPAD_RADIO_DIAL_URL` | URL returning a complete RadioDial resource. Derived from the registry player configuration if not set. | `None`
`RADIOPAD_SWITCHBOARD_URL` | Switchboard URL for remote-control syncing. Discovered from the registry if not set. | `None`

### Registry Discovery

The player discovers its RadioDial and switchboard URL from the [registry](../registry/) using `RADIOPAD_PLAYER`.
The USB macropad client starts before discovery completes, so a headless player can report loading or degraded startup state when the registry or RadioDial is unavailable.

For example, `RADIOPAD_PLAYER=briceburg/living-room` resolves to:

```
https://registry.radiopad.dev/api/accounts/briceburg/players/living-room
```

The registry player resource contains a qualified `radio_dial` identity such as `community/briceburg`. The player combines that identity with `RADIOPAD_REGISTRY_URL` to load the complete RadioDial; `switchboard_url` remains an independently configured endpoint.

#### Editing Stations

Stations are account-owned registry resources. RadioDials contain ordered Station keys, so changing a Station's stream URL updates every RadioDial that references it. Use the registry API or edit the [community seed data](../registry/seed-data/store/accounts/community/) during development.

To bypass registry discovery, set `RADIOPAD_RADIO_DIAL_URL` to a URL returning a complete RadioDial resource:

```json
{
  "key": "community/briceburg",
  "name": "Casa Briceburg",
  "discoverable": true,
  "stations": [
    {
      "key": "community/WWOZ",
      "call_sign": "WWOZ",
      "stream_url": "https://www.wwoz.org/listen/hi"
    }
  ]
}
```

## Troubleshooting Sound

If plugging in the Macropad interferes with your Alsa sound configuration (because it is also registered as a snd-usb-audio device), follow the "[How to choose a particular order for multiple installed cards](https://alsa.opensrc.org/MultipleCards#The_newer_.22slots.3D.22_method)" section of the Alsa docs.

For example, add the following to `/etc/modprobe.d/soundcard-order.conf`, where you get the vendor and product IDs from `lsusb` output:

```sh
# creative labs soundblaster: vid 0x041e pid 0x324d 
# adafruit macropad: vid 0x239a pid 0x8108
options snd-usb-audio index=0,1 vid=0x041e,0x239a pid=0x324d,0x8108
```

## Development

For compose-based development with all services, see the [root README](../README.md#development).

Run player checks with:

```sh
bin/ci
```

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU General Public License v3.0](./LICENSE)
