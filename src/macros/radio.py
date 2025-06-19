from adafruit_hid.keycode import Keycode  # REQUIRED if using Keycode.* values
import json
import os

RADIO_STATIONS = [
    {"name": "wwoz", "url": "https://www.wwoz.org/listen/hi"},
    {"name": "wmse", "url": "https://wmse.streamguys1.com/wmselivemp3"},
    {"name": "gmcr", "url": "http://stream.gmcr.org:8000/gmcr"},
    {"name": "kunm","url": "https://playerservices.streamtheworld.com/api/livestream-redirect/KUNMFM_128.mp3"},
    {"name": "kmkb", "url": "http://50.19.66.66:8000/kmkb"},
    {"name": "kmrd", "url": "https://kmrd.broadcasttool.stream/listen"},
    {"name": "kkfi", "url": "https://stream.pacificaservice.org:9000/kkfi_128"},
    {"name": "wqxr", "url": "https://stream.wqxr.org/wqxr-web?nyprBrowserId="},
    {"name": "wtju", "url": "https://streams.wtju.net/wtju-live.mp3"},
    {"name": "lofi", "url": "https://www.youtube.com/watch?v=5qap5aO4i9A"},
    {"name": "kboo", "url": "https://live.kboo.fm:8443/high"}
]

# Load stations from ../config/stations.json
# stations_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../config/stations.json"))
# with open(stations_path, "r") as f:
#     RADIO_STATIONS = json.load(f)

hotkey = Keycode.F12  # Hotkey to trigger the radio-pad functionality.
default_color = 0x202000  # Default color for station buttons.
default_tuple = (0x000000, "", [])  # Default tuple for buttons not assigned to a station.
encoder_tuple = (0x000000, "", [Keycode.BACKSPACE])  # Encoder button tuple, TODO: mute?

def normalize_station_list(stations):
    # Ensure the list has exactly 12 entries
    stations = stations[:12]  # Truncate if more than 12
    while len(stations) < 12:
        stations.append({"name": "", "url": ""})
    return stations

stations = normalize_station_list(RADIO_STATIONS)

macros = []
for i, station in enumerate(stations):
    if station["name"] and station["url"]:
        # Create a macro for each station with a name and URL
        macros.append((default_color, station["name"], [hotkey, -Keycode.COMMAND, station["name"], hotkey]))
    else:
        # Create a default button for empty slots
        macros.append(default_tuple)

# ensure the encoder button is always the last entry
macros.append(encoder_tuple)

app = {
    "name": "iCEBURG RADIO",
    "macros": macros
}
