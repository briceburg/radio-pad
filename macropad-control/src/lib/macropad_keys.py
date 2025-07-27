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

DEFAULT_COLOR = 0x000077
PLAYING_COLOR = 0x015C01
PRESSED_COLOR = 0x999999
MACROPAD_KEY_COUNT = 12


class MacropadKeys:
    def __init__(self, macropad, display):
        self.macropad = macropad
        self.display = display
        self.macropad.pixels.auto_write = False
        self.macropad.pixels.brightness = 0.10
        self.stations = []
        self.playing_station_index = None
        self.current_page_index = 0
        self.pages = [{"stations": [], "title": "iCEBURG Radio"}]

    def set_stations(self, stations_list):
        self.playing_station_index = None
        self.stations = stations_list
        self.pages = []
        if stations_list:
            for i in range(0, len(stations_list), MACROPAD_KEY_COUNT):
                self.pages.append(
                    {
                        "stations": stations_list[i : i + MACROPAD_KEY_COUNT],
                        "title": (
                            "iCEBURG Radio"
                            if len(stations_list) <= MACROPAD_KEY_COUNT
                            else f"iCEBURG Radio {int(i / MACROPAD_KEY_COUNT) + 1}"
                        ),
                    }
                )
        else:
            self.pages = [{"stations": [], "title": "iCEBURG Radio"}]
        self.switch_page(0)

    def switch_page(self, page_index):
        self.current_page_index = page_index
        self.refresh()

    def refresh(self):
        page = self.pages[self.current_page_index]

        title = page["title"]
        if self.playing_station_index is not None:
            station_page_index = self.get_station_page_index(
                self.playing_station_index
            )
            if self.current_page_index == station_page_index:
                station_index_on_page = self.playing_station_index % MACROPAD_KEY_COUNT
                title = page["stations"][station_index_on_page].get("name", "?")

        self.display.set_title(title, False)

        for i in range(MACROPAD_KEY_COUNT):
            self.display.unhighlight_group(i)
            if i < len(page["stations"]):
                station = page["stations"][i]
                self.display.set_group_text(i, station.get("name", ""))

                station_global_index = self.current_page_index * MACROPAD_KEY_COUNT + i
                if station_global_index == self.playing_station_index:
                    self.macropad.pixels[i] = PLAYING_COLOR
                    self.display.highlight_group(i)
                else:
                    self.macropad.pixels[i] = station.get("color", DEFAULT_COLOR)
            else:
                self.macropad.pixels[i] = 0
                self.display.set_group_text(i, "")

        self.macropad.pixels.show()
        self.display.refresh()

    def set_key_color(self, key_index, color):
        if 0 <= key_index < MACROPAD_KEY_COUNT:
            self.macropad.pixels[key_index] = color
            self.macropad.pixels.show()

    def set_playing_station(self, station_name):
        self.playing_station_index = None
        if station_name:
            for i, station in enumerate(self.stations):
                if station.get("name") == station_name:
                    self.playing_station_index = i
                    break

        if self.playing_station_index is not None:
            page_index = self.get_station_page_index(self.playing_station_index)
            self.switch_page(page_index)
        else:
            self.refresh()

    def get_station_page_index(self, station_index):
        return station_index // MACROPAD_KEY_COUNT

    def get_station_name(self, key_number):
        page = self.pages[self.current_page_index]
        if key_number < len(page["stations"]):
            return page["stations"][key_number].get("name")
        return None

    def flash_keys(self, color=0x990909, duration=0.88):
        for i in range(MACROPAD_KEY_COUNT):
            self.macropad.pixels[i] = color
        self.macropad.pixels.show()
        time.sleep(duration)
        self.refresh()