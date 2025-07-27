import json
import logging
import time
import urllib.request

from lib.exceptions import ConfigError
from lib.interfaces import RadioPadPlayerConfig, RadioPadStation

logger = logging.getLogger("CONFIG")


def fetch_json_url(url, timeout=12, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    return json.loads(response.read())
                else:
                    logger.warning(
                        "Failed to fetch JSON: %s from %s", response.status, url
                    )
        except Exception as e:
            logger.warning("Attempt %s failed for %s: %s", attempt + 1, url, e)
        logger.info("Retrying in %s seconds...", 2**attempt)
        time.sleep(2**attempt)
    return None


def make(
    player_id,
    registry_url,
    stations_url=None,
    switchboard_url=None,
    enable_discovery=True,
):
    """
    Create a RadioPadPlayerConfig object with the provided parameters.
    If enable_discovery is True, attempt to discover missing configuration from the registry.
    """
    if enable_discovery:
        stations_url, switchboard_url = discover_config(
            player_id, registry_url, stations_url, switchboard_url
        )

    if not stations_url:
        raise ConfigError(
            "Please set RADIOPAD_STATIONS_URL or enable discovery by providing RADIOPAD_PLAYER_ID."
        )

    radio_stations = fetch_json_url(stations_url)
    if not radio_stations:
        raise ConfigError("Station list is empty, exiting.")

    # Convert station dicts to RadioPadStation objects
    radio_stations = [
        RadioPadStation(**s) if isinstance(s, dict) else s for s in radio_stations
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
        logger.info("skipping discovery, using provided URLs.")
        return stations_url, switchboard_url

    url = f"{registry_url.rstrip('/')}/v1/players/{player_id}"
    logger.info("Discovering configuration from %s ...", url)
    logger.info("  To skip, set RADIOPAD_ENABLE_DISCOVERY=false")
    data = fetch_json_url(url)
    if data:
        if not stations_url:
            stations_url = data.get("stationsUrl")
        if not switchboard_url:
            switchboard_url = data.get("switchboardUrl")

    return stations_url, switchboard_url
