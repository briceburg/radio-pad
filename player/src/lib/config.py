import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx

from lib.exceptions import ConfigError
from lib.interfaces import RadioPadPlayerConfig, RadioPadStation

logger = logging.getLogger("CONFIG")


def _infer_switchboard_url(registry_url: str, account_id: str, player_id: str) -> str:
    parsed = urlsplit(registry_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    api_path = parsed.path.rstrip("/")
    if api_path.endswith("/api"):
        switchboard_path = f"{api_path[:-4]}/switchboard"
    else:
        switchboard_path = f"{api_path}/switchboard"
    return urlunsplit(
        (scheme, parsed.netloc, f"{switchboard_path}/{account_id}/{player_id}", "", "")
    )


def http_client_headers(custom_headers=None):
    """Return HTTP client headers with RadioPad user agent, merged with any custom headers"""
    defaults = {
        "User-Agent": f"RadioPad/1.0 (Linux; Player) Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko)",
    }
    if custom_headers is None:
        return defaults
    return {**defaults, **custom_headers}


async def fetch_json_url(url, timeout=12, retries=3, on_status=None):
    """Fetch JSON from URL with retries"""
    headers = http_client_headers({"Accept": "application/json"})
    async with httpx.AsyncClient(
        timeout=timeout, headers=headers, follow_redirects=True
    ) as client:
        for attempt in range(retries):
            if on_status and attempt == 0:
                on_status("Fetching registry...")
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.warning(
                        "Failed to fetch JSON: %s from %s",
                        response.status_code,
                        url,
                    )
            except Exception as e:
                logger.warning("Attempt %s failed for %s: %s", attempt + 1, url, e)
            if attempt < retries - 1:
                logger.info("Retrying in %s seconds...", 2**attempt)
                if on_status:
                    on_status(f"Net error, retry {attempt + 1}")
                await asyncio.sleep(2**attempt)
    return None


async def make(
    player,
    registry_url,
    stations_url=None,
    switchboard_url=None,
    enable_discovery=True,
    on_status=None,
):
    """
    Create a RadioPadPlayerConfig object with the provided parameters.
    If enable_discovery is True, attempt to discover missing configuration from the registry.
    """
    if enable_discovery:
        if on_status:
            on_status("Discovering player...")
        stations_url, switchboard_url = await discover_config(
            player, registry_url, stations_url, switchboard_url, on_status=on_status
        )

    if not stations_url:
        raise ConfigError(
            "Please set RADIOPAD_STATIONS_URL or enable discovery by providing RADIOPAD_PLAYER."
        )

    logger.info("Using stations_url: %s", stations_url)
    logger.info("Using switchboard_url: %s", switchboard_url)

    if on_status:
        on_status("Fetching stations...")
    station_data = await fetch_json_url(stations_url, on_status=on_status)
    if not station_data:
        raise ConfigError("Failed fetching stations")
    if (
        not isinstance(station_data, dict)
        or "name" not in station_data
        or "stations" not in station_data
    ):
        raise ConfigError(
            'Station URL must return \'{"name": str, "stations": [{...}]}\''
        )

    # Create config object
    return RadioPadPlayerConfig(
        id=player,
        stations=[RadioPadStation(**s) for s in station_data["stations"]],
        stations_url=stations_url,
        registry_url=registry_url,
        switchboard_url=switchboard_url,
    )


async def discover_config(
    player, registry_url, stations_url=None, switchboard_url=None, on_status=None
):
    """Discover missing player configuration from the registry."""

    if stations_url and switchboard_url:
        logger.info("skipping discovery, using provided URLs.")
        return stations_url, switchboard_url

    try:
        account_id, player_id = player.split("/", 1)
    except ValueError:
        raise ConfigError("Player must be in 'account_id/player_id' format")

    url = f"{registry_url.rstrip('/')}/accounts/{account_id}/players/{player_id}"
    logger.info("Discovering configuration from %s ...", url)
    logger.info("  To skip, set RADIOPAD_ENABLE_DISCOVERY=false")
    data = await fetch_json_url(url, on_status=on_status)

    if data:
        stations_url = stations_url or data.get("stations_url")
        switchboard_url = switchboard_url or data.get("switchboard_url")

    # If the registry didn't provide URLs (e.g. they're omitted on the backend),
    # infer them locally using the known registry endpoint as a base.
    if not stations_url:
        stations_url = f"{registry_url.rstrip('/')}/presets/{account_id}"

    if not switchboard_url:
        # Fallback assumes the switchboard is deployed at the same domain/port as the registry
        switchboard_url = _infer_switchboard_url(registry_url, account_id, player_id)

    return stations_url, switchboard_url
