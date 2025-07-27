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

import websockets

from lib.interfaces import RadioPadClient, RadioPadPlayer

logger = logging.getLogger("SWITCHBOARD")

MPV_SOCKET_FILE = "/tmp/radio-pad-mpv.sock"


class SwitchboardClient(RadioPadClient):
    def __init__(self, player: RadioPadPlayer):
        super().__init__(player)
        self.url = player.config.switchboard_url
        self.ws = None

        self.http_headers = {
            "User-Agent": "RadioPad/1.0",
            "RadioPad-Stations-Url": player.config.stations_url,
        }

    async def run(self):
        if not self.url:
            logger.info("skipping switchboard connection, url not provided.")
            return

        while True:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)
            logger.info("reconnecting to switchboard in 5s...")
            await asyncio.sleep(5)

    async def _connect_and_listen(self):
        async for ws in websockets.connect(
            self.url, additional_headers=self.http_headers
        ):
            try:
                logger.info(f"connected to: {self.url}")
                self.ws = ws
                asyncio.create_task(self.broadcast("station_playing"))
                async for msg in ws:
                    await self.handle_message(msg)
            except websockets.exceptions.ConnectionClosed:
                # If the connection fails with a transient error, it is retried with exponential backoff. If it fails with a fatal error, the exception is raised, breaking out of the loop.
                self.ws = None
                continue
            except (ConnectionRefusedError, OSError) as e:
                logger.warning(f"failed to connect to {self.url}: {e}")
                logger.warning(
                    "If this is the wrong URL, please set the SWITCHBOARD_URL environment variable."
                )
                continue

    async def _send(self, message):
        """Send a message to the macropad or switchboard."""
        if self.ws:
            await self.ws.send(message)

    async def close(self):
        if self.ws:
            await self.ws.close()
