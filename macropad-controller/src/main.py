import time
import json
import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label
from adafruit_macropad import MacroPad
from adafruit_hid.keycode import Keycode

DEFAULT_KEY_COLOR = 0x000077
HIGHLIGHT_COLOR = 0x015C01
LED_BRIGHTNESS = 0.10  # Dim the LEDs, 1 is full brightness
MACROPAD_KEY_COUNT = 12  # Number of keys on the MacroPad
RADIO_STATIONS_FILE = "stations.json"

# Display Setup -----------------------
# each group displays the station 'name' corresponding to the key number.
macropad = MacroPad()
macropad.display.auto_refresh = False
macropad.pixels.auto_write = False
macropad.pixels.brightness = LED_BRIGHTNESS
group = displayio.Group()
for key_index in range(MACROPAD_KEY_COUNT):
    x = key_index % 3
    y = key_index // 3
    group.append(
        label.Label(
            terminalio.FONT,
            text="",
            color=0xFFFFFF,
            anchored_position=(
                (macropad.display.width - 1) * x / 2,
                macropad.display.height - 1 - (3 - y) * 12,
            ),
            anchor_point=(x / 2, 1.0),
        )
    )
rect = Rect(0, 0, macropad.display.width, 13, fill=0xFFFFFF)
group.append(rect)
group.append(
    label.Label(
        terminalio.FONT,
        text="",
        color=0x000000,
        anchored_position=(macropad.display.width // 2, 0),
        anchor_point=(0.5, 0.0),
    )
)
macropad.display.root_group = group


# INITIALIZATION -----------------------
class App:
    def __init__(self, appdata):
        self.stations = appdata["stations"]
        self.title = appdata["title"]

    def switch(self):
        group[13].text = self.title
        rect.fill = 0xFFFFFF
        for i in range(MACROPAD_KEY_COUNT):
            if i < len(self.stations):
                macropad.pixels[i] = self.stations[i].get("color", DEFAULT_KEY_COLOR)
                group[i].text = self.stations[i].get("name", "?")
            else:  # no station assigned to this key, disable LED and label.
                macropad.pixels[i] = 0
                group[i].text = ""

        macropad.keyboard.release_all()
        macropad.consumer_control.release()
        macropad.mouse.release_all()
        macropad.stop_tone()
        macropad.pixels.show()
        macropad.display.refresh()


# add an application for each page of stations, page length is MACROPAD_KEY_COUNT
apps = []
with open(RADIO_STATIONS_FILE, "r") as f:
    stations_list = json.load(f)
    for i in range(0, len(stations_list), MACROPAD_KEY_COUNT):
        apps.append(
            App(
                {
                    "stations": stations_list[i : i + MACROPAD_KEY_COUNT],
                    "title": (
                        "iCEBURG Radio"
                        if len(stations_list) <= MACROPAD_KEY_COUNT
                        else f"iCEBURG Radio {int(i / MACROPAD_KEY_COUNT) + 1}"
                    ),
                }
            )
        )
    del stations_list

if not apps:
    group[13].text = "NO STATIONS DEFINED"
    macropad.display.refresh()
    while True:
        pass

last_position = None
last_pressed = None
last_encoder_switch = macropad.encoder_switch_debounced.pressed
app_index = 0
apps[app_index].switch()


def radio_control(cmd_char, arg_char):
    """Sends a command and argument to the bin/radio-pad listener. Escape sequence is Ctrl+@"""
    macropad.keyboard.press(Keycode.CONTROL)
    macropad.keyboard.press(Keycode.TWO)
    macropad.keyboard.release(Keycode.CONTROL)
    macropad.keyboard.release(Keycode.TWO)
    macropad.keyboard_layout.write(cmd_char)
    macropad.keyboard_layout.write(arg_char)


def index_to_char(idx):
    """
    Convert an integer index to a single character.
    Allows up to 35 pages of stations to be represented by a single keypress.
    0-9 -> '0'-'9', 10-35 -> 'a'-'z'.
    """
    if 0 <= idx <= 9:
        return str(idx)
    elif 10 <= idx <= 35:
        return chr(ord("a") + (idx - 10))
    else:
        raise ValueError("Index out of supported range (0-35)")


# MAIN LOOP ----------------------------
import usb_cdc
data_stream = usb_cdc.data

while True:
    if data_stream.in_waiting > 0:
        received_data = data_stream.readline().decode().strip()
        print(f"Received data from player: {received_data}")
        time.sleep(0.1)
    

    # Read encoder position.
    position = macropad.encoder
    if last_position is not None and position != last_position:
        if last_pressed is not None:
            # if a station is playing, change volume
            radio_control("V", "+" if position > last_position else "-")
        else:

            # else, change station page
            # we cannot use app_index = position % len(apps) -- because the encoder value is linked to volume as well
            # TODO: investiagate ability to reset the macropad.encoder value when switching apps
            if position > last_position:
                app_index += 1
                if app_index > len(apps) - 1:
                    app_index = 0
            else:
                app_index -= 1
                if app_index < 0:
                    app_index = len(apps) - 1
            apps[app_index].switch()

    last_position = position

    # Handle encoder button. If it's pressed, stop radio.
    macropad.encoder_switch_debounced.update()
    encoder_switch = macropad.encoder_switch_debounced.pressed
    if encoder_switch != last_encoder_switch:
        last_encoder_switch = encoder_switch
        if last_pressed is not None:
            # stop radio
            radio_control("X", "*")

            # reset radio display and highlighted key to its original
            group[last_pressed].color = 0xFFFFFF
            group[last_pressed].background_color = 0x000000
            group[13].text = apps[app_index].title
            macropad.display.refresh()

            last_pressed = None

            # flash the pixels
            for i in range(MACROPAD_KEY_COUNT):
                macropad.pixels[i] = 0x990909
            macropad.pixels.show()
            time.sleep(0.66)

            # restore the pixels
            for i in range(MACROPAD_KEY_COUNT):
                try:
                    macropad.pixels[i] = (
                        apps[app_index].stations[i].get("color", DEFAULT_KEY_COLOR)
                    )
                except IndexError:
                    macropad.pixels[i] = 0
            macropad.pixels.show()

        continue
    else:
        event = macropad.keys.events.get()
        if not event or event.key_number >= len(apps[app_index].stations):
            continue  # No key events, or no corresponding station, resume loop
        key_number = event.key_number
        pressed = event.pressed

    # If code reaches here, a key WAS pressed/released and there's a corresponding station.
    if pressed and key_number < MACROPAD_KEY_COUNT:  # No pixel for encoder button

        # highlight the key and label
        macropad.pixels[key_number] = HIGHLIGHT_COLOR
        group[key_number].color = 0x000000
        group[key_number].background_color = 0xFFFFFF
        group[13].text = apps[app_index].stations[key_number].get("name", "?")

        # remove highlighting from previous key and label
        if last_pressed is not None and last_pressed != key_number:
            macropad.pixels[last_pressed] = (
                apps[app_index].stations[last_pressed].get("color", DEFAULT_KEY_COLOR)
            )
            group[last_pressed].color = 0xFFFFFF
            group[last_pressed].background_color = 0x000000

        # play station
        radio_control(index_to_char(app_index), index_to_char(key_number))

        macropad.pixels.show()
        macropad.display.refresh()
        last_pressed = key_number
    else:
        macropad.consumer_control.release()
