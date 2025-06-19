# radio-pad

Use the adafruit macropad as a radio station player

## Overview

The macropad should be plugged into a host, such as a raspberry pi, that has [mpv](https://mpv.io/) and python installed. A listener ( [bin/radio-pad](./bin/radio-pad)) is added to the host that will respond to keypresses by playing the requested station.


### Host Configuration

* ensure mpv is installed
* ensure python3 and [pynput](https://pypi.org/project/pynput/) is available

  ```sh
  pip3 install pynput
  ```
  
* copy [bin/radio-pad](./bin/radio-pad) to a location in your PATH and ensure its executable.
* start `radio-pad`
* program the macropad
* plug in the macropad and enjoy

### Programming the Macropad

Programming the macropad allows you to customize the stations it supports as well as the key colors for each station. All sourecode lives under the [src](./src) directory.

* plug in the macropad and call [bin/mount](./bin/mount) to mount its storage to /mnt/CIRCUITPY for programming.
* modify [src/macros/radio.py](./src/macros/radio.py) to your liking
* sync your changes using [bin/refresh](./bin/refresh)
