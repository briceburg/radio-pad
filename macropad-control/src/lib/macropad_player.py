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

import json
import time

import usb_cdc

PLAYER_SESSION_TIMEOUT_SECONDS = 5
SERIAL_WRITE_BACKPRESSURE_SECONDS = 0.1


class MacropadPlayer:
    def __init__(self):
        self.player = usb_cdc.data
        if not self.player:
            raise RuntimeError("No USB CDC data port found.")
        self._serial_buffer = ""
        self._last_station_request_time = 0
        self._last_player_message_time = 0.0

    @property
    def connected(self):
        try:
            return bool(self.player.connected)
        except Exception as e:
            print(f"PLAYER: error checking connection state: {e}")
            return False

    @property
    def session_connected(self):
        return self.connected and (
            time.monotonic() - self._last_player_message_time
            < PLAYER_SESSION_TIMEOUT_SECONDS
        )

    def send_command(self, event, data=None):
        if not self.connected:
            return

        message = json.dumps({"event": event, "data": data})
        try:
            self.player.write(f"{message}\n".encode())
            time.sleep(SERIAL_WRITE_BACKPRESSURE_SECONDS)
        except Exception as e:
            print(f"PLAYER: error sending command: {e}")
            self.reset_session()

    def read_event(self):
        try:
            in_waiting = self.player.in_waiting
        except Exception as e:
            print(f"PLAYER: error checking serial buffer: {e}")
            self.reset_session()
            return None

        if "\n" not in self._serial_buffer and in_waiting > 0:
            try:
                self._serial_buffer += self.player.read(in_waiting).decode("utf-8")
            except Exception as e:
                print(f"PLAYER: error reading serial buffer: {e}")
                self.reset_session()
                return None

        if "\n" in self._serial_buffer:
            line, self._serial_buffer = self._serial_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                return None
            try:
                msg = json.loads(line)
                self._last_player_message_time = time.monotonic()
                return msg
            except Exception as e:
                print(f"PLAYER: error parsing message: {e}")
        return None

    def request_stations(self):
        current_time = time.monotonic()
        if current_time - self._last_station_request_time >= 3:
            self._last_station_request_time = current_time
            self.send_command("station_list")

    def flush_buffer(self):
        while self.read_event():
            pass

    def reset_session(self):
        self._serial_buffer = ""
        self._last_player_message_time = 0.0
