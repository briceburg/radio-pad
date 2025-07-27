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
import serial_asyncio
import serial.tools.list_ports
import logging
import json

from lib.interfaces import RadioPadClient, RadioPadPlayer

logger = logging.getLogger('MACROPAD')

DATA_INTERFACE_NAME = "CircuitPython CDC2"


class MacropadClient(RadioPadClient):
    def __init__(self, player: RadioPadPlayer):
        super().__init__(player)
        self.writer = None
        self.reader = None

        # Override station_list handler
        self.register_event("station_list", self._handle_station_list)

    async def run(self):
        while True:
            try:
                await self._connect_and_listen()
            except Exception as e:
                logger.error("Unexpected error: %s", e, exc_info=True)
            finally:
                if self.writer:
                    try:
                        self.writer.close()
                        await self.writer.wait_closed()
                    except Exception as e:
                        logger.warning("error during wait_closed (likely unplugged): %s", e)
                    self.writer = None
                    self.reader = None

            logger.info("reconnecting in 3s...")
            await asyncio.sleep(3)

    async def _connect(self):
        macropad_ports = [
            port.device
            for port in serial.tools.list_ports.comports()
            if port.interface and port.interface.startswith(DATA_INTERFACE_NAME)
        ]

        if not macropad_ports:
            logger.warning("no data ports found, is it plugged in?")
            return None, None

        logger.info("found ports: %s", macropad_ports)
        for macropad_port in macropad_ports:
            logger.info("attempting to connect to %s", macropad_port)
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=macropad_port, baudrate=115200
                )
                logger.info("connected to: %s", macropad_port)
                return reader, writer
            except Exception as e:
                logger.warning("failed to connect to %s: %s", macropad_port, e)
                continue
        return None, None

    async def _connect_and_listen(self):
        self.reader, self.writer = await self._connect()

        if not self.writer:
            return

        # Clear all pending serial messages except the last one
        last_line = None
        try:
            while True:
                line = await asyncio.wait_for(self.reader.readline(), timeout=0.1)
                if not line:
                    break
                last_line = line
        except asyncio.TimeoutError:
            pass  # Ignore timeout

        # Process the last received line if it exists
        if last_line:
            try:
                msg = last_line.decode("utf-8").strip()
                if msg:
                    await self.handle_message(msg)
            except Exception as e:
                logger.error("error processing last message: %s", e)

        # Listen for new messages
        await self._listen()

    async def _listen(self):
        buffer = ""
        while True:
            try:
                line = await self.reader.readline()
                if not line:
                    break
                buffer += line.decode("utf-8")
                while "\n" in buffer:
                    msg, buffer = buffer.split("\n", 1)
                    msg = msg.strip()
                    if not msg:
                        continue
                    await self.handle_message(msg)
            except Exception as e:
                logger.error("error reading message: %s", e)
                break

    async def _send(self, message: str):
        if self.writer:
            try:
                self.writer.write((message + "\n").encode())
                await self.writer.drain()
            except Exception as e:
                logger.error("Failed to send: %s", e)

    async def _handle_station_list(self, event):
        station_list = [station.name for station in self.player.config.stations]
        await self.broadcast("station_list", data=station_list)
        await asyncio.sleep(0.1)  # Handle backpressure
        await self.broadcast("station_playing")

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
