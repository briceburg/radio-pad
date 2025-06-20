# radio-pad

Use the Adafruit Macropad as a 🎵 radio station player 🎵.

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

- **Host computer** (Linux recommended, e.g., Raspberry Pi)
- **Python 3**
- **mpv** media player
- **keyboard** Python library (for global hotkey detection)

---

## Installation

1. **Install mpv:**

   ```sh
   sudo apt install mpv
   ```

2. **Install Python dependencies:**

   ```sh
   pip3 install keyboard
   ```

3. **Clone this repository:**

   ```sh
   git clone https://github.com/yourusername/radio-pad.git
   cd radio-pad
   ```

---

## Usage

### Running the Listener

> **Important:**  
> The `keyboard` library requires root privileges to listen to keyboard devices.  
> **Always run the listener with `sudo -E`:**

```sh
sudo -E bin/radio-pad
```

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

## License

[BSD 3-Clause "New" or "Revised" License](./LICENSE)

