# RadioPad player

Streams a player's assigned RadioDial through the host audio system and keeps connected controllers synchronized.

## Usage

### Requirements

- [uv](https://docs.astral.sh/uv/) for the Python environment
- [mpv](https://mpv.io/) for audio playback

Python packages are installed from `pyproject.toml` and `uv.lock`; they are not separate host dependencies.

### Running the player

Start the player through the project script:

```sh
./bin/player

# Select a registered player explicitly
RADIOPAD_PLAYER="briceburg/living-room" ./bin/player
```

On a Raspberry Pi with console auto-login, this `.bashrc` snippet starts the player in tmux. Adjust `RADIOPAD_ROOT` to the checkout path:

```sh
RADIOPAD_ROOT="$HOME/git/radio-pad"

if tmux has-session -t radio-pad 2>/dev/null; then
  echo "RadioPad is running. To attach:"
  echo "  tmux attach-session -t radio-pad"
else
  tmux new-session -s radio-pad -c "$RADIOPAD_ROOT/player" ./bin/player
fi
```

> tmux keeps the player session available when you later attach over SSH.

### Environment variables

| Name | Description | Default |
| --- | --- | --- |
| `RADIOPAD_AUDIO_CHANNELS` | Audio channel mode: `stereo` or `mono`. | `stereo` |
| `RADIOPAD_AUDIO_DEVICE` | Optional mpv device from `mpv --audio-device=help`, such as `alsa/default:CARD=Generic`. | unset |
| `RADIOPAD_AUDIO_OUTPUT` | Optional mpv output driver, such as `null` for headless tests. | unset |
| `RADIOPAD_ENABLE_DISCOVERY` | Enables discovery through `RADIOPAD_PLAYER`; any value other than `true` disables it. | `true` |
| `RADIOPAD_MPV_SOCKET_PATH` | Path to the mpv IPC socket. | `/tmp/radio-pad-mpv.sock` |
| `RADIOPAD_PLAYBACK_TIMEOUT_SECONDS` | Maximum time to wait for mpv IPC and usable audio. | `15` |
| `RADIOPAD_HEALTH_PATH` | Path to the player readiness file used by the container healthcheck. | `/tmp/radio-pad-ready` |
| `RADIOPAD_MACROPAD_PORT` | Explicit Macropad CDC2 serial device. | `auto-detected` |
| `RADIOPAD_PLAYER` | Name of player in `{account_id}/{player_id}` format, used for [registry discovery](#registry-discovery). | `briceburg/living-room` |
| `RADIOPAD_REGISTRY_URL` | Registry URL for [discovery](#registry-discovery). | `https://registry.radiopad.dev/api` |
| `RADIOPAD_RADIO_DIAL_URL` | URL returning a complete RadioDial; derived from the registry player when unset. | unset |
| `RADIOPAD_SWITCHBOARD_URL` | Switchboard URL for remote-control synchronization; discovered from the registry when unset. | unset |

### Registry discovery

The player discovers its RadioDial and switchboard URL from the [registry](../registry/) using `RADIOPAD_PLAYER`. The USB Macropad client starts before discovery completes, so a headless player can report loading or degraded startup state when the registry or RadioDial is unavailable.

For example, `RADIOPAD_PLAYER=briceburg/living-room` resolves to:

```text
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

For Compose-based development with all services, see the [root README](../README.md#development).

Run player checks with:

```sh
bin/ci
```

## License

[GNU General Public License v3.0](./LICENSE)
