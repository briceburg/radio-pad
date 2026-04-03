# radio-pad player

A 🎵 radio station player 🎵 with real-time syncing controllers.

## Usage

### Host Dependencies

- [mpv](https://mpv.io/)
- [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)
- [python-websockets](https://github.com/python-websockets/websockets)

### Running the Player

start the player via a script that automatically activates a python virtual environment and installs dependencies.

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
`RADIOPAD_ENABLE_DISCOVERY` | Enables discovery based on RADIOPAD_PLAYER_ID. Anything other than "true" will disable. | `true`
`RADIOPAD_MPV_SOCKET_PATH` | Path to the mpv IPC socket. | `/tmp/radio-pad-mpv.sock`
`RADIOPAD_PLAYER` | Name of player in `{account_id}/{player_id}` format, used for [registry discovery](#registry-discovery). | `briceburg/living-room`
`RADIOPAD_REGISTRY_URL` | Registry URL for [discovery](#registry-discovery). | `https://registry.radiopad.dev`
`RADIOPAD_STATIONS_URL` | URL returning a station preset JSON object. Discovered from the registry if not set. | `None`
`RADIOPAD_SWITCHBOARD_URL` | Switchboard URL for remote-control syncing. Discovered from the registry if not set. | `None`

### Registry Discovery

The player discovers its station preset and switchboard URL from the [registry](../registry/) using the `RADIOPAD_PLAYER` environment variable.

For example, `RADIOPAD_PLAYER=briceburg/living-room` resolves to:

```
https://registry.radiopad.dev/api/accounts/briceburg/players/living-room
```

The registry returns the `stations_url` (pointing to a station preset) and `switchboard_url` for this player. The station preset contains the named list of stations the player will offer.

#### Editing Stations

Stations are defined in station presets stored in the registry. To modify them, use the registry API or edit the seed data directly — e.g. the [briceburg station preset](../registry/seed-data/store/presets/briceburg.json).

To bypass registry discovery entirely, set `RADIOPAD_STATIONS_URL` to any URL that returns a station preset JSON object:

```json
{
  "name": "Casa Briceburg",
  "stations": [
    {"name": "WWOZ", "url": "https://www.wwoz.org/listen/hi"},
    {"name": "KEXP", "url": "https://kexp.org/stream", "color": 0x770077}
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

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU General Public License v3.0](./LICENSE)
