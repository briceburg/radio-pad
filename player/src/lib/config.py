import os
import sys
import time
import json
import urllib.request
from lib.interfaces import RadioPadPlayerConfig, RadioPadStation

def fetch_json_url(url, timeout=12, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, headers={"Accept": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    return json.loads(response.read())
                else:
                    print(f"Failed to fetch JSON: {response.status} from {url}")
        except Exception as e:
            print(f"Attempt {attempt + 1} failed for {url}: {e}")
        print(f"Retrying in {2 ** attempt} seconds...")
        time.sleep(2**attempt)
    return None

def make(player_id, registry_url, stations_url=None, switchboard_url=None, enable_discovery=True):
    """
    Create a RadioPadPlayerConfig object with the provided parameters.
    If enable_discovery is True, attempt to discover missing configuration from the registry.
    """
    if enable_discovery:
        stations_url, switchboard_url = discover_config(player_id, registry_url, stations_url, switchboard_url)

    if not stations_url:
        print("Please set RADIOPAD_STATIONS_URL or enable discovery by providing RADIOPAD_PLAYER_ID.")
        sys.exit(1)

    radio_stations = fetch_json_url(stations_url)
    if not radio_stations:
        print("Station list is empty, exiting.")
        sys.exit(1)

    # Convert station dicts to RadioPadStation objects
    radio_stations = [
        RadioPadStation(**s) if isinstance(s, dict) else s
        for s in radio_stations
    ]

    # Create config object
    return RadioPadPlayerConfig(
        id=player_id,
        stations=radio_stations,
        stations_url=stations_url,
        registry_url=registry_url,
        switchboard_url=switchboard_url,
    )

def discover_config(player_id, registry_url, stations_url=None, switchboard_url=None):
    """Discover missing player configuration from the registry."""

    if stations_url and switchboard_url:
        print("skipping discovery, using provided URLs.")
        return stations_url, switchboard_url

    url = f"{registry_url.rstrip('/')}/v1/players/{player_id}"
    print(
        f"Discovering configuration from {url} ...\n   to skip, set RADIOPAD_ENABLE_DISCOVERY=false"
    )
    data = fetch_json_url(url)
    if data:
        if not stations_url:
            stations_url = data.get("stationsUrl")
        if not switchboard_url:
            switchboard_url = data.get("switchboardUrl")
            
    return stations_url, switchboard_url