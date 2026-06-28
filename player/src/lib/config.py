import asyncio
import logging
from urllib.parse import urlsplit, urlunsplit

import httpx2

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
    return urlunsplit((scheme, parsed.netloc, f"{switchboard_path}/{account_id}/{player_id}", "", ""))


def _radio_dial_url(registry_url: str, radio_dial: str) -> str:
    parts = radio_dial.split("/")
    if len(parts) != 2 or not all(parts):
        raise ConfigError(
            "Player radio_dial must be in 'account_id/radio_dial_id' format",
            status_summary="RadioDial config error",
        )
    account_id, radio_dial_id = parts
    return f"{registry_url.rstrip('/')}/accounts/{account_id}/radio-dials/{radio_dial_id}"


def http_client_headers(custom_headers=None):
    """Return HTTP client headers with RadioPad user agent, merged with any custom headers"""
    defaults = {
        "User-Agent": "RadioPad/1.0 (Linux; Player) Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko)",
    }
    if custom_headers is None:
        return defaults
    return {**defaults, **custom_headers}


async def fetch_json_url(url, timeout=12, retries=3):
    """Fetch JSON from URL with retries"""
    headers = http_client_headers({"Accept": "application/json"})
    async with httpx2.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
        for attempt in range(retries):
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
                await asyncio.sleep(2**attempt)
    return None


async def make(
    player,
    registry_url,
    radio_dial_url=None,
    switchboard_url=None,
    enable_discovery=True,
):
    """
    Create a RadioPadPlayerConfig object with the provided parameters.
    If enable_discovery is True, attempt to discover missing configuration from the registry.
    """
    if enable_discovery:
        radio_dial_url, switchboard_url = await discover_config(player, registry_url, radio_dial_url, switchboard_url)

    if not radio_dial_url:
        raise ConfigError(
            "Please set RADIOPAD_RADIO_DIAL_URL or enable discovery by providing RADIOPAD_PLAYER.",
            status_summary="RadioDial config error",
        )

    logger.info("Using RadioDial URL: %s", radio_dial_url)
    logger.info("Using switchboard URL: %s", switchboard_url)

    radio_dial = await fetch_json_url(radio_dial_url)
    if not radio_dial:
        raise ConfigError("Failed fetching RadioDial", status_summary="RadioDial unavailable")
    stations = radio_dial.get("stations") if isinstance(radio_dial, dict) else None
    if (
        not isinstance(radio_dial, dict)
        or not isinstance(stations, list)
        or any(
            not isinstance(station, dict)
            or not isinstance(station.get("call_sign"), str)
            or not station["call_sign"]
            or not isinstance(station.get("stream_url"), str)
            or not station["stream_url"]
            for station in stations
        )
        or len({station["call_sign"] for station in stations}) != len(stations)
    ):
        raise ConfigError(
            "RadioDial must contain unique Stations with call_sign and stream_url",
            status_summary="RadioDial config error",
        )

    return RadioPadPlayerConfig(
        stations=[
            RadioPadStation(
                call_sign=station["call_sign"],
                stream_url=station["stream_url"],
            )
            for station in stations
        ],
        radio_dial_url=radio_dial_url,
        switchboard_url=switchboard_url,
    )


async def discover_config(player, registry_url, radio_dial_url=None, switchboard_url=None):
    """Discover missing player configuration from the registry."""

    if radio_dial_url and switchboard_url:
        logger.info("skipping discovery, using provided URLs.")
        return radio_dial_url, switchboard_url

    player_parts = player.split("/")
    if len(player_parts) != 2 or not all(player_parts):
        raise ConfigError(
            "Player must be in 'account_id/player_id' format",
            status_summary="Player config error",
        )
    account_id, player_id = player_parts

    url = f"{registry_url.rstrip('/')}/accounts/{account_id}/players/{player_id}"
    logger.info("Discovering configuration from %s ...", url)
    logger.info("  To skip, set RADIOPAD_ENABLE_DISCOVERY=false")
    data = await fetch_json_url(url)

    if data:
        if not radio_dial_url and data.get("radio_dial"):
            radio_dial_url = _radio_dial_url(registry_url, data["radio_dial"])
        switchboard_url = switchboard_url or data.get("switchboard_url")

    if not switchboard_url:
        switchboard_url = _infer_switchboard_url(registry_url, account_id, player_id)

    return radio_dial_url, switchboard_url
