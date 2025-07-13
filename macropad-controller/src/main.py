import time
import json
import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label
from adafruit_macropad import MacroPad
from adafruit_hid.keycode import Keycode
import usb_cdc


DEFAULT_COLOR = 0x000077
HIGHLIGHT_COLOR = 0x015C01
PRESSED_COLOR = 0x999999
LED_BRIGHTNESS = 0.10  # Dim the LEDs, 1 is full brightness
MACROPAD_KEY_COUNT = 12  # Number of keys on the MacroPad
RADIO_STATIONS_FILE = "stations.json"
PLAYER = usb_cdc.data

if not PLAYER:
    raise RuntimeError("No USB CDC data port found.")

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
        group[MACROPAD_KEY_COUNT + 1].text = self.title
        rect.fill = 0xFFFFFF
        for i in range(MACROPAD_KEY_COUNT):
            if i < len(self.stations):
                macropad.pixels[i] = self.stations[i].get("color", DEFAULT_COLOR)
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
    group[MACROPAD_KEY_COUNT + 1].text = "NO STATIONS DEFINED"
    macropad.display.refresh()
    while True:
        pass


last_position = None
last_encoder_switch = macropad.encoder_switch_debounced.pressed
app_index = 0
apps[app_index].switch()
current_station_index = None


def radio_control(event, data=None):
    PLAYER.write(f"{event}:{data}\n".encode())
    time.sleep(0.1) # Allow time for the message to be sent


def highlight_playing(app_index, station_index):
    """Highlight the currently playing station."""

    group[MACROPAD_KEY_COUNT + 1].text = (
        apps[app_index].stations[station_index].get("name", "?")
    )
    for i in range(MACROPAD_KEY_COUNT):
        try:
            macropad.pixels[i] = (
                HIGHLIGHT_COLOR
                if i == station_index
                else apps[app_index].stations[i].get("color", DEFAULT_COLOR)
            )
        except IndexError:
            macropad.pixels[i] = 0

        group[i].color = 0x000000 if i == station_index else 0xFFFFFF
        group[i].background_color = 0xFFFFFF if i == station_index else 0x000000

    macropad.pixels.show()
    macropad.display.refresh()

def reset_playing(app_index, flash=False):
   
    if flash:
        # flash the pixels
        for i in range(MACROPAD_KEY_COUNT):
            macropad.pixels[i] = 0x990909
        macropad.pixels.show()
        time.sleep(0.66)

    # reset radio display and keys
    group[MACROPAD_KEY_COUNT + 1].text = apps[app_index].title
    for i in range(MACROPAD_KEY_COUNT):
        group[i].color = 0xFFFFFF
        group[i].background_color = 0x000000
        try:
            macropad.pixels[i] = (
                apps[app_index].stations[i].get("color", DEFAULT_COLOR)
            )
        except IndexError:
            macropad.pixels[i] = 0
    macropad.display.refresh()
    macropad.pixels.show()


# MAIN LOOP ----------------------------
while True:
    if PLAYER.in_waiting > 0:
        lines = PLAYER.read(PLAYER.in_waiting).decode("utf-8").strip().splitlines()
        if lines:
            event, _, data = lines[-1].partition(":")
            if event == "station_playing":
                current_station_index = None
                for aidx, app in enumerate(apps):
                    for idx, station in enumerate(app.stations):
                        if station.get("name") == data:
                            # If the app index has changed, switch to the correct app page.
                            if app_index != aidx:
                                apps[aidx].switch()
                                app_index = aidx

                            current_station_index = idx
                            break
                    if current_station_index is not None:
                        break
                
                if current_station_index is None:
                    reset_playing(app_index)
                else:
                    highlight_playing(app_index, current_station_index)
        else:
            print(f"PLAYER: ignored event: {event}")

    # Read encoder position.
    position = macropad.encoder
    if last_position is not None and position != last_position:
        if current_station_index is not None:
            # if a station is playing, change volume
            radio_control("volume", "up" if position > last_position else "down")
        else:

            # else, change station page
            # we cannot use app_index = position % len(apps) -- because the encoder value is linked to volume as well
            # TODO: investiagate ability to reset the macropad.encoder value when switching apps so the number doesn't get huge over time.
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
        if current_station_index is not None:
            radio_control("stop")
    else:
        event = macropad.keys.events.get()
        if not event or event.key_number >= len(apps[app_index].stations):
            continue  # No key events, or no corresponding station, resume loop
        key_number = event.key_number
        pressed = event.pressed

    # If code reaches here, a key WAS pressed/released and there's a corresponding station.
    if pressed and key_number < MACROPAD_KEY_COUNT:  # No pixel for encoder button
        macropad.pixels[key_number] = PRESSED_COLOR
        macropad.pixels.show()
        radio_control("play", apps[app_index].stations[key_number].get("name", "?"))
    else:
        macropad.consumer_control.release()
