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
`RADIOPAD_AUDIO_DEVICE` | Optional mpv device from `mpv --audio-device=help`, such as `alsa/default:CARD=Generic`. | `None`
`RADIOPAD_AUDIO_OUTPUT` | Optional mpv audio output driver, such as `null` for headless tests. | `None`
`RADIOPAD_ENABLE_DISCOVERY` | Enables discovery based on `RADIOPAD_PLAYER`. Anything other than "true" disables it. | `true`
`RADIOPAD_MPV_SOCKET_PATH` | Path to the mpv IPC socket. | `/tmp/radio-pad-mpv.sock`
`RADIOPAD_PLAYBACK_TIMEOUT_SECONDS` | Maximum time to wait for mpv IPC and usable audio. | `15`
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

## Development

For compose-based development with all services, see the [root README](../README.md#development).

Run player checks with:

```sh
bin/ci
```

## License

[GNU General Public License v3.0](./LICENSE)
