# radio-pad player

A 🎵 radio station player 🎵 with real-time syncing controllers.

## Usage

### Host Dependencies

- [mpv](https://mpv.io/)
- [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/en/master/)
- [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc)
- [python-websockets](https://github.com/python-websockets/websockets)

### Running the Listener

install deps
```sh
pip3 install -r requirements.txt
```

start the player

```sh
./bin/radio-pad
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

### Editing Stations

Modify and commit [stations.json](./stations.json). Changes are loaded by the player at startup.

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

[BSD 3-Clause "New" or "Revised" License](./LICENSE)
