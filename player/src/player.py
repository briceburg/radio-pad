#!/usr/bin/env python3

# This file is part of the radio-pad project.
# https://github.com/briceburg/radio-pad
#
# Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import asyncio
import logging
import os
import signal
import sys

import lib.config as config
from lib.client_macropad import MacropadClient
from lib.client_switchboard import SwitchboardClient
from lib.exceptions import ConfigError
from lib.health import DEFAULT_HEALTH_PATH, clear_health, mark_healthy
from lib.interfaces import RadioPadPlayerConfig
from lib.player_mpv import MpvPlayer

logger = logging.getLogger(__name__)


CONFIG_RETRY_SECONDS = 10


async def cleanup(player):
    logger.info("Cleaning up before exit...")
    if hasattr(player, "status_reporter"):
        player.status_reporter = None
    await player.stop()
    for client in player.clients:
        try:
            await client.close()
        except Exception as e:
            logger.error("Error closing client %s: %s", client.__class__.__name__, e)


def _bootstrap_config(player_id, registry_url):
    return RadioPadPlayerConfig(
        id=player_id,
        stations_url=None,
        stations=[],
        registry_url=registry_url,
        switchboard_url=None,
    )


def _config_status_summary(error):
    message = str(error)
    if "Failed fetching stations" in message:
        return "Stations unavailable"
    if "Station URL" in message:
        return "Station config error"
    if "Player must" in message:
        return "Player config error"
    return "Registry unavailable"


async def _load_config_with_retry(player, macropad_client, settings, shutdown_event):
    while not shutdown_event.is_set():
        try:
            player_config = await config.make(**settings)
            player.update_config(player_config)
            await macropad_client.publish_status("upstream", "ok", None)
            return player_config
        except ConfigError as e:
            summary = _config_status_summary(e)
            logger.error("Configuration error: %s", e)
            await macropad_client.publish_status("upstream", "warning", summary)
        except Exception as e:
            logger.error("Unexpected configuration error: %s", e, exc_info=True)
            await macropad_client.publish_status(
                "upstream", "warning", "Registry unavailable"
            )
        logger.info("retrying player configuration in %ss...", CONFIG_RETRY_SECONDS)
        try:
            await asyncio.wait_for(shutdown_event.wait(), timeout=CONFIG_RETRY_SECONDS)
        except asyncio.TimeoutError:
            pass

    return None


def _install_sigterm_handler(shutdown_event):
    loop = asyncio.get_running_loop()

    def request_shutdown():
        if not shutdown_event.is_set():
            logger.info("received SIGTERM, shutting down...")
            shutdown_event.set()

    try:
        loop.add_signal_handler(signal.SIGTERM, request_shutdown)
        return True
    except (NotImplementedError, RuntimeError):
        logger.debug("async SIGTERM handler is not available")
        return False


async def main(player, macropad_client, settings, health_path):
    """Runs the main event loop for the radio-pad player."""
    tasks = [asyncio.create_task(macropad_client.run(), name="MacropadClient.run")]
    shutdown_event = asyncio.Event()
    sigterm_handler_installed = _install_sigterm_handler(shutdown_event)
    try:
        await macropad_client.publish_status("upstream", "loading", None)
        player_config = await _load_config_with_retry(
            player, macropad_client, settings, shutdown_event
        )
        if shutdown_event.is_set() or not player_config:
            return

        if player_config.switchboard_url:

            async def report_upstream_status(level, summary):
                await macropad_client.publish_status("upstream", level, summary)

            switchboard_client = SwitchboardClient(
                player,
                on_connect=lambda: mark_healthy(health_path),
                on_disconnect=lambda: clear_health(health_path),
                status_reporter=report_upstream_status,
            )
            player.register_client(switchboard_client)
            tasks.append(
                asyncio.create_task(
                    switchboard_client.run(),
                    name="SwitchboardClient.run",
                )
            )
        else:
            mark_healthy(health_path)

        shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown.wait")
        tasks.append(shutdown_task)
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            if task is not shutdown_task:
                task.result()

    except asyncio.CancelledError:
        shutdown_event.set()
        raise
    except Exception as e:
        logger.critical("Unexpected error in main: %s", e, exc_info=True)
        raise
    finally:
        if shutdown_event.is_set():
            logger.info("exiting...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await cleanup(player)
        if sigterm_handler_installed:
            asyncio.get_running_loop().remove_signal_handler(signal.SIGTERM)


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)-8s - %(name)-12s - %(message)s",
        datefmt="%H:%M:%S",
    )

    health_path = os.getenv("RADIOPAD_HEALTH_PATH", DEFAULT_HEALTH_PATH)
    clear_health(health_path)
    player = None
    try:
        player_id = os.getenv("RADIOPAD_PLAYER", "briceburg/living-room")
        registry_url = os.getenv(
            "RADIOPAD_REGISTRY_URL", "https://registry.radiopad.dev/api"
        )
        settings = {
            "player": player_id,
            "registry_url": registry_url,
            "stations_url": os.getenv("RADIOPAD_STATIONS_URL", None),
            "switchboard_url": os.getenv("RADIOPAD_SWITCHBOARD_URL", None),
            "enable_discovery": os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true").lower()
            == "true",
        }

        # Initialize player and clients
        player = MpvPlayer(
            _bootstrap_config(player_id, registry_url),
            audio_channels=os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo"),
            socket_path=os.getenv(
                "RADIOPAD_MPV_SOCKET_PATH", "/tmp/radio-pad-mpv.sock"
            ),
        )
        macropad_client = MacropadClient(player)

        async def report_playback_status(level, summary):
            await macropad_client.publish_status("playback", level, summary)

        player.status_reporter = report_playback_status
        player.register_client(macropad_client)

        # Run the main event loop
        asyncio.run(main(player, macropad_client, settings, health_path))

    except (KeyboardInterrupt, EOFError):
        logger.info("Application terminated gracefully.")
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        clear_health(health_path)
