/*
This file is part of the radio-pad project.
https://github.com/briceburg/radio-pad

Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it is useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
*/

export class RadioPadStreamer {
  constructor() {
    this.audio = null;
    this.stations = new Map();
  }

  play(stationName) {
    this.stop();
    const url = this.stations.get(stationName);
    // TODO: support .pls URLS
    if (url) {
      this.audio = new Audio(url);
      this.audio.play();
    }
  }

  stop() {
    if (this.audio) {
      this.audio.pause();
      this.audio = null;
    }
  }

  setStations(station_data) {
    this.stations = new Map(
      station_data.stations.map((station) => [station.name, station.url]),
    );
  }
}
