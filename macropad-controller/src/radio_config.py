# Shared configuration for macropad controller (CircuitPython compatible)

# UI Constants
DEFAULT_COLOR = 0x000077
HIGHLIGHT_COLOR = 0x015C01
PRESSED_COLOR = 0x999999

# Hardware Settings
LED_BRIGHTNESS = 0.10
MACROPAD_KEY_COUNT = 12

# Files
RADIO_STATIONS_FILE = "stations.json"

# Event types
EVENTS = {
    "STATION_PLAYING": "station_playing",
    "STATION_REQUEST": "station_request", 
    "VOLUME": "volume"
}