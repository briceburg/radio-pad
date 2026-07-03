# SPDX-FileCopyrightText: 2025 Brice Burgess (github.com/briceburg)
# SPDX-License-Identifier: GPL-3.0-or-later

import json
import time

import usb_cdc

from lib.macropad_time import ticks_diff, ticks_ms

PLAYER_SESSION_TIMEOUT_MS = 7000
STATION_MENU_REQUEST_INTERVAL_MS = 3000
SERIAL_WRITE_BACKPRESSURE_SECONDS = 0.1


class MacropadPlayer:
    def __init__(self):
        self.player = usb_cdc.data
        if not self.player:
            raise RuntimeError("No USB CDC data port found.")
        self._serial_buffer = ""
        self._last_station_menu_request_time = 0
        self._last_player_message_time = 0
        self._connected_since = 0

    @property
    def connected(self):
        try:
            connected = self.player.connected
        except Exception as e:
            print(f"PLAYER: error checking connection state: {e}")
            self.reset_session()
            return False

        if connected and not self._connected_since:
            self._connected_since = ticks_ms()
        elif not connected:
            self.reset_session()

        return connected

    @property
    def session_stale(self):
        if not self.connected:
            return False
        last_activity = self._last_player_message_time or self._connected_since
        if not last_activity:
            return False
        return ticks_diff(ticks_ms(), last_activity) > PLAYER_SESSION_TIMEOUT_MS

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
                self._last_player_message_time = ticks_ms()
                return msg
            except Exception as e:
                print(f"PLAYER: error parsing message: {e}")
        return None

    def start_playback(self, call_sign):
        self.send_command("playback_start", {"call_sign": call_sign})

    def stop_playback(self):
        self.send_command("playback_stop")

    def volume_up(self):
        self.send_command("volume_up")

    def volume_down(self):
        self.send_command("volume_down")

    def request_station_menu(self):
        current_time = ticks_ms()
        if ticks_diff(current_time, self._last_station_menu_request_time) >= STATION_MENU_REQUEST_INTERVAL_MS:
            self._last_station_menu_request_time = current_time
            self.send_command("station_menu_request")

    def flush_buffer(self):
        while self.read_event():
            pass

    def reset_session(self):
        self._serial_buffer = ""
        self._last_station_menu_request_time = 0
        self._last_player_message_time = 0
        self._connected_since = 0
