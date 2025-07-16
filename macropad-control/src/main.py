import time
import json
import displayio
import terminalio
from adafruit_display_shapes.rect import Rect
from adafruit_display_text import label
from adafruit_macropad import MacroPad
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

class RadioPadApp:
    def __init__(self):
        self.current_page_index = None
        self.current_station_index = None
        self.last_position = macropad.encoder
        self.last_encoder_switch = macropad.encoder_switch_debounced.pressed
        self.pages = []
        try:
            self._load_stations()
        except Exception as e:
            print(f"Error loading stations: {e}")
            self.set_title("STATION LOADING ERROR")
            macropad.display.refresh()
            while True:
                pass

    def _load_stations(self):
        """Load station configurations from a JSON file."""
        with open(RADIO_STATIONS_FILE, "r") as f:
            stations_list = json.load(f)
        if len(stations_list) == 0:
            raise ValueError("No stations found in the configuration file.")
        for i in range(0, len(stations_list), MACROPAD_KEY_COUNT):
            self.pages.append({
                "stations": stations_list[i : i + MACROPAD_KEY_COUNT],
                "title": (
                    "iCEBURG Radio"
                    if len(stations_list) <= MACROPAD_KEY_COUNT
                    else f"iCEBURG Radio {int(i / MACROPAD_KEY_COUNT) + 1}"
                ),
            })

    def radio_control(self, event, data=None):
        """Send a command to the host player."""
        message = json.dumps({"event": event, "data": data})
        PLAYER.write(f"{message}\n".encode())
        time.sleep(0.1)  # Handle backpressure

    def set_title(self, title=None):
        if not title:
            if self.current_station_index is not None:
                title = self.pages[self.current_page_index]['stations'][self.current_station_index].get("name", "?")
            else:
                title = self.pages[self.current_page_index]['title']
        group[MACROPAD_KEY_COUNT + 1].text = title

    def update_display(self, flash=False):
        """Update the entire display, including LEDs and text."""
        if flash:
            for i in range(MACROPAD_KEY_COUNT):
                macropad.pixels[i] = 0x990909
            macropad.pixels.show()
            time.sleep(0.66)

        page = self.pages[self.current_page_index]
        self.set_title()
        for i in range(MACROPAD_KEY_COUNT):
            if i < len(page['stations']):
                station = page['stations'][i]
                if i == self.current_station_index:
                    macropad.pixels[i] = HIGHLIGHT_COLOR
                    group[i].color = 0x000000
                    group[i].background_color = 0xFFFFFF
                else:
                    macropad.pixels[i] = station.get("color", DEFAULT_COLOR)
                    group[i].color = 0xFFFFFF
                    group[i].background_color = 0x000000
                group[i].text = station.get("name", "?")
            else:
                macropad.pixels[i] = 0
                group[i].text = ""

        macropad.pixels.show()
        macropad.display.refresh()

    def switch_page(self, idx=None):
        """Switch to a new page of stations."""
        if idx is not None:
            self.current_page_index = idx
        macropad.keyboard.release_all()
        macropad.consumer_control.release()
        macropad.mouse.release_all()
        macropad.stop_tone()
        self.update_display()

    def handle_player_events(self):
        """Check for and process incoming messages from the player."""
        if PLAYER.in_waiting > 0:
            lines = PLAYER.read(PLAYER.in_waiting).decode("utf-8").strip().splitlines()
            if not lines:
                return
            try:
                msg = json.loads(lines[-1])
                event = msg.get("event")
                data = msg.get("data")
            except (ValueError, IndexError) as e:
                print(f"PLAYER: failed to parse event: {e}")
                return

            if event == "station_playing":
                self.current_station_index = None
                if not data:
                    self.update_display()
                else:
                    for pidx, page in enumerate(self.pages):
                        for sidx, station in enumerate(page['stations']):
                            if station.get("name") == data:
                                self.current_station_index = sidx
                                self.switch_page(pidx)
                                break
                        if self.current_station_index is not None:
                            break
            else:
                print(f"PLAYER: ignored event: {event}")

    def handle_encoder_rotation(self):
        """Handle the rotary encoder for volume or page switching."""
        position = macropad.encoder
        if position != self.last_position:
            if self.current_station_index is not None:
                direction = "up" if position > self.last_position else "down"
                self.radio_control("volume", direction)
            else:
                if position > self.last_position:
                    self.switch_page((self.current_page_index + 1) % len(self.pages))
                else:
                    self.switch_page((self.current_page_index - 1 + len(self.pages)) % len(self.pages))
            self.last_position = position

    def handle_encoder_press(self):
        """Handle the encoder button press to stop playback."""
        macropad.encoder_switch_debounced.update()
        pressed = macropad.encoder_switch_debounced.pressed
        if pressed != self.last_encoder_switch:
            self.last_encoder_switch = pressed
            if pressed and self.current_station_index is not None:
                self.radio_control("station_request", None)

    def handle_key_events(self):
        """Handle key presses to select a station."""
        event = macropad.keys.events.get()
        if not event:
            return

        page = self.pages[self.current_page_index]
        key_number = event.key_number
        if key_number >= len(page['stations']):
            return

        if event.pressed:
            macropad.pixels[key_number] = PRESSED_COLOR
            macropad.pixels.show()
            station_name = page['stations'][key_number].get("name", "?")
            self.radio_control("station_request", station_name)

    def run(self):
        """The main application loop."""
        self.switch_page(0)
        while True:
            self.handle_player_events()
            self.handle_encoder_rotation()
            self.handle_encoder_press()
            self.handle_key_events()

if __name__ == "__main__":
    app = RadioPadApp()
    app.run()
