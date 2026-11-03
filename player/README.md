# RadioPad player

Streams a player's assigned RadioDial through the host audio system and keeps connected controllers synchronized.

## Usage

### Requirements

- [uv](https://docs.astral.sh/uv/) for the Python environment
- [mpv](https://mpv.io/) for audio playback

The player installs locked Python dependencies with uv, including yt-dlp and Deno for site URLs such as YouTube. mpv handles direct streams and playlists.

### Run on a host

From this directory, run a registered player in the foreground; Ctrl+C stops it:

```sh
RADIOPAD_PLAYER="ACCOUNT/PLAYER" ./bin/player
```

`./bin/player` alone uses the default identity listed below.

### Raspberry Pi deployment

Follow the [Raspberry Pi guide](./deploy/raspberry-pi/) for flashing or an existing OS, SSH access, Wi-Fi, audio selection, and service status, logs, and updates.

### Environment variables

| Name | Description | Default |
| --- | --- | --- |
| `RADIOPAD_AUDIO_CHANNELS` | Audio channel mode: `stereo` or `mono`. | `stereo` |
| `RADIOPAD_AUDIO_DEVICE` | Optional mpv device from `mpv --audio-device=help`, such as `alsa/default:CARD=Generic`. | unset |
| `RADIOPAD_AUDIO_OUTPUT` | Optional mpv output driver, such as `null` for headless tests. | unset |
| `RADIOPAD_ENABLE_DISCOVERY` | Case-insensitive `true` enables registry discovery. | `true` |
| `RADIOPAD_MPV_SOCKET_PATH` | Path to the mpv IPC socket. | `/tmp/radio-pad-mpv.sock` |
| `RADIOPAD_PLAYBACK_TIMEOUT_SECONDS` | Maximum time to wait for mpv IPC and usable audio. | `15` |
| `RADIOPAD_HEALTH_PATH` | Path to the player readiness file used by the container healthcheck. | `/tmp/radio-pad-ready` |
| `RADIOPAD_MACROPAD_PORT` | Explicit Macropad CDC2 serial device. | `auto-detected` |
| `RADIOPAD_PLAYER` | Registered `account/player` identity for [discovery](#registry-discovery). | `briceburg/living-room` |
| `RADIOPAD_REGISTRY_URL` | Registry URL for [discovery](#registry-discovery). | `https://registry.radiopad.dev/api` |
| `RADIOPAD_RADIO_DIAL_URL` | URL returning a complete RadioDial; derived from the registry player when unset. | unset |
| `RADIOPAD_SWITCHBOARD_URL` | Switchboard URL for remote-control synchronization; discovered from the registry when unset. | unset |

### Registry discovery

The player discovers its RadioDial and switchboard URL from the [registry](../registry/) using `RADIOPAD_PLAYER`. The USB Macropad starts first and reports loading or degraded state if discovery fails.

For example, `RADIOPAD_PLAYER=briceburg/living-room` resolves to:

```text
https://registry.radiopad.dev/api/accounts/briceburg/players/living-room
```

The registry's `radio_dial` identity, such as `community/briceburg`, resolves against `RADIOPAD_REGISTRY_URL`; `switchboard_url` is a separate endpoint.

The switchboard broadcasts `radio_dial_state` when a RadioDial's ETag changes. The player reloads it and updates the Macropad menu without polling or interrupting playback. Reload failures keep the last valid dial and retry with degraded status.

#### Editing Stations

Stations belong to accounts; RadioDials reference ordered Station keys. Changing a Station updates every referencing dial. Use the registry API or edit [community seed data](../registry/seed-data/data/accounts/community/) during development.

To bypass discovery, set `RADIOPAD_ENABLE_DISCOVERY=false` and `RADIOPAD_RADIO_DIAL_URL` to a complete RadioDial URL. Set `RADIOPAD_SWITCHBOARD_URL` if remote control is needed. The dial response has this shape:

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

Use [Compose](../README.md#development) for the full stack. From this directory, run player checks with:

```sh
bin/ci
```

## License

[GNU General Public License v3.0](./LICENSE)
