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

macropad = MacroPad()
display = MacropadDisplay(macropad)
keys = MacropadKeys(macropad, display)
player = MacropadPlayer()

last_position = macropad.encoder
last_encoder_switch = macropad.encoder_switch_debounced.pressed
had_stations = False
was_connected = False
upstream_status = ""

display.set_title("Connect to Player")
display.set_status("")


def refresh_status(connected, status_message, station_state_ready):
    if not connected:
        display.set_status("", False)
        return

    status = status_message
    if not status and not station_state_ready:
        status = "Loading stations..."
    display.set_status(status, False)


while True:
    # --- Player Connection ---
    if player.connected:
        if not was_connected:
            display.set_title("Player connected", False)
            refresh_status(player.connected, upstream_status, had_stations)
            display.refresh()
            was_connected = True
        if not had_stations:
            player.request_stations()
    else:
        should_reset_display = had_stations or was_connected or bool(upstream_status)
        if had_stations:
            keys.set_stations([])
            had_stations = False
        if was_connected or upstream_status:
            player.flush_buffer()
        was_connected = False
        upstream_status = ""
        if should_reset_display:
            display.set_title("Connect to Player", False)
            display.set_status("", False)
            display.refresh()
        time.sleep(0.01)
        continue

    # --- Player Events ---
    event = player.read_event()
    if event:
        print(f"Received event: {event}")
        event_name = event.get("event")
        data = event.get("data")

        if event_name == "station_list":
            station_list = [
                {"name": station, "color": DEFAULT_COLOR} for station in data
            ]
            keys.set_stations(station_list)
            had_stations = True
            refresh_status(player.connected, upstream_status, had_stations)
            display.refresh()
        elif event_name == "station_playing":
            keys.set_playing_station(data)
        elif event_name == "player_status":
            upstream_status = data.get("summary", "") if data else ""
            refresh_status(player.connected, upstream_status, had_stations)
            display.refresh()

    # --- Encoder Rotation ---
    position = macropad.encoder
    if position != last_position:
        if keys.playing_station_index is not None:
            direction = "up" if position > last_position else "down"
            player.send_command("volume", direction)
        else:
            num_pages = len(keys.pages)
            if position > last_position:
                keys.switch_page((keys.current_page_index + 1) % num_pages)
            else:
                keys.switch_page((keys.current_page_index - 1 + num_pages) % num_pages)
        last_position = position

    # --- Encoder Press ---
    macropad.encoder_switch_debounced.update()
    pressed = macropad.encoder_switch_debounced.pressed
    if pressed and not last_encoder_switch:
        if keys.playing_station_index is not None:
            player.send_command("station_request", None)
            keys.flash_keys()
    last_encoder_switch = pressed

    # --- Key Events ---
    last_pressed_station = None
    while True:
        # Drain keypad event queue so simultaneous presses resolve to the "last" press.
        key_event = macropad.keys.events.get()
        if not key_event:
            break
        if not key_event.pressed:
            continue

        key_number = key_event.key_number
        station_name = keys.get_station_name(key_number)
        if station_name:
            keys.set_key_color(key_number, PRESSED_COLOR)
            last_pressed_station = station_name

    if last_pressed_station:
        player.send_command("station_request", last_pressed_station)
