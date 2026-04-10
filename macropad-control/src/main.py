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

import time

from adafruit_macropad import MacroPad

from lib.macropad_display import MacropadDisplay
from lib.macropad_keys import DEFAULT_COLOR, PRESSED_COLOR, MacropadKeys
from lib.macropad_player import MacropadPlayer

LOOP_SLEEP_SECONDS = 0.01
STATUS_SCOPES = ("upstream", "playback")


class MacropadApp:
    def __init__(self):
        self.macropad = MacroPad()
        self.display = MacropadDisplay(self.macropad)
        self.keys = MacropadKeys(self.macropad, self.display)
        self.player = MacropadPlayer()

        self.last_position = self.macropad.encoder
        self.last_encoder_switch = self.macropad.encoder_switch_debounced.pressed
        self.had_stations = False
        self.was_connected = False
        self.status_by_scope = {scope: "" for scope in STATUS_SCOPES}

    def run(self):
        while True:
            self.tick()
            time.sleep(LOOP_SLEEP_SECONDS)

    def tick(self):
        event = self.player.read_event()

        if not self.player.session_connected:
            self._handle_disconnected_state(event)
            self.keys.tick()
            return

        if not self.was_connected:
            self._refresh_visual_state()
            self.was_connected = True

        if not self.had_stations:
            self.player.request_stations()

        self._handle_player_event(event)
        self._handle_encoder_rotation()
        self._handle_encoder_press()
        self._handle_key_events()
        self.keys.tick()

    def _handle_disconnected_state(self, event):
        self._handle_player_event(event)

        if self.player.session_connected:
            self._refresh_visual_state()
            self.was_connected = True
            return

        if self.had_stations:
            self.keys.set_stations([])
            self.keys.set_playing_station(None)
            self.had_stations = False

        if self.was_connected or any(self.status_by_scope.values()):
            self.player.flush_buffer()
            self.player.reset_session()

        self.was_connected = False
        self._clear_statuses()
        self._refresh_visual_state()

        if self.player.connected:
            self.player.request_stations()

    def _handle_player_event(self, event):
        if not event:
            return

        event_name = event.get("event")
        data = event.get("data")

        if event_name == "station_list":
            self._set_station_list(data)
            return

        if event_name == "station_playing":
            self.keys.set_playing_station(data)
            return

        if event_name == "player_status":
            self._update_status(data)
            self._refresh_visual_state()
            return

        if event_name != "player_heartbeat":
            print(f"Received event: {event}")

    def _set_station_list(self, stations):
        station_list = [{"name": station, "color": DEFAULT_COLOR} for station in stations]
        self.keys.set_stations(station_list)
        self.had_stations = True
        self._refresh_visual_state()

    def _handle_encoder_rotation(self):
        position = self.macropad.encoder
        if position == self.last_position:
            return

        if self.keys.playing_station_index is not None:
            direction = "up" if position > self.last_position else "down"
            self.player.send_command("volume", direction)
        else:
            page_count = len(self.keys.pages)
            direction = 1 if position > self.last_position else -1
            next_page = (self.keys.current_page_index + direction) % page_count
            self.keys.switch_page(next_page)

        self.last_position = position

    def _handle_encoder_press(self):
        self.macropad.encoder_switch_debounced.update()
        pressed = self.macropad.encoder_switch_debounced.pressed
        if pressed and not self.last_encoder_switch:
            if self.keys.playing_station_index is not None:
                self.player.send_command("station_request", None)
                self.keys.flash_keys()
        self.last_encoder_switch = pressed

    def _handle_key_events(self):
        station_name = self._drain_pressed_station_name()
        if station_name:
            self.player.send_command("station_request", station_name)

    def _drain_pressed_station_name(self):
        last_pressed_station = None
        while True:
            key_event = self.macropad.keys.events.get()
            if not key_event:
                return last_pressed_station
            if not key_event.pressed:
                continue

            key_number = key_event.key_number
            station_name = self.keys.get_station_name(key_number)
            if station_name:
                self.keys.set_key_color(key_number, PRESSED_COLOR)
                last_pressed_station = station_name

    def _update_status(self, status_event):
        if not isinstance(status_event, dict):
            print(f"Unexpected player_status payload: {status_event}")
            return

        scope = status_event.get("scope")
        summary = status_event.get("summary")

        if scope not in self.status_by_scope:
            print(f"Unexpected player_status scope: {scope}")
            return

        if isinstance(summary, str):
            self.status_by_scope[scope] = summary
            return

        if summary is not None:
            print(f"Unexpected player_status summary: {summary}")
        self.status_by_scope[scope] = ""

    def _clear_statuses(self):
        for scope in self.status_by_scope:
            self.status_by_scope[scope] = ""

    def _refresh_visual_state(self):
        self.keys.set_waiting_animation(self._waiting_mode())
        self.keys.set_upstream_warning(
            self.had_stations and bool(self.status_by_scope["upstream"])
        )
        self.keys.set_title_override(self._title_override())

    def _waiting_mode(self):
        if not self.player.session_connected:
            return "disconnected"
        if not self.had_stations:
            return "loading"
        return None

    def _title_override(self):
        if not self.player.session_connected:
            return "Waiting for Player"

        for scope in ("playback", "upstream"):
            status = self.status_by_scope[scope]
            if status:
                return status

        if not self.had_stations:
            return "Loading stations"

        return None


MacropadApp().run()
