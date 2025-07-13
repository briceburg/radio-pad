"""
Station management for radio-pad.
Handles loading and managing radio station data.
"""
import json
import logging
import os
import urllib.request
from typing import List, Optional, Dict, Any

from shared.config import Config


class StationManager:
    """Manages radio station data and loading."""
    
    def __init__(self):
        self.stations: List[Dict[str, Any]] = []
        self._loaded = False
    
    async def load_stations(self) -> bool:
        """Load stations from file or URL. Returns success status."""
        if self._loaded:
            return True
            
        try:
            # Download stations if file doesn't exist
            if not os.path.exists(Config.RADIO_STATIONS_FILE):
                logging.info(f"Downloading stations from {Config.RADIO_STATIONS_URL}")
                urllib.request.urlretrieve(Config.RADIO_STATIONS_URL, Config.RADIO_STATIONS_FILE)
            
            # Load stations from file
            with open(Config.RADIO_STATIONS_FILE, "r") as f:
                self.stations = json.load(f)
            
            logging.info(f"Loaded {len(self.stations)} radio stations")
            self._loaded = True
            return True
            
        except Exception as e:
            logging.error(f"Failed to load stations: {e}")
            return False
    
    def find_station_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a station by name."""
        for station in self.stations:
            if station.get("name") == name:
                return station
        return None
    
    def get_all_stations(self) -> List[Dict[str, Any]]:
        """Get all loaded stations."""
        return self.stations.copy()
    
    def get_station_count(self) -> int:
        """Get the number of loaded stations."""
        return len(self.stations)