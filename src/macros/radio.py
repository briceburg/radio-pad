from adafruit_hid.keycode import Keycode  # REQUIRED if using Keycode.* values
import json

# Load stations from ../config/stations.json
stations_path = "config/stations.json"
with open(stations_path, "r") as f:
    RADIO_STATIONS = json.load(f)

default_color = 0x000077  # Default color for station buttons.
default_tuple = (
    0x000000,
    "",
    [],
)  # Default tuple for buttons not assigned to a station.
encoder_tuple = (0x000000, "", [Keycode.BACKSPACE])  # Encoder button tuple, TODO: mute?


def normalize_station_list(stations):
    # Ensure the list has exactly 12 entries
    stations = stations[:12]  # Truncate if more than 12
    while len(stations) < 12:
        stations.append({"name": "", "url": ""})
    return stations


stations = normalize_station_list(RADIO_STATIONS)

page = 0  # Current page of stations, not used in this example.


def index_to_char(idx):
    """
    Convert an integer index to a single character:
    0-9 -> '0'-'9', 10-35 -> 'a'-'z'.
    """
    if 0 <= idx <= 9:
        return str(idx)
    elif 10 <= idx <= 35:
        return chr(ord("a") + (idx - 10))
    else:
        raise ValueError("Index out of supported range (0-35)")


macros = []
for i, station in enumerate(stations):
    if station["name"] and station["url"]:
        macros.append(
            (
                default_color,
                station["name"],
                [
                    Keycode.CONTROL,
                    Keycode.TWO,
                    -Keycode.CONTROL,
                    index_to_char(page),
                    index_to_char(i),
                ],
            )
        )
    else:
        macros.append(default_tuple)

# ensure the encoder button is always the last entry
macros.append(encoder_tuple)

app = {"name": "iCEBURG RADIO", "macros": macros}
