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
from lib.interfaces import RadioPadClient, RadioPadPlayer


class MacropadClient(RadioPadClient):
    def __init__(self, player: RadioPadPlayer):
        super().__init__(player)
        self.serial_writer = None
        # Override station_list handler for macropad-specific behavior
        self.register_event("station_list", self._handle_station_list_macropad)

    async def run(self):
        """Connect to macropad and listen for events with auto-reconnect."""
        while True:
            try:
                reader, writer = await self._connect_to_macropad()
                self.serial_writer = writer

                if self.serial_writer:
                    # Clear all pending serial messages except the last one
                    # this will preserve the last station request from macropad.
                    last_line = None
                    try:
                        while True:
                            line = await asyncio.wait_for(reader.readline(), timeout=0.1)
                            if not line:
                                break
                            last_line = line
                    except Exception:
                        pass  # Ignore timeout or empty buffer

                    # If we found any lines, keep only the last one
                    if last_line:
                        # Put the last line back into the buffer for processing
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

                        reader = LastLineReader(last_line, reader)

                    # Listen for messages from macropad
                    await self._message_loop(reader)

            except Exception as e:
                print(f"MACROPAD: Unexpected error: {e}")
                traceback.print_exc()
            finally:
                if self.serial_writer:
                    try:
                        self.serial_writer.close()
                        await self.serial_writer.wait_closed()
                    except Exception as e:
                        print(f"MACROPAD: error during wait_closed (likely unplugged): {e}")
                    self.serial_writer = None

            print("MACROPAD: reconnecting in 3s...")
            await asyncio.sleep(3)

    async def _connect_to_macropad(self):
        """
        Find and connect to the first available macropad data port (CDC2).
        Returns (reader, writer) tuple, or (None, None) if not found.
        """
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
                continue  # Try next port
        return None, None

    async def _message_loop(self, reader):
        """
        Listen for messages from the macropad and handle events.
        """
        macropad_buffer = ""
        while True:
            try:
                line = await reader.readline()
                if not line:
                    break
                macropad_buffer += line.decode("utf-8")
                while "\n" in macropad_buffer:
                    msg, macropad_buffer = macropad_buffer.split("\n", 1)
                    msg = msg.strip()
                    if not msg:
                        continue
                    await self.handle_message(msg)
            except Exception as e:
                print(f"MACROPAD: error reading message: {e}")
                break

    async def _send(self, message: str):
        """Send a message to the macropad."""
        if self.serial_writer:
            try:
                self.serial_writer.write((message + "\n").encode())
                await self.serial_writer.drain()
            except Exception as e:
                print(f"MACROPAD: Failed to send message: {e}")

    async def _handle_station_list_macropad(self, event):
        """Handle station_list events specifically for macropad."""
        # Send list of stations to macropad, stripping "url" key
        stations_no_url = [
            {"name": station.name, "color": station.color}
            for station in self.player.config.stations
        ]
        await self.broadcast("station_list", data=stations_no_url)
        await asyncio.sleep(0.1)  # Handle backpressure
        await self.broadcast("station_playing")