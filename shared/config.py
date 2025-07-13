"""
Shared configuration management for radio-pad components.
Centralizes environment variables and default values.
"""
import os


class Config:
    """Centralized configuration for radio-pad components."""
    
    # Network settings
    SWITCHBOARD_HOST = os.getenv("SWITCHBOARD_HOST", "localhost")
    SWITCHBOARD_PORT = int(os.getenv("SWITCHBOARD_PORT", 1980))
    SWITCHBOARD_URL = os.getenv("SWITCHBOARD_URL", f"ws://{SWITCHBOARD_HOST}:{SWITCHBOARD_PORT}/")
    
    # Audio settings  
    AUDIO_CHANNELS = os.getenv("AUDIO_CHANNELS", "stereo")
    
    # File paths
    MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"
    RADIO_STATIONS_FILE = "/tmp/radio-pad-stations.json"
    
    # URLs
    RADIO_STATIONS_URL = os.getenv(
        "RADIO_STATIONS_URL",
        "https://raw.githubusercontent.com/briceburg/radio-pad/refs/heads/main/player/stations.json"
    )
    
    # Macropad settings
    MACROPAD_KEY_COUNT = 12
    LED_BRIGHTNESS = 0.10
    
    # UI settings
    DEFAULT_COLOR = 0x000077
    HIGHLIGHT_COLOR = 0x015C01
    PRESSED_COLOR = 0x999999
    
    # Timeouts and delays
    MPV_IPC_RETRIES = 20
    MPV_IPC_RETRY_DELAY = 0.1
    RECONNECT_DELAY = 5
    MACROPAD_RECONNECT_DELAY = 10