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
from lib.player_mpv import MpvPlayer

logger = logging.getLogger(__name__)


async def cleanup(player):
    logger.info("Cleaning up before exit...")
    await player.stop()
    for client in player.clients:
        try:
            await client.close()
        except Exception as e:
            logger.error("Error closing client %s: %s", client.__class__.__name__, e)


async def run_clients(player):
    async with asyncio.TaskGroup() as task_group:
        for client in player.clients:
            task_group.create_task(
                client.run(),
                name=f"{client.__class__.__name__}.run",
            )


async def main(player):
    """Runs the main event loop for the radio-pad player."""
    try:
        try:
            await run_clients(player)
        except* Exception as exc_group:
            logger.critical("Unexpected error in main: %s", exc_group, exc_info=True)
            raise
    except asyncio.CancelledError:
        logger.info("exiting...")
        await cleanup(player)
        raise
    except Exception:
        await cleanup(player)
        raise


def handle_sigterm(signum, frame):
    """Handle Docker stopping the container by gracefully propagating a KeyboardInterrupt."""
    raise KeyboardInterrupt()


if __name__ == "__main__":
    # Map SIGTERM to KeyboardInterrupt so the player softly exits when docker compose downs
    signal.signal(signal.SIGTERM, handle_sigterm)

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
        # Load configuration
        player_config = asyncio.run(
            config.make(
                player=os.getenv("RADIOPAD_PLAYER", "briceburg/living-room"),
                registry_url=os.getenv(
                    "RADIOPAD_REGISTRY_URL", "https://registry.radiopad.dev/api"
                ),
                stations_url=os.getenv("RADIOPAD_STATIONS_URL", None),
                switchboard_url=os.getenv("RADIOPAD_SWITCHBOARD_URL", None),
                enable_discovery=os.getenv("RADIOPAD_ENABLE_DISCOVERY", "true").lower()
                == "true",
            )
        )

        # Initialize player and clients
        player = MpvPlayer(
            player_config,
            audio_channels=os.getenv("RADIOPAD_AUDIO_CHANNELS", "stereo"),
            socket_path=os.getenv(
                "RADIOPAD_MPV_SOCKET_PATH", "/tmp/radio-pad-mpv.sock"
            ),
        )
        macropad_client = MacropadClient(player)

        async def report_playback_status(summary):
            await macropad_client.publish_status("playback", summary)

        async def report_upstream_status(summary):
            await macropad_client.publish_status("upstream", summary)

        player.status_reporter = report_playback_status
        player.register_client(macropad_client)
        if player.config.switchboard_url:
            player.register_client(
                SwitchboardClient(
                    player,
                    on_connect=lambda: mark_healthy(health_path),
                    on_disconnect=lambda: clear_health(health_path),
                    status_reporter=report_upstream_status,
                )
            )
        else:
            mark_healthy(health_path)
            player.register_client(SwitchboardClient(player))

        # Run the main event loop
        asyncio.run(main(player))

    except ConfigError as e:
        logger.critical("Configuration error: %s", e)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        # KeyboardInterrupt handles SIGINT (Ctrl+C) and SIGTERM (via handle_sigterm)
        logger.info("Application terminated gracefully.")
    except Exception as e:
        logger.critical("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        clear_health(health_path)
