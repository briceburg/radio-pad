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
import traceback
import json

from lib.interfaces import RadioPadClient, RadioPadPlayer


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
                print(f"MACROPAD: Unexpected error: {e}")
                traceback.print_exc()
            finally:
                if self.writer:
                    try:
                        self.writer.close()
                        await self.writer.wait_closed()
                    except Exception as e:
                        print(
                            f"MACROPAD: error during wait_closed (likely unplugged): {e}"
                        )
                    self.writer = None
                    self.reader = None

            print("MACROPAD: reconnecting in 3s...")
            await asyncio.sleep(3)

    async def _connect(self):
        macropad_ports = [
            port.device
            for port in serial.tools.list_ports.comports()
            if port.interface and port.interface.startswith("CircuitPython CDC2")
        ]

        if not macropad_ports:
            print("MACROPAD: no data ports found, is it plugged in?")
            return None, None

        print(f"MACROPAD: found ports: {macropad_ports}")
        for macropad_port in macropad_ports:
            print(f"MACROPAD: attempting to connect to {macropad_port}")
            try:
                reader, writer = await serial_asyncio.open_serial_connection(
                    url=macropad_port, baudrate=115200
                )
                print(f"MACROPAD: connected to: {macropad_port}")
                return reader, writer
            except Exception as e:
                print(f"MACROPAD: failed to connect to {macropad_port}: {e}")
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

        if last_line:

            class LastLineReader:
                def __init__(self, last_line, reader):
                    self._last_line = last_line
                    self._reader = reader
                    self._used = False

                async def readline(self):
                    if not self._used:
                        self._used = True
                        return self._last_line
                    return await self._reader.readline()

            self.reader = LastLineReader(last_line, self.reader)

        # Listen for messages
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
                print(f"MACROPAD: error reading message: {e}")
                break

    async def _send(self, message: str):
        if self.writer:
            try:
                self.writer.write((message + "\n").encode())
                await self.writer.drain()
            except Exception as e:
                print(f"MACROPAD: Failed to send: {e}")

    async def _handle_station_list(self, event):
        stations_no_url = [
            {k: v for k, v in station.items() if k != "url"}
            for station in self.player.config.stations
        ]
        await self.broadcast("station_list", data=stations_no_url)
        await asyncio.sleep(0.1)  # Handle backpressure
        await self.broadcast("station_playing")

    async def close(self):
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
