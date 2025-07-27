# radio-pad player

A 🎵 radio station player 🎵 with real-time syncing controllers.

## Usage

### Host Dependencies

- [mpv](https://mpv.io/)
- [python-websockets](https://websockets.readthedocs.io/en/stable/)
- [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)
- [python-websockets](https://github.com/python-websockets/websockets)

### Running the Player

start the player via a script that automatically activates a python virtual environment and installs dependencies.

```sh
./bin/player
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
`RADIOPAD_PLAYER_ID` | Used to discover the station presets and switchboard URL. | `briceburg`
`RADIOPAD_REGISTRY_URL` | Player discovery URL. | `https://registry.radiopad.dev`
`RADIOPAD_STATIONS_URL` | URL to load stations from. Must return a JSON list of stations. Discovered if not provided. | `None`
`RADIOPAD_SWITCHBOARD_URL` | URL of switchboard. The switchboard enables remote-controls. Not needed for locally controlled players. Discovered if not provided. | `None`

### Editing Stations

Modify and commit [stations.json](https://github.com/briceburg/radio-pad-registry/blob/main/src/players/briceburg/stations.json) files for your desired player in the registry. Changes are loaded by the player at startup, and the loaded station list is shared with connected controllers.

If you prefer to skip station discovery and roll your own list, set the RADIOPAD_STATIONS_URL environment variable to a URL that responds with your desired stations.

Example configuration:

```json
[
  {"name": "WWOZ", "url": "https://www.wwoz.org/listen/hi"},
  {"name": "KEXP", "url": "https://kexp.org/stream", "color": 0x770077}
]
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

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU General Public License v3.0](./LICENSE)
