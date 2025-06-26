# radio-pad

Use the [Adafruit Macropad RP2040](https://learn.adafruit.com/adafruit-macropad-rp2040/overview) as a 🎵 radio station player 🎵.

---

## What is radio-pad?

**radio-pad** lets you use an Adafruit Macropad as a controller for playing internet radio stations on your computer (such as a Raspberry Pi). Each Macropad button can be mapped to a different station, and the host computer will play the selected station using [mpv](https://mpv.io/).

---

## How It Works

- The Macropad sends keypresses to the host computer.
- The host runs a listener script (`bin/radio-pad`) that detects these keypresses and starts/stops playback of the corresponding radio stream.
- Station configuration and button colors are customizable.

---

## Requirements

- **Host computer** (Linux recommended, e.g. a Raspberry Pi)
  - **Python 3** with the [prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/en/master/) and [python-mpv-jsonipc](https://github.com/iwalton3/python-mpv-jsonipc) libraries.
  - **mpv** media player

---

## Installation

1. **Install mpv:**

   ```sh
   sudo apt install mpv
   ```

2. **Install Python dependencies:**

   ```sh
   pip3 install prompt_toolkit python-mpv-jsonipc
   ```

3. **Clone this repository:**

   ```sh
   git clone https://github.com/yourusername/radio-pad.git
   cd radio-pad
   ```

4. **Add radio-pad to your PATH**

    ```sh
    sudo ln -s "$PWD/bin/radio-pad" /usr/local/bin/
    ```

---

## Usage

### Running the Listener

```sh
bin/radio-pad
```

on my raspberry pi I start the listener at boot in a tmux session by adding the following to my auto-logged-in user's `.bashrc` file:

```sh
if tmux has-session -t radio-pad 2>/dev/null; then
  echo "radio-pad running. to attach:"
  echo "  tmux attach-session -t radio-pad"
else
  tmux new-session -s radio-pad radio-pad
fi
```

> tmux maintains the tty1 attachment whereas screen drops it if you attach via ssh.

### Programming the Macropad

1. **Mount the Macropad storage:**

   ```sh
   bin/mount
   ```

2. **Customize stations and button colors:**

   - Edit [`src/macros/radio.py`](./src/macros/radio.py) for button assignments.
   - Edit [`src/config/stations.json`](./src/config/stations.json) to change the list of available stations.

3. **Sync your changes to the Macropad:**

   ```sh
   bin/refresh
   ```

---

## Troubleshooting Sound

if plugging in the macropad interferes with your Alsa sound configuration, because it also is registered as a snd-usb-audio device, follow the "[How to choose a particular order for multiple installed cards](https://alsa.opensrc.org/MultipleCards#The_newer_.22slots.3D.22_method)" section of the Alsa docs. 

I ended up adding the following to my `/etc/modprobe.d/soundcard-order.conf`, where I got the vendor and product IDs from `lsusb` output.

```sh
# creative labs soundblaster: vid 0x041e pid 0x324d 
# adafruit macropad: vid 0x239a pid 0x8108
options snd-usb-audio index=0,1 vid=0x041e,0x239a pid=0x324d,0x8108
```

## License

[BSD 3-Clause "New" or "Revised" License](./LICENSE)
