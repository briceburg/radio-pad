/*
This file is part of the radio-pad project.
https://github.com/briceburg/radio-pad

Copyright (c) 2025 Brice Burgess <https://github.com/briceburg>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program. If not, see <http://www.gnu.org/licenses/>.
*/

import { EventEmitter } from "./interfaces.js";

export class RadioPadState extends EventEmitter {
  constructor(
    initialState = {
      player: {
        id: null,
        name: null,
        stations_url: null,
        switchboard_url: null,
      },
      stations_url: null,
      currentStation: null,
    },
  ) {
    super();
    this.state = initialState;
  }

  get(key) {
    return this.state[key] || null;
  }

  async set(key, value) {
    if (value !== this.state[key]) {
      this.state[key] = value;
      await this.emitEvent("on-change", { key, value });
    }
  }
}
